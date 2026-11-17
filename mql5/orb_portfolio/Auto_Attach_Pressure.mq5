#property script_show_inputs

input string InpSymbol = "USTECm";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;

void OnStart()
{
   Print("========================================");
   Print("AUTO ATTACH PRESSURE EA");
   Print("========================================");
   
   // Create new chart
   Print("Creating chart for ", InpSymbol, " M15");
   long chart_id = ChartOpen(InpSymbol, InpTimeframe);
   
   if(chart_id == 0)
   {
      Print("ERROR: Failed to open chart for ", InpSymbol);
      Print("Please open USTECm M15 manually");
      return;
   }
   
   Print("Chart opened successfully: ", chart_id);
   Sleep(2000);
   
   // Redraw chart
   ChartRedraw(chart_id);
   
   Print("========================================");
   Print("NEXT STEPS:");
   Print("1. In MT5 Navigator, go to Experts folder");
   Print("2. Find ORB_Pressure.ex5");
   Print("3. Drag it to this chart");
   Print("4. Right-click EA -> Properties -> Load PRESSURE.set");
   Print("5. Click 'Allow live trading'");
   Print("6. Enable 'Algo Trading' in toolbar");
   Print("========================================");
}
