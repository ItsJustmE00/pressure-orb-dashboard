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
MOROCCO = ZoneInfo("Africa/Casablanca")
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
            global _CONNECTED, _LAST_ERROR
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
        key=lambda item: item.name,
    )
    # Seven days covers a terminal started long before the current session.
    return (mql[0] if mql else None, term[-7:])


def _read_logs():
    mql_log, _ = _latest_logs()
    return _tail(mql_log, 600)


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


def _cfg_int(config, key, default):
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _next_session_label(now_ny, hour, minute):
    candidate = now_ny + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return f"{_WEEKDAYS[candidate.weekday()].capitalize()} {hour:02d}:{minute:02d} NY"


def _market(symbol_tick, config=None):
    config = config or {}
    now_ny = datetime.now(NY)
    now_morocco = datetime.now(MOROCCO)
    weekday = now_ny.weekday()

    range_hour = _cfg_int(config, "InpRangeHourNY", 9)
    range_minute = _cfg_int(config, "InpRangeMinuteNY", 30)
    close_hour = _cfg_int(config, "InpCloseHourNY", 23)
    close_minute = _cfg_int(config, "InpCloseMinuteNY", 0)
    close_buffer = _cfg_int(config, "InpCloseBufferMinutes", 5)
    friday_buffer = _cfg_int(config, "InpFridayCloseBufferMinutes", 10)
    server_offset = _cfg_int(config, "InpServerGMTOffsetHours", 0)

    range_start_dt = now_ny.replace(
        hour=range_hour, minute=range_minute, second=0, microsecond=0
    )
    range_end_dt = range_start_dt + timedelta(minutes=15)
    close_dt = now_ny.replace(
        hour=close_hour, minute=close_minute, second=0, microsecond=0
    )
    buffer = friday_buffer if weekday == 4 else close_buffer
    safety_close_dt = close_dt - timedelta(minutes=buffer)

    # CME equity-index maintenance break: 17:00-18:00 New York.
    break_start = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
    break_end = now_ny.replace(hour=18, minute=0, second=0, microsecond=0)
    daily_break = weekday < 5 and break_start <= now_ny < break_end

    if weekday >= 5:
        status = "weekend"
        phase = "weekend"
        label = "Marché fermé"
        next_event = _next_session_label(now_ny, range_hour, range_minute)
    elif now_ny < range_start_dt:
        status = "pre_open"
        phase = "pre_range"
        label = "Avant l'ouverture"
        next_event = f"{range_hour:02d}:{range_minute:02d} NY"
    elif now_ny < range_end_dt:
        status = "range"
        phase = "opening_range"
        label = "Opening range"
        next_event = f"{range_end_dt:%H:%M} NY"
    elif now_ny < safety_close_dt:
        status = "open"
        phase = "entry_window"
        label = "Fenêtre d'entrée (toute la journée)"
        next_event = f"{safety_close_dt:%H:%M} NY"
    elif now_ny < close_dt:
        status = "open"
        phase = "close_buffer"
        label = "Clôture de sécurité en cours"
        next_event = f"{close_dt:%H:%M} NY"
    else:
        status = "closed"
        phase = "after_close"
        label = "Après clôture"
        next_event = _next_session_label(now_ny, range_hour, range_minute)

    if daily_break and status == "open":
        label = "Pause quotidienne 17:00-18:00 NY"
        next_event = "18:00 NY"

    age = None
    tick_time = None
    if symbol_tick is not None and getattr(symbol_tick, "time", 0):
        # MT5 timestamps are in server time. Convert them to UTC first.
        tick_dt = datetime.fromtimestamp(symbol_tick.time, tz=UTC)
        if server_offset:
            tick_dt -= timedelta(hours=server_offset)
        tick_time = tick_dt.astimezone(NY).isoformat()
        age = max(0, int((datetime.now(UTC) - tick_dt).total_seconds()))

    if weekday >= 5 or status == "closed":
        feed_state = "closed"
    elif daily_break:
        feed_state = "paused"
    elif age is not None and age > 120:
        feed_state = "stale"
    else:
        feed_state = "live"

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
        "tick_stale": feed_state == "stale",
        "feed_state": feed_state,
        "is_weekend": weekday >= 5,
        "daily_break": daily_break,
        "range_start": f"{range_hour:02d}:{range_minute:02d}",
        "range_end": f"{range_end_dt:%H:%M}",
        "close_at": f"{close_dt:%H:%M}",
        "safety_close_at": f"{safety_close_dt:%H:%M}",
        "server_gmt_offset_hours": server_offset,
    }


