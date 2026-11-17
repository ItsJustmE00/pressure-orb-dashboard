#property strict
#property version "1.00"
#property description "Opening-range breakout M15, demo/research only"

input double InpRiskPct = 0.5;
input double InpTargetR = 3.0;
input int InpMagic = 20261109;
input int InpRangeHourNY = 9;
input int InpRangeMinuteNY = 30;
input int InpCloseHourNY = 16;
input int InpCloseMinuteNY = 0;
input int InpCloseBufferMinutes = 5;
input int InpFridayCloseBufferMinutes = 10;
input int InpServerGMTOffsetHours = 0;
input int InpSlippagePoints = 30;
input double InpMaxSpreadPoints = 0;
input bool InpOneTradePerDay = true;
input int InpMaxTradesPerDay = 2;      // re-entrees max/jour si OneTradePerDay=false
input bool InpRequireFreshCross = true; // re-entree seulement apres retour sous le niveau
input bool InpLongOnly = false;
input bool InpUseTrendFilter = false;
input double InpTrendMax = 0.00425;
input bool InpUseRsiFilter = false;
input double InpRsiMin = 56.5;
input bool InpUseRangeRankFilter = false;
input double InpRangeRankMax = 0.20;
input bool InpUseOrCloseFilter = false;
input double InpOrCloseMin = 0.8044;
input bool InpUseMomFilter = false;
input double InpMomMin = 0.00123;
input bool InpUsePrevCloseFilter = false;
input double InpPrevCloseMin = 0.9085;
input bool InpUsePrevWickFilter = false;
input double InpPrevWickMax = 0.07838;
input bool InpShortOnly = false;
input bool InpUseShortOrFilter = false;
input double InpShortOrCloseMax = 0.1956;
input bool InpUseShortMomFilter = false;
input double InpShortMomMax = -0.00123;
input bool InpUseShortTrendFilter = false;
input double InpShortTrendMin = -0.00425;
input bool InpDebugTrend = false;
input bool InpShowDashboard = true;
input int InpDashX = 12;
input int InpDashY = 24;
input int InpDashFontSize = 9;
input color InpDashBg = C'12,18,28';
input color InpDashText = clrWhiteSmoke;
input color InpDashAccent = clrDeepSkyBlue;
input color InpDashGood = clrLimeGreen;
input color InpDashBad = clrTomato;
input color InpDashWarn = clrGold;

#define DASH_PREFIX "ORBDASH_"
#define DASH_WIDTH 390
#define DASH_HEIGHT 525

datetime g_day = 0;
double g_high = 0.0;
double g_low = 0.0;
double g_range_close = 0.0;
double g_range_rank = -1.0;
bool g_range_ready = false;
int g_trades_today = 0;
bool g_below_high = true;   // tick precedent : prix sous le high du range (pour recroisement)
bool g_above_low = true;    // tick precedent : prix au-dessus du low du range
int g_ema20_handle = INVALID_HANDLE;
int g_ema50_handle = INVALID_HANDLE;
int g_rsi_handle = INVALID_HANDLE;
bool g_dash_enabled = false;
datetime g_dash_day = 0;
double g_dash_day_peak = 0.0;
double g_dash_session_peak = 0.0;
double g_dash_session_maxdd = 0.0;
uint g_dash_last_ms = 0;

ENUM_ORDER_TYPE_FILLING FillingMode();

int ServerOffsetHours()
{
   return InpServerGMTOffsetHours;
}

datetime MakeTime(int year, int month, int day, int hour, int minute)
{
   MqlDateTime t;
   t.year = year;
   t.mon = month;
   t.day = day;
   t.hour = hour;
   t.min = minute;
   t.sec = 0;
   return StructToTime(t);
}

int FirstSunday(int year, int month)
{
   for(int day = 1; day <= 7; day++)
   {
      datetime t = MakeTime(year, month, day, 0, 0);
      MqlDateTime dt;
      TimeToStruct(t, dt);
      if(dt.day_of_week == 0)
         return day;
   }
   return 1;
}

int SecondSunday(int year, int month)
{
   return FirstSunday(year, month) + 7;
}

bool IsDSTUTC(datetime utc)
{
   MqlDateTime d;
   TimeToStruct(utc, d);
   datetime start = MakeTime(d.year, 3, SecondSunday(d.year, 3), 7, 0);
   datetime end = MakeTime(d.year, 11, FirstSunday(d.year, 11), 6, 0);
   return utc >= start && utc < end;
}

