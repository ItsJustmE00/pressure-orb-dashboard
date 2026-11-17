#property strict
#property version "1.00"
#property description "Pressure-based ORB M15 - FIXED MONEY MANAGEMENT - FULL DAY TRADING 2:00-23:00 NY"

input double InpRiskPct = 0.5;
input double InpTargetR = 2.0;
input int InpMagic = 20261117;
input int InpRangeHourNY = 2;
input int InpRangeMinuteNY = 0;
input int InpCloseHourNY = 23;
input int InpCloseMinuteNY = 0;
input int InpCloseBufferMinutes = 5;
input int InpFridayCloseBufferMinutes = 10;
input int InpServerGMTOffsetHours = 0;
input int InpSlippagePoints = 30;
input double InpMaxSpreadPoints = 500.0;
input bool InpOneTradePerDay = false;
input int InpMaxTradesPerDay = 10;
input int InpMinPressureBars = 3;
input double InpBuyPressureMin = 0.6;
input double InpSellPressureMin = 0.6;
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

#define DASH_PREFIX "PRESSURE_"
#define DASH_WIDTH 390
#define DASH_HEIGHT 525

datetime g_day = 0;
double g_high = 0.0;
double g_low = 0.0;
bool g_range_ready = false;
int g_trades_today = 0;
double g_base_equity = 0.0;
bool g_dash_enabled = false;

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

datetime UTCToNY(datetime utc)
{
   int offset = IsDSTUTC(utc) ? 4 : 5;
   return utc - offset * 3600;
}

datetime NYToUTC(datetime local)
{
   int offset = IsDSTUTC(local) ? 4 : 5;
   return local + offset * 3600;
}

datetime NYDate(datetime ny_now)
{
   MqlDateTime d;
   TimeToStruct(ny_now, d);
   return MakeTime(d.year, d.mon, d.day, 0, 0);
}

double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
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
   long filling = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_IOC;
}

double CalculatePressure(int bars_count)
{
   double buy_pressure = 0.0;
   double sell_pressure = 0.0;
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 0, bars_count + 1, rates);
   
   if(copied < bars_count + 1)
      return 0.0;
   
   int bullish_count = 0;
   int bearish_count = 0;
   
   for(int i = 1; i <= bars_count; i++)
   {
      double body = MathAbs(rates[i].close - rates[i].open);
      double range_p = rates[i].high - rates[i].low;
      
      if(range_p <= 0.0)
         continue;
      
      double upper_wick = rates[i].high - MathMax(rates[i].open, rates[i].close);
      double lower_wick = MathMin(rates[i].open, rates[i].close) - rates[i].low;
      
      if(rates[i].close > rates[i].open)
      {
         buy_pressure += (body / range_p) * (1.0 - upper_wick / range_p);
         bullish_count++;
      }
      else
      {
         buy_pressure -= (body / range_p) * (1.0 - lower_wick / range_p);
         bearish_count++;
      }
      
      if(rates[i].close < rates[i].open)
      {
         sell_pressure += (body / range_p) * (1.0 - lower_wick / range_p);
      }
      else
      {
         sell_pressure -= (body / range_p) * (1.0 - upper_wick / range_p);
      }
   }
   
   int total = bullish_count + bearish_count;
   if(total > 0)
   {
      buy_pressure = (buy_pressure / total + 1.0) / 2.0;
      sell_pressure = (sell_pressure / total + 1.0) / 2.0;
   }
   
   return buy_pressure;
}

bool RestoreOpeningRange(datetime ny_now)
{
   datetime day_start = NYDate(ny_now);
   MqlDateTime d;
   TimeToStruct(day_start, d);
   datetime range_start_ny = MakeTime(d.year, d.mon, d.day, InpRangeHourNY, InpRangeMinuteNY);
   datetime range_start = NYToUTC(range_start_ny);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, range_start, range_start + 15 * 60 - 1, rates);
   for(int i = 0; i < copied; i++)
   {
      if((datetime)rates[i].time == range_start)
      {
         g_high = rates[i].high;
         g_low = rates[i].low;
         g_range_ready = true;
         Print("PRESSURE range restored: high=", g_high, " low=", g_low);
         return true;
      }
   }
   return false;
}

int CountTradesToday(datetime ny_now)
{
   datetime day_start = NYDate(ny_now);
   datetime from = NYToUTC(day_start);
   if(!HistorySelect(from, TimeCurrent()))
      return 0;

   int count = 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;
      if((int)HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic)
         continue;
      if((int)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      count++;
   }
   return count;
}

