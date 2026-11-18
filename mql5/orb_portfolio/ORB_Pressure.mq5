#property strict
#property version "1.10"
#property description "Pressure-based ORB M15 - range 09:30-09:45 NY - entries 09:45-23:00 NY"

input double InpRiskPct = 0.5;
input double InpTargetR = 2.0;
input int InpMagic = 20261117;
input int InpRangeHourNY = 9;
input int InpRangeMinuteNY = 30;
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

datetime g_day = 0;
double g_high = 0.0;
double g_low = 0.0;
bool g_range_ready = false;
int g_trades_today = 0;
double g_initial_equity = 0.0;
datetime g_last_skip_bar = 0;
string g_last_skip_side = "";
string g_last_skip_reason = "";
datetime g_last_range_warn_bar = 0;

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
   return (datetime)((long)utc - (long)offset * 3600);
}

datetime NYToUTC(datetime ny)
{
   // Resolve the NY offset from the UTC candidate, not from the local time.
   datetime candidate_standard = (datetime)((long)ny + 5 * 3600);
   if(IsDSTUTC(candidate_standard))
      return (datetime)((long)ny + 4 * 3600);
   return candidate_standard;
}

datetime ServerToUTC(datetime server)
{
   return (datetime)((long)server - (long)InpServerGMTOffsetHours * 3600);
}

datetime UTCToServer(datetime utc)
{
   return (datetime)((long)utc + (long)InpServerGMTOffsetHours * 3600);
}

datetime ServerToNY(datetime server)
{
   return UTCToNY(ServerToUTC(server));
}

datetime NYToServer(datetime ny)
{
   return UTCToServer(NYToUTC(ny));
}

datetime ServerNow()
{
   datetime value = TimeTradeServer();
   if(value <= 0)
      value = TimeCurrent();
   return value;
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
   if(tick <= 0.0)
      return price;
   return NormalizeDouble(MathRound(price / tick) * tick, _Digits);
}

int VolumeDigits(double step)
{
   int digits = 0;
   double value = step;
   while(value < 1.0 && digits < 8)
   {
      value *= 10.0;
      digits++;
   }
   return digits;
}

double NormalizeVolume(double volume)
{
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      step = 0.01;
   volume = MathFloor((volume + 1e-9) / step) * step;
   if(volume < minv)
      volume = minv;
   if(volume > maxv)
      volume = maxv;
   return NormalizeDouble(volume, VolumeDigits(step));
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

void CalculatePressure(int bars_count, double &buy_out, double &sell_out,
                       int &bull_out, int &bear_out)
{
   buy_out = 0.5;
   sell_out = 0.5;
   bull_out = 0;
   bear_out = 0;

   if(bars_count <= 0)
      return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 0, bars_count + 2, rates);
   if(copied < bars_count + 1)
      return;

   // Index 0 is forming while a new bar has not closed yet. If the latest
   // bar is already closed (e.g. after the CME break), use it instead of
   // silently skipping it.
   int offset = 1;
   if((long)rates[0].time + 15 * 60 <= (long)ServerNow())
      offset = 0;
   if(copied < bars_count + offset)
      return;

   double buy = 0.0;
   double sell = 0.0;

   for(int k = 0; k < bars_count; k++)
   {
      int i = k + offset;
      double range_p = rates[i].high - rates[i].low;
      if(range_p <= 0.0)
         continue;

      double body = MathAbs(rates[i].close - rates[i].open);
      if(body <= 0.0)
         continue; // Doji: neutral, do not bias the denominator.

      double upper_wick = rates[i].high - MathMax(rates[i].open, rates[i].close);
      double lower_wick = MathMin(rates[i].open, rates[i].close) - rates[i].low;
      double body_ratio = body / range_p;

      if(rates[i].close > rates[i].open)
      {
         double contribution = body_ratio * (1.0 - upper_wick / range_p);
         buy += contribution;
         sell -= contribution;
         bull_out++;
      }
      else
      {
         double contribution = body_ratio * (1.0 - lower_wick / range_p);
         sell += contribution;
         buy -= contribution;
         bear_out++;
      }
   }

   int total = bull_out + bear_out;
   if(total > 0)
   {
      buy_out = (buy / (double)total + 1.0) / 2.0;
      sell_out = (sell / (double)total + 1.0) / 2.0;
   }

   buy_out = MathMax(0.0, MathMin(1.0, buy_out));
   sell_out = MathMax(0.0, MathMin(1.0, sell_out));
}