bool IsDSTLocal(datetime local)
{
   MqlDateTime d;
   TimeToStruct(local, d);
   datetime start = MakeTime(d.year, 3, SecondSunday(d.year, 3), 2, 0);
   datetime end = MakeTime(d.year, 11, FirstSunday(d.year, 11), 2, 0);
   return local >= start && local < end;
}

datetime UTCToNY(datetime utc)
{
   int offset = IsDSTUTC(utc) ? 4 : 5;
   return utc - offset * 3600;
}

datetime NYToUTC(datetime local)
{
   int offset = IsDSTLocal(local) ? 4 : 5;
   return local + offset * 3600;
}

datetime NYDate(datetime ny_now)
{
   MqlDateTime d;
   TimeToStruct(ny_now, d);
   return MakeTime(d.year, d.mon, d.day, 0, 0);
}

datetime CloseNYTime(datetime ny_now)
{
   MqlDateTime d;
   TimeToStruct(ny_now, d);
   datetime close_ny = MakeTime(d.year, d.mon, d.day, InpCloseHourNY, InpCloseMinuteNY);
   int buffer = (int)MathMax(0.0, MathMin(60.0, (double)InpCloseBufferMinutes));
   if(d.day_of_week == 5)
   {
      int friday_buffer = (int)MathMax(0.0, MathMin(60.0,
                          (double)InpFridayCloseBufferMinutes));
      buffer = (int)MathMax((double)buffer, (double)friday_buffer);
   }
   return close_ny - buffer * 60;
}

bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      return true;
   }
   return false;
}

bool HasStalePosition(datetime ny_day)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      datetime opened_server = (datetime)PositionGetInteger(POSITION_TIME);
      if(opened_server <= 0)
         continue;
      datetime opened_utc = opened_server - ServerOffsetHours() * 3600;
      datetime opened_ny = UTCToNY(opened_utc);
      if(NYDate(opened_ny) < ny_day)
         return true;
   }
   return false;
}

double DailyTrend()
{
   double ema20[1], ema50[1], close1[1];
   if(g_ema20_handle == INVALID_HANDLE || g_ema50_handle == INVALID_HANDLE)
      return 999.0;
   if(CopyBuffer(g_ema20_handle, 0, 1, 1, ema20) != 1)
      return 999.0;
   if(CopyBuffer(g_ema50_handle, 0, 1, 1, ema50) != 1)
      return 999.0;
   if(CopyClose(_Symbol, PERIOD_D1, 1, 1, close1) != 1)
      return 999.0;
   if(ema20[0] <= 0.0 || ema50[0] <= 0.0 || close1[0] <= 0.0)
      return 999.0;
   return (ema20[0] - ema50[0]) / close1[0];
}

double RsiM15()
{
   double b[1];
   if(g_rsi_handle == INVALID_HANDLE)
      return -1.0;
   if(CopyBuffer(g_rsi_handle, 0, 1, 1, b) != 1)
      return -1.0;
   return b[0];
}

double OrClosePos()
{
   if(g_high <= g_low || g_range_close <= 0.0)
      return -1.0;
   return (g_range_close - g_low) / (g_high - g_low);
}

double PrevMomentum6()
{
   double c1 = iClose(_Symbol, PERIOD_M15, 1);
   double c7 = iClose(_Symbol, PERIOD_M15, 7);
   if(c1 <= 0.0 || c7 <= 0.0)
      return -999.0;
   return c1 / c7 - 1.0;
}

double PrevClosePos()
{
   double o = iOpen(_Symbol, PERIOD_M15, 1);
   double h = iHigh(_Symbol, PERIOD_M15, 1);
   double l = iLow(_Symbol, PERIOD_M15, 1);
   double c = iClose(_Symbol, PERIOD_M15, 1);
   if(h <= l || o <= 0.0 || c <= 0.0)
      return -1.0;
   return (c - l) / (h - l);
}

double PrevUpperWick()
{
   double o = iOpen(_Symbol, PERIOD_M15, 1);
   double h = iHigh(_Symbol, PERIOD_M15, 1);
   double l = iLow(_Symbol, PERIOD_M15, 1);
   double c = iClose(_Symbol, PERIOD_M15, 1);
   if(h <= l || o <= 0.0 || c <= 0.0)
      return -1.0;
   return (h - MathMax(o, c)) / (h - l);
}

