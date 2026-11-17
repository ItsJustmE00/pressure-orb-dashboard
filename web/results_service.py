import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import mistune

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "out_orb_portfolio_57k"
OOS = ROOT / "out_orb_both_oos"
RISK = ROOT / "out_orb_both_oos_risk"
DIRECT_RUNS = Path(__file__).resolve().parent / "data" / "direct_runs.json"
REPORT = PORTFOLIO / "report.md"
SUMMARY = PORTFOLIO / "summary.json"
OOS_SUMMARY = OOS / "summary.csv"
RISK_SUMMARY = RISK / "summary.csv"
OOS_METADATA = OOS / "metadata.json"
OOS_TRADES_05 = OOS / "trades_r0.005_c1.7_e1.csv"
DIRECT_TRADES_25 = PORTFOLIO / "trades_BOTH_12m_25.csv"

PERIOD_LABELS = {
    "is": "IS 2016-2021",
    "oos": "OOS 2022-2025",
    "recent": "12 mois récents",
    "y26": "2026",
    "full": "Full 2016-2026",
}


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize(row):
    return {
        "risk_pct": _float(row.get("risk_pct")),
        "cost_points": _float(row.get("cost_points")),
        "eod_bars_back": _int(row.get("eod_bars_back")),
        "period": row.get("period"),
        "trades": _int(row.get("trades")),
        "win_rate": round(_float(row.get("win_rate")) * 100, 2),
        "avg_r": round(_float(row.get("avg_r")), 4),
        "total_r": round(_float(row.get("total_r")), 2),
        "final": round(_float(row.get("final")), 2),
        "return_pct": round(_float(row.get("return_pct")) * 100, 2),
        "max_dd_pct": round(_float(row.get("max_dd_pct")) * 100, 2),
        "per_day": round(_float(row.get("per_day")), 2),
        "long_n": _int(row.get("long_n")),
        "short_n": _int(row.get("short_n")),
        "long_avg_r": round(_float(row.get("long_avg_r")), 4),
        "short_avg_r": round(_float(row.get("short_avg_r")), 4),
    }


def _rows_for(rows, risk, cost, eod):
    return [
        row
        for row in rows
        if row["risk_pct"] == risk
        and row["cost_points"] == cost
        and row["eod_bars_back"] == eod
    ]


def _find(rows, risk, cost, eod, period):
    for row in rows:
        if (
            row["risk_pct"] == risk
            and row["cost_points"] == cost
            and row["eod_bars_back"] == eod
            and row["period"] == period
        ):
            return row
    return None


def _labelled(rows):
    values = []
    for row in rows:
        item = dict(row)
        item["label"] = PERIOD_LABELS.get(row["period"], row["period"])
        values.append(item)
    return values


def _equity_curve(path, value_key, date_key, start=None, end=None):
    rows = _read_csv(path)
    points = []
    for row in rows:
        date = (row.get(date_key) or "")[:10]
        if start and date < start:
            continue
        if end and date >= end:
            continue
        value = _float(row.get(value_key), default=None)
        if value is None:
            continue
        points.append({"date": date, "value": round(value, 2)})
    if not points:
        return {"points": [], "return_pct": 0.0, "max_dd_pct": 0.0}
    peak = points[0]["value"]
    max_dd = 0.0
    for point in points:
        peak = max(peak, point["value"])
        if peak:
            max_dd = max(max_dd, (peak - point["value"]) / peak * 100)
    first = points[0]["value"]
    last = points[-1]["value"]
    return {
        "points": points,
        "return_pct": round((last / first - 1) * 100, 2) if first else 0.0,
        "max_dd_pct": round(max_dd, 2),
    }


def _curve_with_deposit(path, value_key, date_key):
    curve = _equity_curve(path, value_key, date_key)
    if curve["points"]:
        first_date = curve["points"][0]["date"]
        curve["points"].insert(0, {"date": first_date, "value": 57000.0})
        first = curve["points"][0]["value"]
        last = curve["points"][-1]["value"]
        peak = first
        max_dd = 0.0
        for point in curve["points"]:
            peak = max(peak, point["value"])
            if peak:
                max_dd = max(max_dd, (peak - point["value"]) / peak * 100)
        curve["return_pct"] = round((last / first - 1) * 100, 2)
        curve["max_dd_pct"] = round(max_dd, 2)
    return curve


