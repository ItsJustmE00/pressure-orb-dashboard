"""Send a Telegram rationale for every new ORB Pressure entry.

The notifier is read-only:
  * it polls the local Flask API (which already owns the single MT5 connection);
  * it reads the EA log to recover the pressure, spread, risk and refused
    signals at the entry;
  * it never opens MT5 and never touches the EA or the position.

Credentials are read from ``tools/telegram.env`` (TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID). The token is never printed or logged.

Usage:
    python tools/telegram_trade_notifier.py --once --dry-run --send-existing
    python tools/telegram_trade_notifier.py --once
    python tools/telegram_trade_notifier.py
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "tools" / "telegram.env"
STATE = ROOT / "logs" / "telegram_notifier_state.json"
LOG = ROOT / "logs" / "telegram_notifier.log"
DEFAULT_API = "http://127.0.0.1:8050"
DEFAULT_DATA = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)
FIRST_RUN_GRACE = timedelta(minutes=15)

RE_ENTRY = re.compile(
    r"PRESSURE entry (BUY|SELL) vol=([0-9.]+) (?:price|entry)=([0-9.]+) "
    r"sl=([0-9.]+) tp=([0-9.]+)(.*)"
)
RE_SKIP = re.compile(
    r"PRESSURE signal skipped (BUY|SELL) reason=pressure pressure=([0-9.]+)"
)
RE_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("ORB_API_BASE", DEFAULT_API))
    parser.add_argument("--data-dir", default=os.environ.get("ORB_MT5_DATA_DIR", str(DEFAULT_DATA)))
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send-existing", action="store_true")
    parser.add_argument("--force-position", default="")
    parser.add_argument("--no-state", action="store_true")
    return parser.parse_args()


def log(message):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    try:
        print(line)
    except (AttributeError, OSError, ValueError):
        pass
    try:
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            LOG.replace(LOG.with_suffix(".log.1"))
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def load_credentials():
    token = ""
    chat = ""
    if not ENV.exists():
        raise SystemExit(f"Fichier absent: {ENV}")
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key.strip() == "TELEGRAM_BOT_TOKEN":
            token = value.strip()
        elif key.strip() == "TELEGRAM_CHAT_ID":
            chat = value.strip()
    if not token or not chat:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID manquant")
    return token, chat


def load_state(path=STATE):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("seen"), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"seen": [], "updated_at": None}


def save_state(state, path=STATE):
    path.parent.mkdir(parents=True, exist_ok=True)
    state["seen"] = state["seen"][-500:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temp, path)


def fetch_live(api_base):
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/live",
        headers={"Cache-Control": "no-cache", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def send_telegram(token, chat, text):
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram refuse: {payload.get('description')}")
    return payload


def fr(value, digits=2):
    if value is None:
        return "n/d"
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def read_log_lines(path):
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


def log_time(line):
    parts = line.split("\t")
    if len(parts) < 3:
        return None
    match = RE_TIME.match(parts[2].strip())
    if not match:
        return None
    hour, minute, second = (int(value) for value in match.groups())
    return hour * 3600 + minute * 60 + second


def log_message(line):
    parts = line.split("\t")
    return parts[-1].strip() if parts else line.strip()


def data_dir_from_api(live, fallback):
    preset = (live.get("ea") or {}).get("preset") or ""
    if preset:
        candidate = Path(preset).parents[2]
        if candidate.exists():
            return candidate
    return Path(fallback)


def find_log_file(data_dir, deal_dt):
    base = Path(data_dir) / "MQL5" / "Logs"
    for offset in (0, -1, 1):
        date = (deal_dt + timedelta(days=offset)).strftime("%Y%m%d")
        path = base / f"{date}.log"
        if path.exists():
            return path
    return None


def parse_entry_context(data_dir, deal):
    """Recover pressure, risk, spread and refused signals from the EA log."""
    context = {
        "found": False,
        "log_price": None,
        "sl": None,
        "tp": None,
        "risk_est": None,
        "risk_target": None,
        "equity": None,
        "buy_pressure": None,
        "sell_pressure": None,
        "spread": None,
        "skips": 0,
    }
    try:
        deal_dt = datetime.fromtimestamp(int(deal.get("time", 0)), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return context
    path = find_log_file(data_dir, deal_dt)
    if path is None:
        return context
    try:
        lines = read_log_lines(path)
    except OSError:
        return context

    target = deal_dt.hour * 3600 + deal_dt.minute * 60 + deal_dt.second
    best = None
    for index, line in enumerate(lines):
        if "PRESSURE entry " not in line:
            continue
        seconds = log_time(line)
        if seconds is None:
            continue
        delta = abs(seconds - target)
        if delta <= 20 and (best is None or delta < best[0]):
            best = (delta, index, line)

    if best is None:
        return context

    _, index, line = best
    match = RE_ENTRY.search(log_message(line))
    if not match:
        return context
    side = match.group(1)
    context["found"] = True
    context["log_price"] = float(match.group(3))
    context["sl"] = float(match.group(4))
    context["tp"] = float(match.group(5))
    rest = match.group(6)
    for key, pattern in (
        ("risk_est", r"risk_est=([0-9.]+)"),
        ("risk_target", r"risk_target=([0-9.]+)"),
        ("equity", r"equity=([0-9.]+)"),
    ):
        found = re.search(pattern, rest)
        if found:
            context[key] = float(found.group(1))

    for neighbour in lines[max(0, index - 20) : index + 20]:
        message = log_message(neighbour)
        buy = re.search(r"buy_pressure=([0-9.]+)", message)
        sell = re.search(r"sell_pressure=([0-9.]+)", message)
        if buy:
            context["buy_pressure"] = float(buy.group(1))
        if sell:
            context["sell_pressure"] = float(sell.group(1))

    if context["buy_pressure"] is None and context["sell_pressure"] is not None:
        context["buy_pressure"] = 1.0 - context["sell_pressure"]
    if context["sell_pressure"] is None and context["buy_pressure"] is not None:
        context["sell_pressure"] = 1.0 - context["buy_pressure"]

    entry_seconds = log_time(line)
    for neighbour in reversed(lines[max(0, index - 240) : index + 1]):
        if "spread=" not in neighbour:
            continue
        seconds = log_time(neighbour)
        if seconds is None or entry_seconds is None:
            continue
        if abs(seconds - entry_seconds) <= 1800:
            found = re.search(r"spread=([0-9.]+)", log_message(neighbour))
            if found:
                context["spread"] = float(found.group(1))
                break

    start = 0
    for cursor in range(index - 1, -1, -1):
        if "PRESSURE entry " in lines[cursor]:
            start = cursor + 1
            break
    for neighbour in lines[start:index]:
        message = log_message(neighbour)
        match_skip = RE_SKIP.search(message)
        if match_skip and match_skip.group(1) == side:
            context["skips"] += 1

    return context


def build_message(live, deal, context):
    market = live.get("market") or {}
    account = live.get("account") or {}
    pressure = live.get("pressure") or {}
    config = live.get("config") or {}
    deals = (live.get("today") or {}).get("deals") or []
    positions = live.get("positions") or []

    side = (deal.get("side") or "").upper()
    volume = float(deal.get("volume") or 0.0)
    entry = float(deal.get("price") or 0.0)
    live_symbol = live.get("symbol")
    if isinstance(live_symbol, dict):
        live_symbol = live_symbol.get("name")
    symbol = deal.get("symbol") or live_symbol or ""
    magic = config.get("InpMagic") or (live.get("ea") or {}).get("magic")
    position_id = str(deal.get("position_id") or deal.get("ticket") or "")
    deal_time = datetime.fromtimestamp(int(deal.get("time", 0)), tz=timezone.utc)
    ny_time = deal.get("time_ny")
    try:
        ny_dt = datetime.fromisoformat(ny_time) if ny_time else None
    except ValueError:
        ny_dt = None

    position = None
    for item in positions:
        if str(item.get("ticket")) == position_id or str(item.get("identifier")) == position_id:
            position = item
            break

    sl = float(position.get("sl") or 0.0) if position else context.get("sl")
    tp = float(position.get("tp") or 0.0) if position else context.get("tp")
    if not sl:
        sl = context.get("sl")
    if not tp:
        tp = context.get("tp")

    range_low = pressure.get("range_low")
    range_high = pressure.get("range_high")
    width = None
    if range_low is not None and range_high is not None:
        width = float(range_high) - float(range_low)

    boundary = float(range_low if side == "SELL" else range_high) if width else None
    extension = abs(entry - boundary) if boundary is not None else None
    extension_ratio = extension / width if extension is not None and width else None
    stop_distance = abs(float(sl) - entry) if sl else None
    stop_ratio = stop_distance / width if stop_distance is not None and width else None

    risk_est = context.get("risk_est")
    if risk_est is None and stop_distance is not None:
        risk_est = stop_distance * volume
    equity = context.get("equity") or account.get("equity")
    risk_pct = (risk_est / float(equity) * 100.0) if risk_est and equity else None

    buy_pressure = context.get("buy_pressure")
    sell_pressure = context.get("sell_pressure")
    pressure_source = "à l'entrée"
    if buy_pressure is None or sell_pressure is None:
        buy_pressure = pressure.get("buy_pressure")
        sell_pressure = pressure.get("sell_pressure")
        pressure_source = "actuelle"
    threshold = config.get(
        "InpSellPressureMin" if side == "SELL" else "InpBuyPressureMin", 0.6
    )
    own_pressure = sell_pressure if side == "SELL" else buy_pressure
    other_pressure = buy_pressure if side == "SELL" else sell_pressure
    threshold = float(threshold or 0.6)
    max_trades = config.get("InpMaxTradesPerDay", 10)
    bars = config.get("InpMinPressureBars", 3)

    rank = 0
    if magic is not None and deal.get("time") is not None:
        for item in deals:
            if (
                item.get("entry_label") == "IN"
                and item.get("magic") == magic
                and item.get("symbol") == symbol
                and int(item.get("time") or 0) <= int(deal.get("time") or 0)
            ):
                rank += 1

    if position:
        profit = float(position.get("profit") or 0.0)
        now_ny = market.get("ny_time")
        now_ny_dt = None
        if now_ny:
            try:
                now_ny_dt = datetime.fromisoformat(now_ny)
            except ValueError:
                now_ny_dt = None
        stamp = f"{now_ny_dt:%H:%M}" if now_ny_dt else (f"{ny_dt:%H:%M}" if ny_dt else "--:--")
        status = f"ouvert | P/L {fr(profit)} $ à {stamp} NY"
    else:
        exit_deal = None
        for item in deals:
            if (
                item.get("entry_label") == "OUT"
                and str(item.get("position_id")) == position_id
            ):
                exit_deal = item
                break
        if exit_deal:
            exit_dt = datetime.fromtimestamp(
                int(exit_deal.get("time", 0)), tz=timezone.utc
            )
            status = (
                f"clôturé à {exit_dt:%H:%M} UTC | "
                f"P/L {fr(exit_deal.get('profit'))} $"
            )
        else:
            status = "ouvert (position absente du snapshot)"

    lines = [
        "📣 NOUVEAU TRADE — ORB Pressure",
        "",
        f"{side} {fr(volume)} {symbol} @ {fr(entry)}",
    ]
    if sl or tp:
        lines.append(f"SL {fr(sl)} | TP {fr(tp)}")
    stamp = f"{ny_dt:%d/%m %H:%M}" if ny_dt else deal_time.strftime("%d/%m %H:%M UTC")
    lines.extend(
        [
            f"Ticket {position_id} | {stamp} NY",
            "",
            f"Pourquoi {side} :",
        ]
    )
    if width:
        lines.append(f"• Range 09:30 NY : {fr(range_low)} – {fr(range_high)}")
    lines.append(
        f"• Pression {bars} bougies ({pressure_source}) : "
        f"{side} {fr(own_pressure, 4)} ≥ {fr(threshold)} "
        f"({('BUY' if side == 'SELL' else 'SELL')} {fr(other_pressure, 4)})"
    )
    if boundary is not None:
        position_text = "sous le bas" if side == "SELL" else "au-dessus du haut"
        direction_text = "baissière" if side == "SELL" else "haussière"
        lines.append(
            f"• Prix {position_text} du range → cassure {direction_text} confirmée"
        )
    if context.get("skips"):
        lines.append(
            f"• Refus avant entrée : {context['skips']} signaux sous {fr(threshold)}"
        )
    spread = context.get("spread")
    risk_text = f"risque {fr(risk_est)} $"
    if risk_pct is not None:
        risk_text += f" ({fr(risk_pct)} %)"
    if spread is not None:
        lines.append(f"• Spread {fr(spread)} pt | {risk_text}")
    else:
        lines.append(f"• {risk_text[0].upper() + risk_text[1:]}")

    alerts = []
    if extension_ratio is not None:
        if extension_ratio <= 0.05:
            label = "Cassure nette"
        elif extension_ratio <= 1.0:
            label = "Entrée décalée"
        else:
            label = "Entrée tardive"
        alerts.append(
            f"{label} : {fr(extension)} pts ({fr(extension_ratio)}× le range)"
        )
    if stop_ratio is not None:
        alerts.append(f"Stop : {fr(stop_distance)} pts ({fr(stop_ratio)}× le range)")
    if ny_dt and (ny_dt.hour * 60 + ny_dt.minute) >= 15 * 60:
        alerts.append("Entrée de fin de session (après 15:00 NY)")
    if risk_pct is not None and risk_pct > 0.55:
        alerts.append(f"Risque {fr(risk_pct)} % > cible 0,50 %")
    if not alerts:
        alerts.append("Conforme aux règles")

    lines.extend(["", "Audit :"])
    lines.extend(f"• {item}" for item in alerts)
    ordinal = "1er" if rank == 1 else f"{rank}e"
    lines.append(
        f"• {ordinal} trade du jour | position unique | max {max_trades}/jour"
    )
    lines.extend(
        [
            "",
            f"Statut : {status}",
            f"Compte démo {account.get('server', 'démo')} | magic {magic}",
        ]
    )
    return "\n".join(lines)


def handle_entry(live, deal, args, token, chat, state):
    position_id = str(deal.get("position_id") or deal.get("ticket") or "")
    context = parse_entry_context(
        data_dir_from_api(live, args.data_dir), deal
    )
    message = build_message(live, deal, context)
    if args.dry_run:
        log(f"DRY-RUN position={position_id}")
        print(message)
        print("-" * 60)
        return False
    send_telegram(token, chat, message)
    log(f"envoye position={position_id} chars={len(message)}")
    state["seen"].append(position_id)
    return True


def poll_once(args, token, chat, state):
    live = fetch_live(args.api)
    if not live.get("ok"):
        log(f"API indisponible: {live.get('error', 'ok=false')}")
        return False

    config = live.get("config") or {}
    magic = config.get("InpMagic") or (live.get("ea") or {}).get("magic")
    symbol = live.get("symbol")
    if isinstance(symbol, dict):
        symbol = symbol.get("name")
    deals = (live.get("today") or {}).get("deals") or []
    seen = set(str(item) for item in state.get("seen", []))
    first_run = not STATE.exists() and not args.no_state
    changed = False

    entries = [
        deal
        for deal in deals
        if deal.get("entry_label") == "IN"
        and (magic is None or deal.get("magic") == magic)
        and (symbol is None or deal.get("symbol") == symbol)
    ]
    entries.sort(key=lambda item: int(item.get("time") or 0))

    now = datetime.now(timezone.utc)
    for deal in entries:
        position_id = str(deal.get("position_id") or deal.get("ticket") or "")
        if not position_id:
            continue
        forced = args.force_position and position_id == args.force_position
        if position_id in seen and not forced:
            continue
        if first_run and not args.send_existing and not forced:
            deal_dt = datetime.fromtimestamp(
                int(deal.get("time", 0)), tz=timezone.utc
            )
            if now - deal_dt > FIRST_RUN_GRACE:
                state["seen"].append(position_id)
                changed = True
                log(f"amorcage position={position_id} (ancien trade)")
                continue
        try:
            if handle_entry(live, deal, args, token, chat, state):
                changed = True
                seen.add(position_id)
        except (urllib.error.URLError, RuntimeError, OSError) as exc:
            log(f"ERREUR envoi position={position_id}: {exc}")

    if changed and not args.dry_run and not args.no_state:
        save_state(state)
    return changed


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    args = parse_args()
    token, chat = load_credentials()
    state = load_state()
    if args.once:
        poll_once(args, token, chat, state)
        return
    log("notifier demarre")
    while True:
        try:
            poll_once(args, token, chat, state)
        except KeyboardInterrupt:
            log("notifier arrete")
            return
        except Exception as exc:  # keep the notifier alive
            log(f"ERREUR boucle: {exc}")
        time.sleep(max(2.0, args.interval))


if __name__ == "__main__":
    main()