def _ea_state(term_lines, config):
    load_pattern = re.compile(
        r"expert (ORB_Pressure|ORB_Portfolio) .* loaded successfully|"
        r"(ORB_Pressure|ORB_Portfolio) loaded|"
        r"inputs read from expert '(ORB_Pressure|ORB_Portfolio)'",
        re.IGNORECASE,
    )
    remove_pattern = re.compile(
        r"expert (ORB_Pressure|ORB_Portfolio) .* removed",
        re.IGNORECASE,
    )
    start_pattern = re.compile(
        r"MetaTrader 5 x64 build .* started",
        re.IGNORECASE,
    )
    last_start = -1
    last_load = -1
    last_remove = -1
    last = None
    for index, line in enumerate(term_lines):
        if start_pattern.search(line):
            last_start = index
        if load_pattern.search(line):
            last_load = index
            last = line
        elif remove_pattern.search(line):
            last_remove = index

    # A load is valid only if it happened after the last terminal start and
    # after the last removal. If the start line is older than the scanned
    # window (terminal up for days), a later load still proves the EA is here.
    if last_remove > last_load:
        loaded = False
    elif last_start >= 0:
        loaded = last_load > last_start
    else:
        loaded = last_load >= 0

    name = None
    if loaded and last:
        found = re.search(r"(ORB_Pressure|ORB_Portfolio)", last, re.IGNORECASE)
        name = found.group(1) if found else None
    return {
        "loaded": loaded,
        "name": name,
        "last_line": last if loaded else None,
        "preset": str(PRESET),
        "preset_exists": PRESET.exists(),
        "risk_pct": config.get("InpRiskPct"),
        "magic": config.get("InpMagic"),
    }


def _calculate_pressure(bars_count=3, server_offset=0):
    """Calculate buy/sell pressure from the last N closed M15 candles.

    The formula is identical to the EA: doji bars are neutral and excluded
    from the denominator, so they cannot drag the reading toward 0.5. The
    latest bar is used when it is already closed (e.g. after the CME break).
    """
    bars_count = max(1, int(bars_count))
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, bars_count + 2)
        if rates is None or len(rates) < bars_count + 1:
            return {
                "buy_pressure": 0.5,
                "sell_pressure": 0.5,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "body_avg": 0.0,
                "bars_count": bars_count,
                "candles": [],
            }

        now_server = datetime.now(UTC) + timedelta(hours=server_offset)
        last_bar_server = datetime.fromtimestamp(int(rates[-1][0]), tz=UTC)
        latest_closed = last_bar_server + timedelta(minutes=15) <= now_server
        if latest_closed:
            selected = list(rates[-bars_count:])
        else:
            selected = list(rates[-(bars_count + 1):-1])
        if len(selected) < bars_count:
            raise ValueError("pas assez de bougies M15 cloturees")

        buy_pressure = 0.0
        sell_pressure = 0.0
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        total_body = 0.0
        candles_data = []

        # Newest first, matching the EA series order and the dashboard labels.
        for rate in reversed(selected):
            open_p = float(rate[1])
            high = float(rate[2])
            low = float(rate[3])
            close = float(rate[4])
            bar_server = datetime.fromtimestamp(int(rate[0]), tz=UTC)
            bar_utc = bar_server - timedelta(hours=server_offset)

            body = abs(close - open_p)
            range_p = high - low
            if range_p <= 0:
                continue

            upper_wick = high - max(open_p, close)
            lower_wick = min(open_p, close) - low

            if body <= 0:
                neutral_count += 1
            elif close > open_p:
                buy_pressure += (body / range_p) * (1 - upper_wick / range_p)
                sell_pressure -= (body / range_p) * (1 - upper_wick / range_p)
                bullish_count += 1
                total_body += body
            else:
                sell_pressure += (body / range_p) * (1 - lower_wick / range_p)
                buy_pressure -= (body / range_p) * (1 - lower_wick / range_p)
                bearish_count += 1
                total_body += body

            candles_data.append(
                {
                    "time": bar_utc.isoformat(),
                    "time_ny": bar_utc.astimezone(NY).isoformat(),
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "close": close,
                    "body": body,
                    "range": range_p,
                    "upper_wick": upper_wick,
                    "lower_wick": lower_wick,
                    "neutral": body <= 0,
                }
            )

        total_bars = bullish_count + bearish_count
        if total_bars > 0:
            buy_pressure = (buy_pressure / total_bars + 1) / 2
            sell_pressure = (sell_pressure / total_bars + 1) / 2
            body_avg = total_body / total_bars
        else:
            buy_pressure = 0.5
            sell_pressure = 0.5
            body_avg = 0.0

        return {
            "buy_pressure": max(0.0, min(1.0, buy_pressure)),
            "sell_pressure": max(0.0, min(1.0, sell_pressure)),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "body_avg": body_avg,
            "bars_count": bars_count,
            "candles": candles_data,
        }
    except Exception:
        return {
            "buy_pressure": 0.0,
            "sell_pressure": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "body_avg": 0.0,
            "bars_count": bars_count,
            "candles": [],
        }


