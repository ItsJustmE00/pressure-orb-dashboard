import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psutil

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
DATA_PATH = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)
PRESET = DATA_PATH / "MQL5" / "Presets" / "PRESSURE.set"
SYMBOL = "USTECm"
MAGIC = 20261117
NY = ZoneInfo("America/New_York")
UTC = timezone.utc

_LOCK = threading.RLock()
_CONNECTED = False
_LAST_ERROR = None
_LAST_ATTEMPT = 0.0
_LAST_SNAPSHOT = None
_LAST_SNAPSHOT_AT = 0.0

_WEEKDAYS = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]


def _terminal_processes():
    found = []
    target = str(TERMINAL).lower()
    for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
        try:
            info = proc.info
            if (info.get("name") or "").lower() != "terminal64.exe":
                continue
            exe = info.get("exe")
            if exe and str(Path(exe)).lower() != target:
                continue
            found.append(
                {
                    "pid": info.get("pid"),
                    "exe": exe,
                    "started": datetime.fromtimestamp(
                        info.get("create_time") or 0, tz=UTC
                    ).isoformat(),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return found


def _connect_locked():
    global _CONNECTED, _LAST_ERROR, _LAST_ATTEMPT
    if mt5 is None:
        _LAST_ERROR = "MetaTrader5 Python indisponible"
        return False
    if _CONNECTED:
        try:
            if mt5.terminal_info() is not None:
                return True
        except Exception:
            pass
        _CONNECTED = False
    if not _terminal_processes():
        _LAST_ERROR = "terminal64.exe n'est pas en cours d'exécution"
        return False
    now = time.monotonic()
    if now - _LAST_ATTEMPT < 2.0:
        return False
    _LAST_ATTEMPT = now
    try:
        ok = mt5.initialize(path=str(TERMINAL), timeout=5000)
    except Exception as exc:
        _LAST_ERROR = str(exc)
        return False
    if not ok:
        code, message = mt5.last_error()
        _LAST_ERROR = f"initialize a échoué ({code}) {message}"
        return False
    _CONNECTED = True
    _LAST_ERROR = None
    return True


def _call(fn):
    with _LOCK:
        if not _connect_locked():
            return None
        try:
            return fn()
        except Exception as exc:
            global _CONNECTED
            _CONNECTED = False
            _LAST_ERROR = str(exc)
            return None


def _safe_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _dict_from_trade(item):
    data = item._asdict() if hasattr(item, "_asdict") else dict(item)
    return {key: _safe_value(value) for key, value in data.items()}


def _epoch_to_iso(value):
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def _decode(raw):
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _tail(path, lines=120):
    try:
        if not path or not path.exists():
            return []
        text = _decode(path.read_bytes())
    except OSError:
        return []
    values = [line.rstrip() for line in text.splitlines() if line.strip()]
    return values[-lines:]


def _latest_logs():
    mql_dir = DATA_PATH / "MQL5" / "Logs"
    term_dir = DATA_PATH / "Logs"
    mql = sorted(
        mql_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True
    )
    term = sorted(
        [
            item
            for item in term_dir.glob("*.log")
            if re.fullmatch(r"\d{8}\.log", item.name)
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return (mql[0] if mql else None, term[0] if term else None)


def _read_config():
    values = {}
    try:
        text = PRESET.read_text(encoding="utf-16")
    except (OSError, UnicodeError):
        try:
            text = PRESET.read_text(encoding="utf-8")
        except OSError:
            text = ""
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() == "true":
            values[key] = True
        elif value.lower() == "false":
            values[key] = False
        else:
            try:
                values[key] = float(value) if "." in value else int(value)
            except ValueError:
                values[key] = value
    return values


def _market(symbol_tick):
    now_ny = datetime.now(NY)
    now_morocco = datetime.now(timezone(timedelta(hours=1)))  # GMT+1 (Maroc)
    weekday = now_ny.weekday()
    clock = now_ny.time()
    close_hour = 23  # Trade jusqu'à 23:00 NY
    close_minute = 0
    close_time = now_ny.replace(
        hour=close_hour, minute=close_minute, second=0, microsecond=0
    ).time()
    range_start = now_ny.replace(hour=9, minute=30, second=0, microsecond=0).time()
    range_end = now_ny.replace(hour=9, minute=45, second=0, microsecond=0).time()

    if weekday >= 5:
        status = "weekend"
        phase = "weekend"
        label = "Marché fermé"
        next_event = "Lundi 09:30 NY"
    elif clock < range_start:
        status = "pre_open"
        phase = "pre_range"
        label = "Avant l'ouverture"
        next_event = "09:30 NY"
    elif clock < range_end:
        status = "range"
        phase = "opening_range"
        label = "Opening range"
        next_event = "09:45 NY"
    elif clock < close_time:
        status = "open"
        phase = "entry_window"
        label = "Fenêtre d'entrée (toute la journée)"
        next_event = f"{close_time.strftime('%H:%M')} NY"
    else:
        status = "closed"
        phase = "after_close"
        label = "Après clôture"
        next_event = "Demain 09:30 NY"

    age = None
    tick_time = None
    if symbol_tick is not None and getattr(symbol_tick, "time", 0):
        tick_dt = datetime.fromtimestamp(symbol_tick.time, tz=UTC)
        tick_time = tick_dt.astimezone(NY).isoformat()
        age = max(0, int((datetime.now(UTC) - tick_dt).total_seconds()))

    return {
        "ny_time": now_ny.isoformat(),
        "ny_clock": now_ny.strftime("%H:%M:%S"),
        "ny_date": now_ny.strftime("%d/%m/%Y"),
        "morocco_time": now_morocco.isoformat(),
        "morocco_clock": now_morocco.strftime("%H:%M:%S"),
        "morocco_date": now_morocco.strftime("%d/%m/%Y"),
        "weekday": _WEEKDAYS[weekday],
        "status": status,
        "phase": phase,
        "label": label,
        "next_event": next_event,
        "tick_time": tick_time,
        "tick_age_sec": age,
        "is_weekend": weekday >= 5,
    }


def _ea_state(term_lines, config):
    pattern = re.compile(
        r"expert ORB_Portfolio .* loaded successfully|ORB_Portfolio loaded|"
        r"inputs read from expert 'ORB_Portfolio'",
        re.IGNORECASE,
    )
    matches = [line for line in term_lines if pattern.search(line)]
    last = matches[-1] if matches else None
    return {
        "loaded": bool(last),
        "last_line": last,
        "preset": str(PRESET),
        "preset_exists": PRESET.exists(),
        "risk_pct": config.get("InpRiskPct"),
        "magic": config.get("InpMagic"),
    }


def _calculate_pressure(bars_count=3):
    """Calculate buy/sell pressure from recent M15 candles"""
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, bars_count + 1)
        if rates is None or len(rates) < bars_count + 1:
            return {
                "buy_pressure": 0.0,
                "sell_pressure": 0.0,
                "bullish_count": 0,
                "bearish_count": 0,
                "body_avg": 0.0,
                "candles": []
            }
        
        buy_pressure = 0.0
        sell_pressure = 0.0
        bullish_count = 0
        bearish_count = 0
        total_body = 0.0
        candles_data = []
        
        for i in range(1, bars_count + 1):
            rate = rates[i]
            open_p = rate[1]
            high = rate[2]
            low = rate[3]
            close = rate[4]
            
            body = abs(close - open_p)
            range_p = high - low
            
            if range_p <= 0:
                continue
            
            upper_wick = high - max(open_p, close)
            lower_wick = min(open_p, close) - low
            
            if close > open_p:
                buy_pressure += (body / range_p) * (1 - upper_wick / range_p)
                bullish_count += 1
            else:
                buy_pressure -= (body / range_p) * (1 - lower_wick / range_p)
                bearish_count += 1
            
            if close < open_p:
                sell_pressure += (body / range_p) * (1 - lower_wick / range_p)
            else:
                sell_pressure -= (body / range_p) * (1 - upper_wick / range_p)
            
            total_body += body
            candles_data.append({
                "open": open_p,
                "high": high,
                "low": low,
                "close": close,
                "body": body,
                "range": range_p,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick
            })
        
        total_bars = bullish_count + bearish_count
        if total_bars > 0:
            buy_pressure = (buy_pressure / total_bars + 1) / 2
            sell_pressure = (sell_pressure / total_bars + 1) / 2
            body_avg = total_body / total_bars
        else:
            buy_pressure = 0.0
            sell_pressure = 0.0
            body_avg = 0.0
        
        return {
            "buy_pressure": max(0, min(1, buy_pressure)),
            "sell_pressure": max(0, min(1, sell_pressure)),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "body_avg": body_avg,
            "candles": candles_data
        }
    except Exception as e:
        return {
            "buy_pressure": 0.0,
            "sell_pressure": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "body_avg": 0.0,
            "candles": []
        }


def _live_read():
    account = mt5.account_info()
    terminal = mt5.terminal_info()
    if account is None or terminal is None:
        raise RuntimeError("compte ou terminal MT5 indisponible")

    symbol_tick = mt5.symbol_info_tick(SYMBOL)
    symbol_info = mt5.symbol_info(SYMBOL)
    positions_raw = mt5.positions_get() or ()
    orders_raw = mt5.orders_get() or ()

    now = datetime.now(UTC)
    history_from = now - timedelta(days=14)
    deals_raw = mt5.history_deals_get(history_from, now + timedelta(days=1)) or ()

    positions = []
    for item in positions_raw:
        row = _dict_from_trade(item)
        row["is_orb"] = row.get("magic") == MAGIC
        row["side"] = "BUY" if row.get("type") == 0 else "SELL"
        positions.append(row)
    
    # Calculate pressure from candles
    pressure = _calculate_pressure(bars_count=3)
    
    # Get range from EA logs if available
    range_high = None
    range_low = None
    try:
        logs = _read_logs()
        for line in reversed(logs):
            if "PRESSURE range high=" in line:
                import re
                match = re.search(r"high=([\d.]+)\s+low=([\d.]+)", line)
                if match:
                    range_high = float(match.group(1))
                    range_low = float(match.group(2))
                    break
    except:
        pass
    
    pressure["range_high"] = range_high
    pressure["range_low"] = range_low

    orders = []
    for item in orders_raw:
        row = _dict_from_trade(item)
        row["is_orb"] = row.get("magic") == MAGIC
        row["side"] = "BUY" if row.get("type") == 0 else "SELL"
        orders.append(row)

    today_ny = datetime.now(NY).date()
    today_deals = []
    for item in deals_raw:
        row = _dict_from_trade(item)
        if row.get("magic") != MAGIC:
            continue
        deal_time = row.get("time")
        if not deal_time:
            continue
        deal_ny = datetime.fromtimestamp(deal_time, tz=UTC).astimezone(NY)
        if deal_ny.date() != today_ny:
            continue
        row["time_ny"] = deal_ny.isoformat()
        row["side"] = "BUY" if row.get("type") == 0 else "SELL"
        row["entry_label"] = {
            0: "IN",
            1: "OUT",
            2: "INOUT",
            3: "OUT_BY",
        }.get(row.get("entry"), str(row.get("entry")))
        today_deals.append(row)

    realized = round(
        sum(
            float(row.get("profit") or 0)
            + float(row.get("swap") or 0)
            + float(row.get("commission") or 0)
            for row in today_deals
            if row.get("entry") in (1, 2, 3)
        ),
        2,
    )
    wins = sum(
        1
        for row in today_deals
        if row.get("entry") in (1, 2, 3)
        and (float(row.get("profit") or 0) > 0)
    )
    losses = sum(
        1
        for row in today_deals
        if row.get("entry") in (1, 2, 3)
        and (float(row.get("profit") or 0) < 0)
    )

    spread = None
    if symbol_tick is not None:
        spread = round(float(symbol_tick.ask) - float(symbol_tick.bid), 4)

    config = _read_config()
    mql_log, term_log = _latest_logs()
    mql_lines = _tail(mql_log, 80)
    term_lines = _tail(term_log, 800)
    relevant = [
        line
        for line in term_lines
        if re.search(
            r"ORB|expert|automated trading|Market closed|order|deal|position|"
            r"failed|error|trade",
            line,
            re.IGNORECASE,
        )
    ]
    logs = [{"source": "MQL5", "line": line} for line in mql_lines[-50:]]
    logs += [{"source": "Terminal", "line": line} for line in relevant[-40:]]

    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "terminal_running": True,
        "server": {
            "terminal_running": True,
            "processes": _terminal_processes(),
            "connected": bool(terminal.connected),
            "path": terminal.path,
            "data_path": terminal.data_path,
            "build": terminal.build,
            "trade_allowed": bool(terminal.trade_allowed),
            "ping_ms": terminal.ping_last,
            "error": _LAST_ERROR,
        },
        "account": {
            "login": account.login,
            "name": account.name,
            "server": account.server,
            "company": account.company,
            "currency": account.currency,
            "balance": account.balance,
            "equity": account.equity,
            "profit": account.profit,
            "margin": account.margin,
            "margin_free": account.margin_free,
            "margin_level": account.margin_level,
            "leverage": account.leverage,
            "trade_allowed": bool(account.trade_allowed),
            "trade_expert": bool(account.trade_expert),
        },
        "symbol": {
            "name": SYMBOL,
            "bid": symbol_tick.bid if symbol_tick else None,
            "ask": symbol_tick.ask if symbol_tick else None,
            "spread": spread,
            "point": symbol_info.point if symbol_info else None,
            "digits": symbol_info.digits if symbol_info else None,
            "trade_mode": symbol_info.trade_mode if symbol_info else None,
            "time": _epoch_to_iso(symbol_tick.time) if symbol_tick else None,
        },
        "market": _market(symbol_tick),
        "ea": _ea_state(term_lines, config),
        "config": config,
        "positions": positions,
        "orders": orders,
        "today": {
            "deals": today_deals,
            "realized": realized,
            "wins": wins,
            "losses": losses,
            "count": wins + losses,
        },
        "pressure": pressure,
        "logs": logs[-80:],
    }


def live_snapshot(force=False):
    global _LAST_SNAPSHOT, _LAST_SNAPSHOT_AT
    with _LOCK:
        if (
            not force
            and _LAST_SNAPSHOT is not None
            and time.monotonic() - _LAST_SNAPSHOT_AT < 2.0
        ):
            return _LAST_SNAPSHOT
    data = _call(_live_read)
    if data is None:
        return {
            "ok": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "error": _LAST_ERROR or "MT5 indisponible",
            "terminal_running": bool(_terminal_processes()),
            "processes": _terminal_processes(),
            "market": _market(None),
            "config": _read_config(),
            "positions": [],
            "orders": [],
            "pressure": {
                "buy_pressure": 0.0,
                "sell_pressure": 0.0,
                "bullish_count": 0,
                "bearish_count": 0,
                "body_avg": 0.0,
                "candles": []
            },
            "logs": [],
        }
    with _LOCK:
        _LAST_SNAPSHOT = data
        _LAST_SNAPSHOT_AT = time.monotonic()
    return data


def shutdown():
    global _CONNECTED
    with _LOCK:
        if mt5 is not None and _CONNECTED:
            try:
                mt5.shutdown()
            except Exception:
                pass
        _CONNECTED = False