def _recent_trades(path, start=None, limit=18):
    rows = _read_csv(path)
    selected = []
    for row in rows:
        date = (row.get("date") or row.get("entry_time") or "")[:10]
        if start and date < start:
            continue
        selected.append(
            {
                "date": date,
                "side": (row.get("side") or "").upper(),
                "entry": _float(row.get("entry")),
                "exit": _float(row.get("exit")),
                "reason": row.get("reason") or "",
                "r": round(_float(row.get("r_multiple") or row.get("R")), 3),
                "pnl": round(_float(row.get("pnl") or row.get("pnl_usd")), 2),
            }
        )
    return list(reversed(selected[-limit:]))


def _direct():
    if not DIRECT_RUNS.exists():
        return {"deposit": 57000.0, "runs": [], "notes": []}
    data = json.loads(DIRECT_RUNS.read_text(encoding="utf-8"))
    for run in data.get("runs", []):
        run["pnl"] = round(run.get("final", 0) - data.get("deposit", 0), 2)
    return data


def _historical():
    if not SUMMARY.exists():
        return {}
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def _metadata():
    if not OOS_METADATA.exists():
        return {}
    return json.loads(OOS_METADATA.read_text(encoding="utf-8"))


def _report_html():
    if not REPORT.exists():
        return ""
    return mistune.html(REPORT.read_text(encoding="utf-8"))


def results_payload():
    base_rows = [_normalize(row) for row in _read_csv(OOS_SUMMARY)]
    risk_rows = [_normalize(row) for row in _read_csv(RISK_SUMMARY)]

    primary = _find(base_rows, 0.5, 1.7, 1, "oos")
    primary_rows = _labelled(_rows_for(base_rows, 0.5, 1.7, 1))
    stress_rows = _labelled(_rows_for(base_rows, 0.5, 5.1, 1))
    risk_frontier = []
    for risk in (0.5, 0.75, 1.0, 1.5, 2.0, 2.5):
        row = _find(base_rows, risk, 1.7, 1, "oos") or _find(
            risk_rows, risk, 1.7, 1, "oos"
        )
        if row:
            risk_frontier.append(
                {
                    "risk_pct": risk,
                    "return_pct": row["return_pct"],
                    "max_dd_pct": row["max_dd_pct"],
                    "per_day": row["per_day"],
                    "trades": row["trades"],
                    "avg_r": row["avg_r"],
                }
            )

    curves = {
        "oos_05": {
            "label": "OOS 0,5 %",
            "sub": "2022-2025 · coût 1,7 · 194 trades",
            **_equity_curve(
                OOS_TRADES_05, "balance", "date", "2022-01-01", "2025-09-21"
            ),
        },
        "full_05": {
            "label": "Full 0,5 %",
            "sub": "2016-2026 · coût 1,7 · 481 trades",
            **_equity_curve(OOS_TRADES_05, "balance", "date"),
        },
        "direct_25": {
            "label": "12 mois 2,5 %",
            "sub": "Test direct MT5 · 62 trades",
            **_curve_with_deposit(DIRECT_TRADES_25, "equity_after", "entry_time"),
        },
    }

    calibration = {
        "sim_12m_pct": 8.47,
        "mt5_12m_pct": 6.07,
        "gap_pct": round(6.07 - 8.47, 2),
        "gap_r": -0.08,
        "text": (
            "La simulation bar-level surestime le 12 mois d'environ 2,4 points "
            "(~0,08R/trade). Après haircut, l'OOS 0,5 % reste positif vers "
            "+7-8 %, mais loin de 50 $/jour."
        ),
    }

    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deposit": 57000.0,
        "direct": _direct(),
        "historical": _historical(),
        "oos": {
            "primary": primary,
            "rows": primary_rows,
            "stress": stress_rows,
            "risk_frontier": risk_frontier,
        },
        "curves": curves,
        "recent_trades": _recent_trades(
            OOS_TRADES_05, start="2022-01-01", limit=18
        ),
        "calibration": calibration,
        "metadata": _metadata(),
        "notes": [
            "OOS 0,5 % : +15,72 %, DD 7,56 %, 194 trades, coût 1,7 point.",
            "Le 0,5 % est le seul réglage compatible avec un drawdown inférieur à 10 %.",
            "Aucun réglage testé ne donne 50 $/jour sous 10 % de DD sur ce seul instrument.",
            "Le warmup D1 du terminal fausse le début du test 12 mois ; la fenêtre 2026 est la plus fiable.",
        ],
    }


def report_html():
    return _report_html()
