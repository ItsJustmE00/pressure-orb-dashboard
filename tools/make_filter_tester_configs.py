from pathlib import Path

out = Path("out_orb_portfolio_57k")

common = """[Tester]
Expert=ORB_Portfolio.ex5
Symbol={symbol}
Period=M15
Optimization=0
Model=4
FromDate=2026.01.01
ToDate=2026.09.15
ForwardMode=0
Deposit=57000
Currency=USD
Leverage=1:2000
ExecutionMode=0
OptimizationCriterion=0
Visual=0
UseLocal=1
UseRemote=0
UseCloud=0
Port={port}
Report={report}
ReplaceReport=1
ShutdownTerminal=1
[TesterInputs]
InpRiskPct={risk}||{risk}||0.100000||10.000000||N
InpTargetR=3.0||3.0||0.300000||30.000000||N
InpMagic=20261109||20261109||1||202611090||N
InpRangeHourNY=9||9||1||90||N
InpRangeMinuteNY=30||30||1||300||N
InpCloseHourNY=16||16||1||160||N
InpCloseMinuteNY=0||0||1||10||N
InpServerGMTOffsetHours=0||0||1||10||N
InpSlippagePoints=30||30||1||300||N
InpMaxSpreadPoints=500||0||0||0||N
InpOneTradePerDay=true||false||0||true||N
InpLongOnly={long_only}||false||0||true||N
InpUseTrendFilter={use_trend}||false||0||true||N
InpTrendMax={trend_max}||0.00425||0.001||0.100||N
InpUseRsiFilter={use_rsi}||false||0||true||N
InpRsiMin={rsi_min}||56.5||1.0||100.0||N
InpUseRangeRankFilter={use_range}||false||0||true||N
InpRangeRankMax={range_max}||0.20||0.01||1.00||N
"""

configs = {
    "tester_ustecm_trend.ini": dict(
        symbol="USTECm",
        port=3013,
        report=str((out / "mt5_ustecm_trend").resolve()),
        risk=1.5,
        long_only="true",
        use_trend="true",
        trend_max=0.0042500175354026,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend_3.ini": dict(
        symbol="USTECm",
        port=3014,
        report=str((out / "mt5_ustecm_trend_3").resolve()),
        risk=3.0,
        long_only="true",
        use_trend="true",
        trend_max=0.0042500175354026,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend2_25.ini": dict(
        symbol="USTECm",
        port=3018,
        report=str((out / "mt5_ustecm_trend2_25").resolve()),
        risk=2.5,
        long_only="true",
        use_trend="true",
        trend_max=0.002,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend6_25.ini": dict(
        symbol="USTECm",
        port=3019,
        report=str((out / "mt5_ustecm_trend6_25").resolve()),
        risk=2.5,
        long_only="true",
        use_trend="true",
        trend_max=0.006,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend8_25.ini": dict(
        symbol="USTECm",
        port=3020,
        report=str((out / "mt5_ustecm_trend8_25").resolve()),
        risk=2.5,
        long_only="true",
        use_trend="true",
        trend_max=0.008,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend0_25.ini": dict(
        symbol="USTECm",
        port=3017,
        report=str((out / "mt5_ustecm_trend0_25").resolve()),
        risk=2.5,
        long_only="true",
        use_trend="true",
        trend_max=0.0,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_trend_25.ini": dict(
        symbol="USTECm",
        port=3016,
        report=str((out / "mt5_ustecm_trend_25").resolve()),
        risk=2.5,
        long_only="true",
        use_trend="true",
        trend_max=0.0042500175354026,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_filtered_3.ini": dict(
        symbol="USTECm",
        port=3015,
        report=str((out / "mt5_ustecm_filtered_3").resolve()),
        risk=3.0,
        long_only="true",
        use_trend="true",
        trend_max=0.0042500175354026,
        use_rsi="true",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_ustecm_filtered.ini": dict(
        symbol="USTECm",
        port=3011,
        report=str((out / "mt5_ustecm_filtered").resolve()),
        risk=1.5,
        long_only="true",
        use_trend="true",
        trend_max=0.0042500175354026,
        use_rsi="true",
        rsi_min=56.5194859038146,
        use_range="false",
        range_max=0.20,
    ),
    "tester_us30_filtered.ini": dict(
        symbol="US30m",
        port=3012,
        report=str((out / "mt5_us30_filtered").resolve()),
        risk=1.5,
        long_only="false",
        use_trend="false",
        trend_max=0.0042500175354026,
        use_rsi="false",
        rsi_min=56.5194859038146,
        use_range="true",
        range_max=0.1916666666666666,
    ),
}

for name, cfg in configs.items():
    text = common.format(**cfg)
    (out / name).write_text(text, encoding="utf-16", newline="\r\n")
    print(name, (out / name).stat().st_size)