def _opening_range_state(config, now_ny=None):
    """Return the 09:30 NY M15 range and whether that bar is closed.

    Before 09:45 the bar is still forming; its high/low is exposed for display
    only and must never be used as a trading range.
    """
    config = config or {}
    now_ny = now_ny or datetime.now(NY)
    server_offset = _cfg_int(config, "InpServerGMTOffsetHours", 0)
    range_hour = _cfg_int(config, "InpRangeHourNY", 9)
    range_minute = _cfg_int(config, "InpRangeMinuteNY", 30)
    start_ny = now_ny.replace(
        hour=range_hour, minute=range_minute, second=0, microsecond=0
    )
    end_ny = start_ny + timedelta(minutes=15)

    state = {
        "high": None,
        "low": None,
        "complete": False,
        "status": "pending",
        "bar_time": None,
        "source": None,
        "range_start": start_ny.isoformat(),
        "range_end": end_ny.isoformat(),
    }

    if now_ny.weekday() >= 5:
        state["status"] = "weekend"
        return state
    if now_ny < start_ny:
        return state

    rates = None
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 400)
    except Exception:
        rates = None

    if rates is not None:
        for rate in rates:
            bar_server = datetime.fromtimestamp(int(rate[0]), tz=UTC)
            bar_utc = bar_server - timedelta(hours=server_offset)
            bar_ny = bar_utc.astimezone(NY)
            if bar_ny.replace(second=0, microsecond=0) != start_ny:
                continue
            state["high"] = float(rate[2])
            state["low"] = float(rate[3])
            state["bar_time"] = bar_utc.isoformat()
            state["source"] = "m15"
            state["complete"] = now_ny >= end_ny
            state["status"] = "complete" if state["complete"] else "forming"
            return state

    if now_ny < end_ny:
        state["status"] = "forming"
        return state

    # Fallback: read the range logged by the EA when M15 history is missing.
    mql_log, _ = _latest_logs()
    if mql_log is not None:
        try:
            log_age = time.time() - mql_log.stat().st_mtime
        except OSError:
            log_age = 10**9
        today_server = datetime.now(UTC).strftime("%Y%m%d") + ".log"
        date_tag = f"{start_ny.year:04d}.{start_ny.month:02d}.{start_ny.day:02d}"
        if log_age <= 36 * 3600:
            fixed_re = re.compile(
                r"PRESSURE range (?:fixed|restored):\s*high=([0-9.]+)\s+"
                r"low=([0-9.]+)(?:\s+bar=(\d{4}\.\d{2}\.\d{2}))?",
                re.IGNORECASE,
            )
            signal_re = re.compile(
                r"PRESSURE range high=([0-9.]+)\s+low=([0-9.]+)",
                re.IGNORECASE,
            )
            for line in reversed(_tail(mql_log, 600)):
                match = fixed_re.search(line)
                if match:
                    tag = match.group(3)
                    if tag is None or tag == date_tag:
                        state["high"] = float(match.group(1))
                        state["low"] = float(match.group(2))
                        state["complete"] = True
                        state["status"] = "complete"
                        state["bar_time"] = start_ny.isoformat()
                        state["source"] = "ea_log"
                        return state
                match = signal_re.search(line)
                if match and mql_log.name == today_server:
                    state["high"] = float(match.group(1))
                    state["low"] = float(match.group(2))
                    state["complete"] = True
                    state["status"] = "complete"
                    state["bar_time"] = start_ny.isoformat()
                    state["source"] = "ea_log"
                    return state

    state["status"] = "unavailable"
    return state


