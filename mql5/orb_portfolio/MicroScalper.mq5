#property strict
#property version "1.00"
#property description "MicroScalper HFT : mean-reversion Ornstein-Uhlenbeck par tick"
#property description "Math : z = (mid - mu) / sigma sur fenetre de ticks"
#property description "Entree si |z| > seuil, sortie sur retour a la moyenne (TP) ou z-sigma (SL)"
#property description "Demo/recherche uniquement - garde-fous stricts"

#include <Trade\Trade.mqh>

input double InpRiskPct          = 0.10;   // risque % du solde par trade
input int    InpWindowTicks      = 400;    // fenetre de ticks pour mu/sigma
input double InpZEntry           = 2.5;    // seuil z-score d'entree
input double InpTpSigma          = 0.8;    // take profit en multiples de sigma (retour a la moyenne)
input double InpSlSigma          = 2.5;    // stop loss en multiples de sigma
input double InpMaxSpreadPoints  = 150;    // spread max (points)
input double InpMinSigmaPoints   = 1.5;    // sigma min en points (marche trop calme = skip)
input int    InpMaxTradesPerMin  = 8;      // max trades par minute
input int    InpMaxTradesPerDay  = 500;    // max trades par jour (plafond viable)
input double InpDailyLossPct     = 1.0;    // stop jour si perte > % du solde
input int    InpCooldownSec      = 2;      // secondes entre deux trades
input bool   InpLongOnly         = false;
input bool   InpShortOnly        = false;
input int    InpMagic            = 20261116;

CTrade   g_trade;
double   g_buffer[];         // prix mid historises
int      g_count = 0;        // nombre de valeurs dans le buffer
datetime g_day = 0;
int      g_trades_today = 0;
int      g_min = -1;
int      g_trades_this_min = 0;
double   g_day_start_balance = 0.0;
datetime g_last_trade = 0;
ulong    g_position_ticket = 0;

double MidPrice(const MqlTick &t)
{
   return (t.bid + t.ask) * 0.5;
}

void PushMid(double mid)
{
   int size = InpWindowTicks;
   if(ArraySize(g_buffer) != size)
   {
      ArrayResize(g_buffer, size);
      g_count = 0;
   }
   if(g_count < size)
   {
      g_buffer[g_count++] = mid;
      return;
   }
   // decalage : buffer circulaire simplifie (deplace de 1)
   for(int i = 1; i < size; i++)
      g_buffer[i - 1] = g_buffer[i];
   g_buffer[size - 1] = mid;
}

// mu, sigma calcules sur les variations tick-a-tick (processus O-U discret)
bool Stats(double &mu, double &sigma)
{
   int n = g_count;
   if(n < 100)
      return false;
   double sum = 0.0;
   for(int i = 0; i < n; i++)
      sum += g_buffer[i];
   mu = sum / n;
   // sigma : ecart-type des prix autour de mu (echelle du processus)
   double s2 = 0.0;
   for(int i = 0; i < n; i++)
   {
      double d = g_buffer[i] - mu;
      s2 += d * d;
   }
   sigma = MathSqrt(s2 / (n - 1));
   return sigma > 0.0;
}

bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         g_position_ticket = ticket;
         return true;
      }
   }
   g_position_ticket = 0;
   return false;
}

double DailyRealizedPnl()
{
   datetime from = g_day;
   if(!HistorySelect(from, TimeCurrent() + 60))
      return 0.0;
   double pnl = 0.0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(dt == 0)
         continue;
      if(HistoryDealGetInteger(dt, DEAL_MAGIC) != InpMagic)
         continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol)
         continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt, DEAL_ENTRY) != DEAL_ENTRY_OUT)
         continue;
      pnl += HistoryDealGetDouble(dt, DEAL_PROFIT)
           + HistoryDealGetDouble(dt, DEAL_SWAP)
           + HistoryDealGetDouble(dt, DEAL_COMMISSION);
   }
   return pnl;
}

double NormalizeLots(double lots)
{
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / step) * step;
   if(lots < min_lot)
      lots = min_lot;
   if(lots > max_lot)
      lots = max_lot;
   return lots;
}