double OpeningRangeRank()
{
   if(g_high <= g_low)
      return -1.0;
   double current = g_high - g_low;
   int found = 0;
   int less = 0;
   datetime ny_now = UTCToNY(TimeCurrent() - ServerOffsetHours() * 3600);
   MqlDateTime nyd;
   TimeToStruct(ny_now, nyd);
   datetime ny_day = MakeTime(nyd.year, nyd.mon, nyd.day, 0, 0);
   for(int i = 1; i < 20000 && found < 59; i++)
   {
      datetime bt = iTime(_Symbol, PERIOD_M15, i);
      if(bt == 0)
         break;
      datetime ny = UTCToNY(bt - ServerOffsetHours() * 3600);
      MqlDateTime d;
      TimeToStruct(ny, d);
      if(d.hour != 9 || d.min != 30)
         continue;
      datetime day = MakeTime(d.year, d.mon, d.day, 0, 0);
      if(day == ny_day)
         continue;
      double r = iHigh(_Symbol, PERIOD_M15, i) - iLow(_Symbol, PERIOD_M15, i);
      if(r <= 0.0)
         continue;
      if(r <= current)
         less++;
      found++;
   }
   if(found < 20)
      return -1.0;
   return (double)(less + 1) / (double)(found + 1);
}

void ClosePositions()
{
   static datetime last_attempt = 0;
   static datetime last_log = 0;
   datetime now = TimeCurrent();
   if(last_attempt != 0 && now - last_attempt < 60)
      return;
   last_attempt = now;
   bool can_log = (last_log == 0 || now - last_log >= 60);
   for(int attempt = 0; attempt < 3; attempt++)
   {
      bool found = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0)
            continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol)
            continue;
         if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic)
            continue;
         found = true;
         long type = PositionGetInteger(POSITION_TYPE);
         double volume = PositionGetDouble(POSITION_VOLUME);
         MqlTradeRequest req;
         MqlTradeResult res;
         ZeroMemory(req);
         ZeroMemory(res);
         req.action = TRADE_ACTION_DEAL;
         req.symbol = _Symbol;
         req.volume = volume;
         req.deviation = InpSlippagePoints;
         req.magic = InpMagic;
         req.position = ticket;
         req.comment = "ORB close";
         req.type = (type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         req.price = (type == POSITION_TYPE_BUY) ?
                     SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                     SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         req.type_filling = FillingMode();
         if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
         {
            if(can_log)
            {
               Print("ORB close failed retcode=", res.retcode,
                     " ticket=", ticket, " volume=", DoubleToString(volume, 2));
               last_log = now;
               can_log = false;
            }
         }
      }
      if(!found)
         return;
      Sleep(200);
   }
}

double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      return price;
   return MathRound(price / tick) * tick;
}

double NormalizeVolume(double volume)
{
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      step = 0.01;
   volume = MathFloor(volume / step) * step;
   if(volume < minv)
      volume = minv;
   if(volume > maxv)
      volume = maxv;
   return NormalizeDouble(volume, 2);
}

ENUM_ORDER_TYPE_FILLING FillingMode()
{
   long modes = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((modes & SYMBOL_FILLING_FOK) != 0)
      return ORDER_FILLING_FOK;
   if((modes & SYMBOL_FILLING_IOC) != 0)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

bool Enter(int side, double entry, double stop, double target)
{
   double stop_distance = MathAbs(entry - stop);
   if(stop_distance <= 0.0)
      return false;
   long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double min_distance = (double)stops_level * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(stop_distance < min_distance)
      return false;
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0.0 || tick_value <= 0.0)
      return false;
   double risk_money = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
   double lots = risk_money / (stop_distance / tick_size * tick_value);
   lots = NormalizeVolume(lots);
   double margin = 0.0;
   if(!OrderCalcMargin((ENUM_ORDER_TYPE)side, _Symbol, lots, entry, margin))
      return false;
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.8)
   {
      Print("ORB margin refused");
      return false;
   }
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = _Symbol;
   req.volume = lots;
   req.type = (ENUM_ORDER_TYPE)side;
   req.price = (side == ORDER_TYPE_BUY) ?
               SymbolInfoDouble(_Symbol, SYMBOL_ASK) :
               SymbolInfoDouble(_Symbol, SYMBOL_BID);
   req.sl = NormalizePrice(stop);
   req.tp = NormalizePrice(target);
   req.deviation = InpSlippagePoints;
   req.magic = InpMagic;
   req.comment = "ORB entry";
   req.type_filling = FillingMode();
   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("ORB entry failed retcode=", res.retcode, " volume=", lots);
      return false;
   }
   Print("ORB entry ", (side == ORDER_TYPE_BUY ? "BUY " : "SELL "),
         "vol=", lots, " entry=", req.price, " sl=", req.sl, " tp=", req.tp);
   return true;
}

