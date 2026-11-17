#property strict
#property version "1.00"
#property description "Enregistreur DOM (order book) + ticks - demo/recherche uniquement"
#property description "Ecrit MQL5/Files/dom_records.csv - aucun ordre envoye"

input int InpMaxLevels = 10;        // niveaux de profondeur a enregistrer
input int InpFlushEveryMin = 1;     // flush du fichier toutes les N minutes

int g_handle = INVALID_HANDLE;
datetime g_last_flush = 0;
uint g_book_seq = 0;
uint g_tick_seq = 0;

int OnInit()
{
   g_handle = FileOpen("dom_records.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ';');
   if(g_handle == INVALID_HANDLE)
   {
      Print("DOM_Recorder: impossible d'ouvrir dom_records.csv, err=", GetLastError());
      return INIT_FAILED;
   }
   FileSeek(g_handle, 0, SEEK_END);
   if(FileTell(g_handle) == 0)
      FileWrite(g_handle, "seq", "kind", "time_utc", "ms", "data");
   Print("DOM_Recorder demarre sur ", _Symbol,
         " (profondeur max=", InpMaxLevels, ") - lecture seule");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_handle != INVALID_HANDLE)
      FileClose(g_handle);
   Print("DOM_Recorder arrete, rows book=", g_book_seq, " tick=", g_tick_seq);
}

void OnTimer()
{
   datetime now = TimeGMT();
   if(now - g_last_flush >= InpFlushEveryMin * 60)
   {
      FileFlush(g_handle);
      g_last_flush = now;
   }
}

void OnTick()
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;
   long flags = SymbolInfoInteger(_Symbol, SYMBOL_TICKS_BOOKDEPTH);
   string data = StringFormat("bid=%.2f;ask=%.2f;last=%.2f;vol=%d;bookdepth=%d",
                              t.bid, t.ask, t.last, (int)t.volume, (int)flags);
   g_tick_seq++;
   FileWrite(g_handle, (long)g_tick_seq, "TICK",
             TimeToString(t.time, TIME_DATE | TIME_SECONDS),
             (long)t.time_msc % 1000, data);
}

void OnBookEvent(const string &symbol)
{
   if(symbol != _Symbol)
      return;
   MqlBookInfo levels[];
   if(!MarketBookGet(_Symbol, levels))
      return;
   int n = MathMin(ArraySize(levels), InpMaxLevels);
   if(n <= 0)
      return;
   string bids = "", asks = "";
   for(int i = 0; i < n; i++)
   {
      string lvl = StringFormat("%.2fx%d", levels[i].price, (int)levels[i].volume);
      if(levels[i].type == BOOK_TYPE_SELL)
         asks += (asks == "" ? "" : "|") + lvl;
      else
         bids += (bids == "" ? "" : "|") + lvl;
   }
   g_book_seq++;
   FileWrite(g_handle, (long)g_book_seq, "BOOK",
             TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS), "",
             StringFormat("bids=%s;asks=%s", bids, asks));
}