bool LoadOpeningRange(datetime ny_now, bool log_result)
{
   datetime day_start = NYDate(ny_now);
   MqlDateTime d;
   TimeToStruct(day_start, d);
   datetime range_start_ny = MakeTime(d.year, d.mon, d.day, InpRangeHourNY, InpRangeMinuteNY);
   datetime range_end_ny = (datetime)((long)range_start_ny + 15 * 60);

   // The 09:30 M15 bar is only usable once it is closed at 09:45 NY.
   if((long)ny_now < (long)range_end_ny)
      return false;

   datetime range_start_server = NYToServer(range_start_ny);
   datetime range_end_server = (datetime)((long)range_start_server + 15 * 60 - 1);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, range_start_server, range_end_server, rates);
   for(int i = 0; i < copied; i++)
   {
      if((datetime)rates[i].time != range_start_server)
         continue;
      if(rates[i].high <= rates[i].low)
         return false;

      g_high = rates[i].high;
      g_low = rates[i].low;
      g_range_ready = true;
      if(log_result)
         Print("PRESSURE range fixed: high=", DoubleToString(g_high, _Digits),
               " low=", DoubleToString(g_low, _Digits),
               " bar=", TimeToString(range_start_ny, TIME_DATE|TIME_MINUTES), " NY");
      return true;
   }

   // Fallback after a restart: locate the exact bar by shift.
   int shift = iBarShift(_Symbol, PERIOD_M15, range_start_server, false);
   if(shift >= 0)
   {
      MqlRates one[];
      if(CopyRates(_Symbol, PERIOD_M15, shift, 1, one) == 1)
      {
         if((datetime)one[0].time == range_start_server && one[0].high > one[0].low)
         {
            g_high = one[0].high;
            g_low = one[0].low;
            g_range_ready = true;
            if(log_result)
               Print("PRESSURE range fixed: high=", DoubleToString(g_high, _Digits),
                     " low=", DoubleToString(g_low, _Digits),
                     " bar=", TimeToString(range_start_ny, TIME_DATE|TIME_MINUTES), " NY");
            return true;
         }
      }
   }

   return false;
}

int CountTradesToday(datetime ny_now)
{
   datetime day_start = NYDate(ny_now);
   datetime from = NYToServer(day_start);
   datetime to = ServerNow();
   if((long)to <= (long)from)
      return 0;
   if(!HistorySelect(from, to))
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

bool EnterTrade(ENUM_ORDER_TYPE side, double stop, double target)
{
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      Print("PRESSURE entry refused: terminal trading disabled");
      return false;
   }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      Print("PRESSURE entry refused: expert trading disabled");
      return false;
   }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      Print("PRESSURE entry refused: account expert trading disabled");
      return false;
   }

   ENUM_SYMBOL_TRADE_MODE trade_mode =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(trade_mode != SYMBOL_TRADE_MODE_FULL)
   {
      Print("PRESSURE entry refused: symbol trade mode=", (int)trade_mode);
      return false;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
      return false;

   double entry = (side == ORDER_TYPE_BUY) ? ask : bid;
   stop = NormalizePrice(stop);
   target = NormalizePrice(target);

   if(side == ORDER_TYPE_BUY)
   {
      if(stop >= entry || target <= entry)
      {
         Print("PRESSURE entry refused: invalid BUY levels entry=", DoubleToString(entry, _Digits),
               " sl=", DoubleToString(stop, _Digits), " tp=", DoubleToString(target, _Digits));
         return false;
      }
   }
   else
   {
      if(stop <= entry || target >= entry)
      {
         Print("PRESSURE entry refused: invalid SELL levels entry=", DoubleToString(entry, _Digits),
               " sl=", DoubleToString(stop, _Digits), " tp=", DoubleToString(target, _Digits));
         return false;
      }
   }

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tick_value <= 0.0)
      tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0.0 || tick_value <= 0.0)
   {
      Print("PRESSURE entry refused: tick_size=", tick_size, " tick_value_loss=", tick_value);
      return false;
   }

   double stop_distance = (side == ORDER_TYPE_BUY) ? (entry - stop) : (stop - entry);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double min_distance = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   if(stop_distance < min_distance)
   {
      Print("PRESSURE entry refused: stop_distance=", DoubleToString(stop_distance, _Digits),
            " < stops_level=", DoubleToString(min_distance, _Digits));
      return false;
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_money = equity * InpRiskPct / 100.0;
   if(equity <= 0.0 || risk_money <= 0.0)
   {
      Print("PRESSURE entry refused: invalid equity=", equity, " risk_money=", risk_money);
      return false;
   }

   double loss_per_lot = (stop_distance / tick_size) * tick_value;
   if(loss_per_lot <= 0.0)
      return false;

   double raw_lots = risk_money / loss_per_lot;
   double lots = NormalizeVolume(raw_lots);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = MathMin(10.0, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
   if(lots > max_lot)
   {
      Print("PRESSURE lot capped: raw=", DoubleToString(raw_lots, 4),
            " cap=", DoubleToString(max_lot, 2));
      lots = NormalizeVolume(max_lot);
   }
   if(lots < min_lot)
   {
      Print("PRESSURE entry refused: lots=", lots, " < min_lot=", min_lot);
      return false;
   }

   double estimated_loss = loss_per_lot * lots;
   if(estimated_loss > risk_money * 1.05)
   {
      Print("PRESSURE entry refused: min volume risk=", DoubleToString(estimated_loss, 2),
            " > target=", DoubleToString(risk_money, 2));
      return false;
   }

   double margin = 0.0;
   if(!OrderCalcMargin(side, _Symbol, lots, entry, margin))
   {
      Print("PRESSURE entry refused: OrderCalcMargin failed");
      return false;
   }
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(margin > free_margin * 0.8)
   {
      Print("PRESSURE entry refused: margin=", DoubleToString(margin, 2),
            " free=", DoubleToString(free_margin, 2));
      return false;
   }

   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = _Symbol;
   req.volume = lots;
   req.type = side;
   req.price = NormalizePrice(entry);
   req.sl = stop;
   req.tp = target;
   req.deviation = InpSlippagePoints;
   req.magic = InpMagic;
   req.comment = "PRESSURE entry";
   req.type_filling = FillingMode();

   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("PRESSURE entry failed retcode=", res.retcode,
            " volume=", DoubleToString(lots, 2),
            " price=", DoubleToString(req.price, _Digits),
            " comment=", res.comment);
      return false;
   }

   double fill = (res.price > 0.0) ? res.price : req.price;
   double real_risk = (side == ORDER_TYPE_BUY)
      ? ((fill - stop) / tick_size) * tick_value * lots
      : ((stop - fill) / tick_size) * tick_value * lots;
   Print("PRESSURE entry ", (side == ORDER_TYPE_BUY ? "BUY " : "SELL "),
         "vol=", DoubleToString(lots, 2),
         " price=", DoubleToString(fill, _Digits),
         " sl=", DoubleToString(stop, _Digits),
         " tp=", DoubleToString(target, _Digits),
         " risk_target=", DoubleToString(risk_money, 2),
         " risk_est=", DoubleToString(real_risk, 2),
         " stop_dist=", DoubleToString(stop_distance, _Digits),
         " equity=", DoubleToString(equity, 2));
   return true;
}