void ResetDay(datetime day)
{
   g_day = day;
   g_high = 0.0;
   g_low = 0.0;
   g_range_close = 0.0;
   g_range_rank = -1.0;
   g_range_ready = false;
   g_trades_today = 0;
   g_below_high = true;
   g_above_low = true;
}

void TryRange(datetime ny_now)
{
   if(g_range_ready)
      return;
   MqlDateTime d;
   TimeToStruct(ny_now, d);
   datetime range_start_ny = MakeTime(d.year, d.mon, d.day, InpRangeHourNY, InpRangeMinuteNY);
   datetime range_end_ny = range_start_ny + 15 * 60;
   if(ny_now < range_end_ny)
      return;
   datetime range_start_utc = NYToUTC(range_start_ny);
   datetime range_start_server = range_start_utc + ServerOffsetHours() * 3600;
   int shift = iBarShift(_Symbol, PERIOD_M15, range_start_server, true);
   if(shift < 0)
   {
      Print("ORB range bar not found");
      return;
   }
   datetime bar_time = iTime(_Symbol, PERIOD_M15, shift);
   if(MathAbs((long)(bar_time - range_start_server)) > 60)
   {
      Print("ORB range bar mismatch");
      return;
   }
   g_high = iHigh(_Symbol, PERIOD_M15, shift);
   g_low = iLow(_Symbol, PERIOD_M15, shift);
   g_range_close = iClose(_Symbol, PERIOD_M15, shift);
   if(g_high <= g_low || g_range_close <= 0.0)
      return;
   g_range_ready = true;
   if(InpUseRangeRankFilter)
      g_range_rank = OpeningRangeRank();
   Print("ORB range high=", g_high, " low=", g_low, " rank=", g_range_rank);
   if(InpDebugTrend)
      Print("ORB trend=", DoubleToString(DailyTrend(), 6), " max=", InpTrendMax,
            " orclose=", DoubleToString(OrClosePos(), 4),
            " mom6=", DoubleToString(PrevMomentum6(), 6));
}

string DashMoney(double value)
{
   return DoubleToString(value, 2);
}

string DashSigned(double value)
{
   return (value >= 0.0 ? "+" : "") + DoubleToString(value, 2);
}

string DashPct(double value)
{
   return DoubleToString(value, 2) + "%";
}

string DashPrice(double value)
{
   return (value > 0.0 ? DoubleToString(value, _Digits) : "-");
}

string DashSide(long type)
{
   return (type == POSITION_TYPE_BUY ? "BUY" : "SELL");
}

color DashPnlColor(double value)
{
   if(value > 0.0)
      return InpDashGood;
   if(value < 0.0)
      return InpDashBad;
   return InpDashText;
}

void DashLabel(string key, string text, int y, color clr, int size_delta = 0)
{
   if(!g_dash_enabled)
      return;
   string name = DASH_PREFIX + key;
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, InpDashX + 14);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, InpDashY + y);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpDashFontSize + size_delta);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_ZORDER, 1);
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
}

void CreateDashboard()
{
   if(!g_dash_enabled)
      return;
   string name = DASH_PREFIX + "bg";
   if(ObjectFind(0, name) >= 0)
      return;
   ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, InpDashX);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, InpDashY);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, DASH_WIDTH);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, DASH_HEIGHT);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, InpDashBg);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, InpDashAccent);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, name, OBJPROP_ZORDER, 0);
}

void TodayStats(int &trades, double &closed_pnl)
{
   trades = 0;
   closed_pnl = 0.0;
   datetime utc_now = TimeCurrent() - ServerOffsetHours() * 3600;
   datetime ny_now = UTCToNY(utc_now);
   MqlDateTime d;
   TimeToStruct(ny_now, d);
   datetime ny_start = MakeTime(d.year, d.mon, d.day, 0, 0);
   datetime server_start = NYToUTC(ny_start) + ServerOffsetHours() * 3600;
   if(!HistorySelect(server_start, TimeCurrent()))
      return;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol)
         continue;
      if((int)HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic)
         continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN)
         trades++;
      else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY || entry == DEAL_ENTRY_INOUT)
         closed_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                     + HistoryDealGetDouble(ticket, DEAL_SWAP)
                     + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   }
}

