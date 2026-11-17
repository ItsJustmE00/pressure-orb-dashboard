#property script_show_inputs

input string InpSymbol = "USTECm";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;
input string InpEAName = "ORB_Pressure";
input string InpPreset = "PRESSURE.set";

void OnStart()
{
   long chart_id = ChartOpen(InpSymbol, InpTimeframe);
   if(chart_id == 0)
   {
      Print("Failed to open chart for ", InpSymbol);
      return;
   }
   
   Print("Chart opened: ", chart_id, " for ", InpSymbol);
   
   // Wait for chart to be ready
   Sleep(1000);
   
   // Navigate to chart
   ChartSetInteger(chart_id, CHART_BRING_TO_FRONT, true);
   
   // Try to attach EA
   string ea_path = "MQL5\\Experts\\" + InpEAName + ".ex5";
   Print("Attempting to attach EA: ", ea_path);
   
   // Note: Direct EA attachment from script is limited in MT5
   // This script opens the chart and prepares it for manual EA attachment
   Print("Please manually attach ", InpEAName, " to this chart");
   Print("Load preset: ", InpPreset);
}