bool ClosePosition(ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
   {
      Print("PRESSURE close failed: ticket not found=", ticket);
      return false;
   }

   ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   double volume = PositionGetDouble(POSITION_VOLUME);
   double price = (pos_type == POSITION_TYPE_BUY)
      ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
      : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(volume <= 0.0 || price <= 0.0)
      return false;

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
   req.type = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.price = NormalizePrice(price);
   req.comment = "PRESSURE close";
   req.type_filling = FillingMode();

   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("PRESSURE close failed retcode=", res.retcode,
            " ticket=", ticket, " comment=", res.comment);
      return false;
   }

   double fill = (res.price > 0.0) ? res.price : req.price;
   Print("PRESSURE close ticket=", ticket,
         " vol=", DoubleToString(volume, 2),
         " price=", DoubleToString(fill, _Digits));
   return true;
}

void ResetDay(datetime day)
{
   g_day = day;
   g_high = 0.0;
   g_low = 0.0;
   g_range_ready = false;
   g_trades_today = 0;
   g_last_skip_bar = 0;
   g_last_skip_side = "";
   g_last_skip_reason = "";
   g_last_range_warn_bar = 0;
}

void LogSkippedSignal(string side, double pressure, double threshold,
                      double bid, double ask, double spread, string reason)
{
   datetime bar = iTime(_Symbol, PERIOD_M15, 0);
   if(bar == g_last_skip_bar && side == g_last_skip_side && reason == g_last_skip_reason)
      return;
   g_last_skip_bar = bar;
   g_last_skip_side = side;
   g_last_skip_reason = reason;
   Print("PRESSURE signal skipped ", side, " reason=", reason,
         " pressure=", DoubleToString(pressure, 4),
         " threshold=", DoubleToString(threshold, 2),
         " bid=", DoubleToString(bid, _Digits),
         " ask=", DoubleToString(ask, _Digits),
         " spread=", DoubleToString(spread, _Digits),
         " range=", DoubleToString(g_low, _Digits), "-", DoubleToString(g_high, _Digits));
}