void ResetDayIfNeeded()
{
   MqlDateTime d;
   TimeToStruct(TimeCurrent(), d);
   d.hour = 0; d.min = 0; d.sec = 0;
   datetime today = StructToTime(d);
   if(today != g_day)
   {
      g_day = today;
      g_trades_today = 0;
      g_min = -1;
      g_trades_this_min = 0;
      g_day_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      Print("MicroScalper: nouveau jour, solde=", DoubleToString(g_day_start_balance, 2));
   }
}

int MinuteKey()
{
   MqlDateTime d;
   TimeToStruct(TimeCurrent(), d);
   return d.hour * 60 + d.min;
}

void OnTick()
{
   ResetDayIfNeeded();

   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;
   if(t.bid <= 0.0 || t.ask <= 0.0)
      return;

   double mid = MidPrice(t);
   PushMid(mid);

   double mu, sigma;
   if(!Stats(mu, sigma))
      return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(sigma / point < InpMinSigmaPoints)
      return;   // marche trop calme : pas d'edge

   double spread_pts = (t.ask - t.bid) / point;
   if(spread_pts > InpMaxSpreadPoints)
      return;

   // garde-fous quotidiens
   if(g_trades_today >= InpMaxTradesPerDay)
      return;
   double daily_pnl = DailyRealizedPnl();
   if(daily_pnl <= -InpDailyLossPct / 100.0 * g_day_start_balance)
      return;

   // limite par minute
   int mk = MinuteKey();
   if(mk != g_min)
   {
      g_min = mk;
      g_trades_this_min = 0;
   }
   if(g_trades_this_min >= InpMaxTradesPerMin)
      return;
   if(TimeCurrent() - g_last_trade < InpCooldownSec)
      return;

   double z = (mid - mu) / sigma;

   if(HasPosition())
   {
      // verrou de securite : si |z| explose, on coupe la position (disaster exit)
      double exit_z = InpSlSigma * 2.0;
      if(MathAbs(z) >= exit_z)
      {
         if(!g_trade.PositionClose(g_position_ticket))
            return;
         Print("MicroScalper: disaster exit z=", DoubleToString(z, 2));
         g_last_trade = TimeCurrent();
      }
      return;
   }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_money = balance * InpRiskPct / 100.0;
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double value_per_point = tick_value * (point / tick_size);

   if(z <= -InpZEntry && !InpShortOnly)
   {
      // mean reversion : prix sous la moyenne -> achat
      double entry = t.ask;
      double sl = entry - InpSlSigma * sigma;
      double tp = entry + InpTpSigma * sigma;
      double sl_points = MathMax((entry - sl) / point, 1.0);
      double lots = NormalizeLots(risk_money / (sl_points * value_per_point));
      if(g_trade.Buy(lots, _Symbol, 0.0, sl, tp, "MS z<0"))
      {
         g_trades_today++;
         g_trades_this_min++;
         g_last_trade = TimeCurrent();
      }
      return;
   }
   if(z >= InpZEntry && !InpLongOnly)
   {
      double entry = t.bid;
      double sl = entry + InpSlSigma * sigma;
      double tp = entry - InpTpSigma * sigma;
      double sl_points = MathMax((sl - entry) / point, 1.0);
      double lots = NormalizeLots(risk_money / (sl_points * value_per_point));
      if(g_trade.Sell(lots, _Symbol, 0.0, sl, tp, "MS z>0"))
      {
         g_trades_today++;
         g_trades_this_min++;
         g_last_trade = TimeCurrent();
      }
   }
}

int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(30);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   ArrayResize(g_buffer, InpWindowTicks);
   g_count = 0;
   g_day_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   Print("MicroScalper demarre : window=", InpWindowTicks, " z=", InpZEntry,
         " tp=", InpTpSigma, "x sigma sl=", InpSlSigma, "x sigma max/day=", InpMaxTradesPerDay,
         " lecture seule du marche, ordres demo uniquement");
   return INIT_SUCCEEDED;
}