def _live_read():
    config = _read_config()
    server_offset = _cfg_int(config, "InpServerGMTOffsetHours", 0)
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
    
    # Calculate pressure from the last N closed M15 candles (preset-driven).
    pressure = _calculate_pressure(
        bars_count=_cfg_int(config, "InpMinPressureBars", 3),
        server_offset=server_offset,
    )

    # The ORB range is the completed 09:30 NY M15 bar. Before 09:45 the same
    # bar is exposed as "forming" for display only.
    range_state = _opening_range_state(config)
    pressure["range_high"] = range_state["high"]
    pressure["range_low"] = range_state["low"]
    pressure["range_complete"] = range_state["complete"]
    pressure["range_status"] = range_state["status"]
    pressure["range_bar_time"] = range_state["bar_time"]
    pressure["range_source"] = range_state["source"]

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
        deal_utc = datetime.fromtimestamp(deal_time, tz=UTC) - timedelta(
            hours=server_offset
        )
        deal_ny = deal_utc.astimezone(NY)
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

    # The EA counts DEAL_ENTRY_IN deals; mirror that exactly for the day cap.
    entries = sum(1 for row in today_deals if row.get("entry") == 0)

    # Aggregate exits by position so partial closes count as one trade.
    exit_groups = {}
    for row in today_deals:
        if row.get("entry") not in (1, 2, 3):
            continue
        key = row.get("position_id") or row.get("ticket")
        value = (
            float(row.get("profit") or 0)
            + float(row.get("swap") or 0)
            + float(row.get("commission") or 0)
        )
        exit_groups[key] = exit_groups.get(key, 0.0) + value

    wins = sum(1 for value in exit_groups.values() if value > 0)
    losses = sum(1 for value in exit_groups.values() if value < 0)
    realized = round(
        sum(
            float(row.get("profit") or 0)
            + float(row.get("swap") or 0)
            + float(row.get("commission") or 0)
            for row in today_deals
        ),
        2,
    )
    realized_closed = round(sum(exit_groups.values()), 2)
    commission_today = round(
        sum(float(row.get("commission") or 0) for row in today_deals), 2
    )
    swap_today = round(sum(float(row.get("swap") or 0) for row in today_deals), 2)

    spread = None
    if symbol_tick is not None:
        spread = round(float(symbol_tick.ask) - float(symbol_tick.bid), 4)

    mql_log, term_logs = _latest_logs()
    mql_lines = _tail(mql_log, 80)
    term_lines = []
    for term_log in term_logs:
        term_lines.extend(_tail(term_log, 800))
    display_lines = _tail(term_logs[-1], 800) if term_logs else []
    relevant = [
        line
        for line in display_lines
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
            "time": (
                _epoch_to_iso(symbol_tick.time - server_offset * 3600)
                if symbol_tick
                else None
            ),
        },
        "market": _market(symbol_tick, config),
        "ea": _ea_state(term_lines, config),
        "config": config,
        "positions": positions,
        "orders": orders,
        "today": {
            "deals": today_deals,
            "realized": realized,
            "realized_closed": realized_closed,
            "commission": commission_today,
            "swap": swap_today,
            "wins": wins,
            "losses": losses,
            "entries": entries,
            "closed": wins + losses,
            "count": entries,
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
        config = _read_config()
        return {
            "ok": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "error": _LAST_ERROR or "MT5 indisponible",
            "terminal_running": bool(_terminal_processes()),
            "processes": _terminal_processes(),
            "market": _market(None, config),
            "config": config,
            "ea": _ea_state([], config),
            "positions": [],
            "orders": [],
            "today": {
                "deals": [],
                "realized": 0,
                "realized_closed": 0,
                "commission": 0,
                "swap": 0,
                "wins": 0,
                "losses": 0,
                "entries": 0,
                "closed": 0,
                "count": 0,
            },
            "pressure": {
                "buy_pressure": 0.0,
                "sell_pressure": 0.0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "body_avg": 0.0,
                "bars_count": _cfg_int(config, "InpMinPressureBars", 3),
                "range_high": None,
                "range_low": None,
                "range_complete": False,
                "range_status": "unavailable",
                "range_bar_time": None,
                "range_source": None,
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