double BotFloatingPnL()
{
   double pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return pnl;
}

bool GetBotPosition(ulong &ticket, long &type, double &volume, double &entry,
                    double &sl, double &tp, double &pnl)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      ticket = t;
      type = PositionGetInteger(POSITION_TYPE);
      volume = PositionGetDouble(POSITION_VOLUME);
      entry = PositionGetDouble(POSITION_PRICE_OPEN);
      sl = PositionGetDouble(POSITION_SL);
      tp = PositionGetDouble(POSITION_TP);
      pnl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      return true;
   }
   return false;
}

void UpdateDashboard()
{
   if(!g_dash_enabled)
      return;
   uint now = GetTickCount();
   if(g_dash_last_ms != 0 && now - g_dash_last_ms < 900)
      return;
   g_dash_last_ms = now;
   CreateDashboard();

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double floating = AccountInfoDouble(ACCOUNT_PROFIT);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);

   ENUM_ACCOUNT_TRADE_MODE account_mode =
      (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   string mode = (account_mode == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" :
                 (account_mode == ACCOUNT_TRADE_MODE_REAL ? "REAL" : "CONTEST"));
   color mode_color = (account_mode == ACCOUNT_TRADE_MODE_REAL ? InpDashBad : InpDashGood);
   bool algo_on = MQLInfoInteger(MQL_TRADE_ALLOWED) &&
                  TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   string algo = (algo_on ? "ALGO ON" : "ALGO OFF");
   color title_color = (account_mode == ACCOUNT_TRADE_MODE_REAL || !algo_on)
                       ? InpDashBad : mode_color;

   string tf = EnumToString((ENUM_TIMEFRAMES)_Period);
   if(StringFind(tf, "PERIOD_") == 0)
      tf = StringSubstr(tf, 7);
   string direction = (InpShortOnly ? "SHORT ONLY" :
                      (InpLongOnly ? "LONG ONLY" : "BOTH"));

   datetime server_now = TimeCurrent();
   datetime utc_now = server_now - ServerOffsetHours() * 3600;
   datetime ny_now = UTCToNY(utc_now);
   MqlDateTime nyd;
   TimeToStruct(ny_now, nyd);
   datetime ny_day = NYDate(ny_now);
   datetime close_ny = CloseNYTime(ny_now);

   if(g_dash_day != ny_day)
   {
      g_dash_day = ny_day;
      g_dash_day_peak = equity;
   }
   if(g_dash_day_peak <= 0.0)
      g_dash_day_peak = equity;
   if(equity > g_dash_day_peak)
      g_dash_day_peak = equity;
   double day_dd = (g_dash_day_peak > 0.0 ? (1.0 - equity / g_dash_day_peak) * 100.0 : 0.0);
   if(g_dash_session_peak <= 0.0)
      g_dash_session_peak = equity;
   if(equity > g_dash_session_peak)
      g_dash_session_peak = equity;
   double session_dd = (g_dash_session_peak > 0.0 ?
                        (1.0 - equity / g_dash_session_peak) * 100.0 : 0.0);
   if(session_dd > g_dash_session_maxdd)
      g_dash_session_maxdd = session_dd;

   int trades_today = 0;
   double closed_today = 0.0;
   TodayStats(trades_today, closed_today);
   double bot_float = BotFloatingPnL();
   double today_pnl = closed_today + bot_float;

   double trend = DailyTrend();
   double orc = OrClosePos();
   double mom = PrevMomentum6();
   bool long_ok = g_range_ready;
   bool short_ok = g_range_ready;
   if(InpUseTrendFilter && (trend >= 900.0 || trend > InpTrendMax))
      long_ok = false;
   if(InpUseOrCloseFilter && (orc < 0.0 || orc < InpOrCloseMin))
      long_ok = false;
   if(InpUseMomFilter && (mom <= -900.0 || mom < InpMomMin))
      long_ok = false;
   if(InpUseShortTrendFilter && (trend >= 900.0 || trend < InpShortTrendMin))
      short_ok = false;
   if(InpUseShortOrFilter && (orc < 0.0 || orc > InpShortOrCloseMax))
      short_ok = false;
   if(InpUseShortMomFilter && (mom <= -900.0 || mom > InpShortMomMax))
      short_ok = false;

   MqlTick tick;
   double ask = 0.0;
   double bid = 0.0;
   if(SymbolInfoTick(_Symbol, tick))
   {
      ask = tick.ask;
      bid = tick.bid;
   }
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread_pts = (point > 0.0 ? (ask - bid) / point : 0.0);

   ulong pos_ticket = 0;
   long pos_type = 0;
   double pos_volume = 0.0;
   double pos_entry = 0.0;
   double pos_sl = 0.0;
   double pos_tp = 0.0;
   double pos_pnl = 0.0;
   bool has_position = GetBotPosition(pos_ticket, pos_type, pos_volume,
                                      pos_entry, pos_sl, pos_tp, pos_pnl);
   bool weekend = (nyd.day_of_week == 0 || nyd.day_of_week == 6);
   ENUM_SYMBOL_TRADE_MODE symbol_mode =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   bool market_closed = weekend || symbol_mode == SYMBOL_TRADE_MODE_DISABLED ||
                        ny_now >= close_ny;

   string status = "";
   color status_color = InpDashWarn;
   if(has_position)
   {
      status = "IN POSITION";
      status_color = InpDashGood;
   }
   else if(market_closed)
   {
      status = (weekend ? "WEEKEND - MARKET CLOSED" : "CLOSED FOR TODAY");
      status_color = InpDashText;
   }
   else if(g_trades_today >= InpMaxTradesPerDay)
   {
      status = "MAX TRADES DONE";
      status_color = InpDashText;
   }
   else if(!g_range_ready)
   {
      status = "WAITING FOR RANGE";
      status_color = InpDashWarn;
   }
   else if(long_ok && short_ok)
   {
      status = "ARMED - BOTH SIDES";
      status_color = InpDashGood;
   }
   else if(long_ok)
   {
      status = "ARMED - LONG";
      status_color = InpDashGood;
   }
   else if(short_ok)
   {
      status = "ARMED - SHORT";
      status_color = InpDashGood;
   }
   else
   {
      status = "WAITING BREAKOUT";
      status_color = InpDashWarn;
   }

   DashLabel("title", "ORB PORTFOLIO  |  " + mode + "  |  " + algo, 12, title_color, 3);
   DashLabel("sub", _Symbol + " " + tf + "  |  " + direction + "  |  #" +
             IntegerToString(InpMagic) + "  |  risk " +
             DoubleToString(InpRiskPct, 2) + "%  |  " +
             DoubleToString(InpTargetR, 1) + "R", 34, InpDashText, 0);
   DashLabel("acct", "ACCOUNT  " + IntegerToString(login) + "  |  " + currency +
             "  |  1:" + IntegerToString(leverage), 60, InpDashAccent, 0);
   DashLabel("balance", "Balance:       " + DashMoney(balance) + " " + currency, 80,
             InpDashText, 0);
   DashLabel("equity", "Equity:        " + DashMoney(equity) + " " + currency, 99,
             InpDashText, 0);
   DashLabel("floating", "Floating P&L:  " + DashSigned(floating) + " " + currency, 118,
             DashPnlColor(floating), 0);
   DashLabel("free", "Free margin:   " + DashMoney(free_margin) + " " + currency, 137,
             InpDashText, 0);
   DashLabel("margin", "Margin level:  " +
             (margin_level > 0.0 ? DashPct(margin_level) : "-"), 156, InpDashText, 0);
   DashLabel("today_h", "TODAY", 182, InpDashAccent, 0);
   DashLabel("today_pnl", "Bot P&L:       " + DashSigned(today_pnl) + " " + currency, 202,
             DashPnlColor(today_pnl), 0);
   DashLabel("today_stats", "Trades: " + IntegerToString(trades_today) +
             "  |  Day DD " + DashPct(day_dd) + "  |  Max DD " +
             DashPct(g_dash_session_maxdd), 221, InpDashText, 0);
   DashLabel("pos_h", "POSITION", 247, InpDashAccent, 0);
   if(has_position)
   {
      DashLabel("pos_side", "POSITION  " + DashSide(pos_type) + " " +
                DoubleToString(pos_volume, 2) + " @ " + DashPrice(pos_entry), 267,
                InpDashAccent, 0);
      DashLabel("pos_levels", "SL " + DashPrice(pos_sl) + "  |  TP " +
                DashPrice(pos_tp), 286, InpDashText, 0);
      double risk_money = balance * InpRiskPct / 100.0;
      double pos_r = (risk_money > 0.0 ? pos_pnl / risk_money : 0.0);
      DashLabel("pos_pnl", "P&L " + DashSigned(pos_pnl) + " " + currency +
                "  |  " + DashSigned(pos_r) + "R", 305, DashPnlColor(pos_pnl), 0);
   }
   else
   {
      DashLabel("pos_side", "POSITION  FLAT", 267, InpDashText, 0);
      DashLabel("pos_levels", "No open trade for this magic", 286, InpDashText, 0);
      DashLabel("pos_pnl", "Next window: 09:30-09:45 NY", 305, InpDashText, 0);
   }
   DashLabel("market_h", "MARKET", 331, InpDashAccent, 0);
   string range_text = (g_range_ready ?
      DashPrice(g_high) + " / " + DashPrice(g_low) + "  (" +
      DoubleToString(g_high - g_low, 1) + ")" : "waiting 09:30-09:45 NY");
   DashLabel("range", "Range:         " + range_text, 351, InpDashText, 0);
   string orc_text = (g_range_ready && orc >= 0.0 ? DoubleToString(orc, 3) : "-");
   string trend_text = (trend < 900.0 ? DoubleToString(trend, 5) : "-");
   string mom_text = (mom > -900.0 ? DoubleToString(mom * 100.0, 3) + "%" : "-");
   DashLabel("filters", "OR close " + orc_text + "  |  trend " + trend_text +
             "  |  mom6 " + mom_text, 370, InpDashText, 0);
   string long_text = (g_range_ready ? (long_ok ? "OK" : "NO") : "WAIT");
   string short_text = (g_range_ready ? (short_ok ? "OK" : "NO") : "WAIT");
   DashLabel("sides", "LONG filters: " + long_text + "  |  SHORT filters: " +
             short_text, 389, (long_ok || short_ok ? InpDashGood : InpDashBad), 0);
   string max_spread = (InpMaxSpreadPoints > 0.0 ?
      DoubleToString(InpMaxSpreadPoints, 0) : "off");
   color spread_color = (InpMaxSpreadPoints > 0.0 && spread_pts > InpMaxSpreadPoints ?
                         InpDashBad : InpDashText);
   DashLabel("spread", "Spread: " + DoubleToString(spread_pts, 0) +
             " pts  |  max " + max_spread, 408, spread_color, 0);
   DashLabel("time_h", "TIME", 434, InpDashAccent, 0);
   DashLabel("server", "Server " + TimeToString(server_now, TIME_DATE | TIME_MINUTES) +
             "  |  NY " + TimeToString(ny_now, TIME_DATE | TIME_MINUTES), 454,
             InpDashText, 0);
   DashLabel("status", "STATUS  " + status, 473, status_color, 1);
   ChartRedraw(0);
}