bool EnterTrade(ENUM_ORDER_TYPE side, double entry, double stop, double target)
{
   long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double stop_distance = MathAbs(entry - stop);
   double min_distance = (double)stops_level * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(stop_distance < min_distance)
      return false;
   
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0.0 || tick_value <= 0.0)
      return false;
   
   if(g_base_equity <= 0.0)
      g_base_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   double risk_money = g_base_equity * InpRiskPct / 100.0;
   double lots = risk_money / (stop_distance / tick_size * tick_value);
   lots = NormalizeVolume(lots);
   
   double max_lots = 10.0;
   if(lots > max_lots)
   {
      Print("PRESSURE: Lot size capped at ", max_lots, " (calculated: ", lots, ")");
      lots = max_lots;
   }
   
   double margin = 0.0;
   if(!OrderCalcMargin((ENUM_ORDER_TYPE)side, _Symbol, lots, entry, margin))
      return false;
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.8)
   {
      Print("PRESSURE margin refused");
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
   req.comment = "PRESSURE entry";
   req.type_filling = FillingMode();
   
   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("PRESSURE entry failed retcode=", res.retcode, " volume=", lots);
      return false;
   }
   
   Print("PRESSURE entry ", (side == ORDER_TYPE_BUY ? "BUY " : "SELL "),
         "vol=", lots, " entry=", req.price, " sl=", req.sl, " tp=", req.tp);
   return true;
}

bool ClosePosition(ulong ticket)
{
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = _Symbol;
   req.volume = PositionGetDouble(POSITION_VOLUME);
   req.deviation = InpSlippagePoints;
   req.magic = InpMagic;
   req.position = ticket;
   req.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ?
              ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.type_filling = FillingMode();
   
   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("PRESSURE close failed retcode=", res.retcode);
      return false;
   }
   return true;
}

void ResetDay(datetime day)
{
   g_day = day;
   g_high = 0.0;
   g_low = 0.0;
   g_range_ready = false;
   g_trades_today = 0;
}

int OnInit()
{
   g_base_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   datetime ny_now = UTCToNY(TimeCurrent());
   g_day = NYDate(ny_now);
   g_trades_today = CountTradesToday(ny_now);
   Print("PRESSURE ORB initialized, base equity=", g_base_equity, " symbol=", _Symbol);
   Print("Trading hours: ", InpRangeHourNY, ":", InpRangeMinuteNY, " NY to ", InpCloseHourNY, ":", InpCloseMinuteNY, " NY");
   Print("PRESSURE trades today restored=", g_trades_today);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, DASH_PREFIX);
}

void OnTick()
{
   datetime now = TimeCurrent();
   datetime ny_now = UTCToNY(now);
   datetime ny_date = NYDate(ny_now);
   
   if(ny_date != g_day)
      ResetDay(ny_date);
   
   MqlDateTime nyd;
   TimeToStruct(ny_now, nyd);
   bool weekend = (nyd.day_of_week == 0 || nyd.day_of_week == 6);
   
   if(weekend)
      return;
   
   bool has_position = false;
   ulong pos_ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      has_position = true;
      pos_ticket = PositionGetInteger(POSITION_TICKET);
      break;
   }
   
   int range_start_min = InpRangeHourNY * 60 + InpRangeMinuteNY;
   int range_end_min = range_start_min + 15;
   int current_min = nyd.hour * 60 + nyd.min;

   // Apres un redemarrage, reconstruire le range depuis la bougie M15 de 09:30 NY.
   if(!g_range_ready && current_min >= range_start_min)
      RestoreOpeningRange(ny_now);

   if(current_min >= range_start_min && current_min < range_end_min)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(!g_range_ready || bid > g_high)
         g_high = bid;
      if(!g_range_ready || bid < g_low)
         g_low = bid;
      g_range_ready = true;
   }
   
   int close_min = InpCloseHourNY * 60 + InpCloseMinuteNY;
   int buffer = (nyd.day_of_week == 5) ? InpFridayCloseBufferMinutes : InpCloseBufferMinutes;
   
   if(has_position && current_min >= close_min - buffer)
   {
      ClosePosition(pos_ticket);
      return;
   }
   
   if(current_min >= range_end_min && current_min < close_min - buffer)
   {
      if(!has_position && g_trades_today < InpMaxTradesPerDay && g_range_ready)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double spread = ask - bid;
         
         if(spread > InpMaxSpreadPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT))
            return;
         
         double pressure = CalculatePressure(InpMinPressureBars);
         
         if(bid > g_high && pressure >= InpBuyPressureMin)
         {
            double stop = g_low;
            double target = ask + (ask - stop) * InpTargetR;
            if(EnterTrade(ORDER_TYPE_BUY, ask, stop, target))
            {
               g_trades_today++;
               Print("PRESSURE range high=", g_high, " low=", g_low, " buy_pressure=", pressure);
            }
         }
         else if(ask < g_low && (1.0 - pressure) >= InpSellPressureMin)
         {
            double stop = g_high;
            double target = bid - (stop - bid) * InpTargetR;
            if(EnterTrade(ORDER_TYPE_SELL, bid, stop, target))
            {
               g_trades_today++;
               Print("PRESSURE range high=", g_high, " low=", g_low, " sell_pressure=", (1.0 - pressure));
            }
         }
      }
   }
}