int OnInit()
{
   g_initial_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   datetime server_now = ServerNow();
   datetime ny_now = ServerToNY(server_now);
   g_day = NYDate(ny_now);
   g_trades_today = CountTradesToday(ny_now);

   int ny_offset = IsDSTUTC(ServerToUTC(server_now)) ? 4 : 5;
   Print("PRESSURE ORB initialized, equity=", DoubleToString(g_initial_equity, 2),
         " symbol=", _Symbol,
         " server_gmt_offset=", InpServerGMTOffsetHours,
         " ny_offset=", ny_offset);
   Print("Trading hours: ", InpRangeHourNY, ":", InpRangeMinuteNY,
         " NY to ", InpCloseHourNY, ":", InpCloseMinuteNY, " NY");
   Print("PRESSURE trades today restored=", g_trades_today);

   LoadOpeningRange(ny_now, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
}

void OnTick()
{
   datetime server_now = ServerNow();
   datetime ny_now = ServerToNY(server_now);
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
      pos_ticket = (ulong)PositionGetInteger(POSITION_TICKET);
      break;
   }

   int range_start_min = InpRangeHourNY * 60 + InpRangeMinuteNY;
   int range_end_min = range_start_min + 15;
   int current_min = nyd.hour * 60 + nyd.min;
   int close_min = InpCloseHourNY * 60 + InpCloseMinuteNY;
   int buffer = (nyd.day_of_week == 5) ? InpFridayCloseBufferMinutes : InpCloseBufferMinutes;

   // The opening range is only the completed 09:30-09:45 M15 bar.
   if(!g_range_ready && current_min >= range_end_min)
   {
      if(!LoadOpeningRange(ny_now, true))
      {
         datetime bar = iTime(_Symbol, PERIOD_M15, 0);
         if(bar != g_last_range_warn_bar)
         {
            g_last_range_warn_bar = bar;
            Print("PRESSURE range unavailable for ", TimeToString(ny_now, TIME_DATE|TIME_MINUTES),
                  " NY - waiting for the 09:30 M15 bar");
         }
      }
   }

   if(has_position && current_min >= close_min - buffer)
   {
      ClosePosition(pos_ticket);
      return;
   }

   if(current_min < range_end_min || current_min >= close_min - buffer)
      return;
   if(has_position || !g_range_ready)
      return;
   if(g_trades_today >= InpMaxTradesPerDay)
      return;
   if(InpOneTradePerDay && g_trades_today >= 1)
      return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0.0 || ask <= 0.0)
      return;

   bool buy_break = bid > g_high;
   bool sell_break = ask < g_low;
   if(!buy_break && !sell_break)
      return;

   double buy_pressure = 0.5;
   double sell_pressure = 0.5;
   int bullish_count = 0;
   int bearish_count = 0;
   CalculatePressure(InpMinPressureBars, buy_pressure, sell_pressure,
                     bullish_count, bearish_count);

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = ask - bid;
   string side = buy_break ? "BUY" : "SELL";
   double pressure = buy_break ? buy_pressure : sell_pressure;
   double threshold = buy_break ? InpBuyPressureMin : InpSellPressureMin;

   if(spread > InpMaxSpreadPoints * point)
   {
      LogSkippedSignal(side, pressure, threshold, bid, ask, spread, "spread");
      return;
   }

   if(buy_break)
   {
      if(buy_pressure < InpBuyPressureMin)
      {
         LogSkippedSignal("BUY", buy_pressure, InpBuyPressureMin, bid, ask, spread, "pressure");
         return;
      }

      double stop = g_low;
      double target = ask + (ask - stop) * InpTargetR;
      if(EnterTrade(ORDER_TYPE_BUY, stop, target))
      {
         g_trades_today++;
         Print("PRESSURE signal BUY range high=", DoubleToString(g_high, _Digits),
               " low=", DoubleToString(g_low, _Digits),
               " buy_pressure=", DoubleToString(buy_pressure, 4),
               " sell_pressure=", DoubleToString(sell_pressure, 4),
               " bars=", InpMinPressureBars,
               " bullish=", bullish_count, " bearish=", bearish_count);
      }
   }
   else if(sell_break)
   {
      if(sell_pressure < InpSellPressureMin)
      {
         LogSkippedSignal("SELL", sell_pressure, InpSellPressureMin, bid, ask, spread, "pressure");
         return;
      }

      double stop = g_high;
      double target = bid - (stop - bid) * InpTargetR;
      if(EnterTrade(ORDER_TYPE_SELL, stop, target))
      {
         g_trades_today++;
         Print("PRESSURE signal SELL range high=", DoubleToString(g_high, _Digits),
               " low=", DoubleToString(g_low, _Digits),
               " buy_pressure=", DoubleToString(buy_pressure, 4),
               " sell_pressure=", DoubleToString(sell_pressure, 4),
               " bars=", InpMinPressureBars,
               " bullish=", bullish_count, " bearish=", bearish_count);
      }
   }
}