void OnTimer()
{
   UpdateDashboard();
}

void OnTick()
{
   UpdateDashboard();
   datetime utc_now = TimeCurrent() - ServerOffsetHours() * 3600;
   datetime ny_now = UTCToNY(utc_now);
   MqlDateTime nyd;
   TimeToStruct(ny_now, nyd);
   if(nyd.day_of_week == 0 || nyd.day_of_week == 6)
      return;
   datetime ny_day = NYDate(ny_now);
   if(g_day != ny_day)
      ResetDay(ny_day);
   datetime close_ny = CloseNYTime(ny_now);
   if(ny_now >= close_ny)
   {
      if(HasPosition())
         ClosePositions();
      return;
   }
   TryRange(ny_now);
   if(!g_range_ready)
      return;
   if(InpOneTradePerDay && g_trades_today >= 1)
      return;
   if(!InpOneTradePerDay && g_trades_today >= InpMaxTradesPerDay)
      return;
   if(HasPosition())
   {
      if(HasStalePosition(ny_day))
      {
         ClosePositions();
         return;
      }
      return;
   }
   if(ny_now < MakeTime(nyd.year, nyd.mon, nyd.day, InpRangeHourNY, InpRangeMinuteNY) + 15 * 60)
      return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
      return;
   double spread = (ask - bid) / SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(InpMaxSpreadPoints > 0.0 && spread > InpMaxSpreadPoints)
      return;
   // etat du tick precedent pour exiger un recroisement frais du niveau
   bool was_below_high = g_below_high;
   bool was_above_low = g_above_low;
   g_below_high = (bid < g_high);
   g_above_low = (ask > g_low);
   bool long_signal = !InpShortOnly && (ask >= g_high)
                      && (!InpRequireFreshCross || was_below_high);
   bool short_signal = !InpLongOnly && (bid <= g_low)
                       && (!InpRequireFreshCross || was_above_low);
   if(!long_signal && !short_signal)
      return;
   if(InpUseRsiFilter)
   {
      double rsi = RsiM15();
      if(rsi <= 0.0 || rsi < InpRsiMin)
         return;
   }
   if(InpUseRangeRankFilter)
   {
      if(g_range_rank < 0.0 || g_range_rank >= InpRangeRankMax)
         return;
   }
   if(long_signal)
   {
      if(InpUseTrendFilter)
      {
         double trend = DailyTrend();
         if(trend > InpTrendMax)
            return;
      }
      if(InpUseOrCloseFilter)
      {
         double orc = OrClosePos();
         if(orc < 0.0 || orc < InpOrCloseMin)
            return;
      }
      if(InpUseMomFilter)
      {
         double m6 = PrevMomentum6();
         if(m6 < InpMomMin)
            return;
      }
      if(InpUsePrevCloseFilter)
      {
         double pc = PrevClosePos();
         if(pc < 0.0 || pc < InpPrevCloseMin)
            return;
      }
      if(InpUsePrevWickFilter)
      {
         double pw = PrevUpperWick();
         if(pw < 0.0 || pw > InpPrevWickMax)
            return;
      }
      double stop = g_low;
      double target = ask + InpTargetR * (ask - stop);
      if(Enter(ORDER_TYPE_BUY, ask, stop, target))
         g_trades_today++;
      return;
   }
   if(short_signal)
   {
      if(InpUseShortTrendFilter)
      {
         double trend = DailyTrend();
         if(trend < InpShortTrendMin)
            return;
      }
      if(InpUseShortOrFilter)
      {
         double orc = OrClosePos();
         if(orc < 0.0 || orc > InpShortOrCloseMax)
            return;
      }
      if(InpUseShortMomFilter)
      {
         double m6 = PrevMomentum6();
         if(m6 > InpShortMomMax)
            return;
      }
      double stop = g_high;
      double target = bid - InpTargetR * (stop - bid);
      if(Enter(ORDER_TYPE_SELL, bid, stop, target))
         g_trades_today++;
   }
}

int OnInit()
{
   if(_Period != PERIOD_M15)
   {
      Print("ORB requires M15 chart");
      return INIT_FAILED;
   }
   if(InpUseTrendFilter)
   {
      g_ema20_handle = iMA(_Symbol, PERIOD_D1, 20, 0, MODE_EMA, PRICE_CLOSE);
      g_ema50_handle = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);
      if(g_ema20_handle == INVALID_HANDLE || g_ema50_handle == INVALID_HANDLE)
      {
         Print("ORB daily EMA handle failed");
         return INIT_FAILED;
      }
   }
   if(InpUseRsiFilter)
   {
      g_rsi_handle = iRSI(_Symbol, PERIOD_M15, 14, PRICE_CLOSE);
      if(g_rsi_handle == INVALID_HANDLE)
      {
         Print("ORB RSI handle failed");
         return INIT_FAILED;
      }
   }
   g_dash_enabled = InpShowDashboard &&
                    (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE));
   if(g_dash_enabled)
   {
      g_dash_session_peak = AccountInfoDouble(ACCOUNT_EQUITY);
      if(g_dash_session_peak <= 0.0)
         g_dash_session_peak = AccountInfoDouble(ACCOUNT_BALANCE);
      g_dash_day_peak = g_dash_session_peak;
      CreateDashboard();
      UpdateDashboard();
      EventSetTimer(1);
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, DASH_PREFIX);
   if(g_ema20_handle != INVALID_HANDLE)
      IndicatorRelease(g_ema20_handle);
   if(g_ema50_handle != INVALID_HANDLE)
      IndicatorRelease(g_ema50_handle);
   if(g_rsi_handle != INVALID_HANDLE)
      IndicatorRelease(g_rsi_handle);
}
