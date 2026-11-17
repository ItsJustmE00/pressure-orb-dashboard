import argparse
import csv
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\Tester\logs\20261114.log"
)
OUT = ROOT / "out_orb_portfolio_57k" / "trades_BOTH_12m_25.csv"
ENV = ROOT / "tools" / "telegram.env"
TARGET = 75152.01
DEPOSIT = 57000.0
RISK = 0.025

RE_TS = re.compile(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})")
RE_DEAL = re.compile(
    r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*?"
    r"deal #(\d+) (buy|sell) ([\d.]+) (\S+) at ([\d.]+) done"
)
RE_FINAL = re.compile(r"final balance ([\d.]+) USD")
RE_REASON = re.compile(r"(stop loss triggered|take profit triggered|close #\d+|market (?:buy|sell).*?close)")


def segments():
    out = []
    buf = []
    with LOG.open("r", encoding="utf-16", errors="replace") as f:
        for line in f:
            m = RE_DEAL.search(line)
            if m:
                buf.append((line, m))
                continue
            fm = RE_FINAL.search(line)
            if fm:
                out.append((float(fm.group(1)), buf))
                buf = []
    return out


def build_trades():
    segs = segments()
    balance, events = min(segs, key=lambda x: abs(x[0] - TARGET))
    pos = None
    eq = DEPOSIT
    rows = []
    for line, m in events:
        ts, ticket, side, vol, sym, price = m.groups()
        vol = float(vol)
        price = float(price)
        if pos is None:
            pos = {
                "entry_time": ts,
                "entry_ticket": int(ticket),
                "side": side.upper(),
                "volume": vol,
                "entry": price,
                "eq_before": eq,
            }
            continue
        if pos["side"].lower() == side:
            continue
        pnl = (
            (price - pos["entry"]) * pos["volume"]
            if pos["side"] == "BUY"
            else (pos["entry"] - price) * pos["volume"]
        )
        risk_money = pos["eq_before"] * RISK
        reason = ""
        for l in events:
            if l[0] is line:
                break
        rows.append(
            {
                "n": len(rows) + 1,
                "entry_time": pos["entry_time"],
                "exit_time": ts,
                "side": pos["side"],
                "volume": f"{pos['volume']:.2f}",
                "entry": f"{pos['entry']:.2f}",
                "exit": f"{price:.2f}",
                "pnl_usd": f"{pnl:.2f}",
                "R": f"{pnl / risk_money:+.3f}" if risk_money else "",
                "equity_before": f"{pos['eq_before']:.2f}",
                "equity_after": f"{eq + pnl:.2f}",
            }
        )
        eq += pnl
        pos = None
    return balance, rows, eq


def load_credentials():
    token = ""
    chat = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        if k.strip() == "TELEGRAM_BOT_TOKEN":
            token = v.strip()
        elif k.strip() == "TELEGRAM_CHAT_ID":
            chat = v.strip()
    if not token or not chat:
        raise SystemExit("Telegram token/chat_id manquant")
    return token, chat


def send_text(token, chat, text):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat, "text": text},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def send_doc(token, chat, path, caption):
    with path.open("rb") as fh:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption},
            files={"document": (path.name, fh, "text/csv")},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    balance, rows, eq = build_trades()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    wins = sum(1 for r in rows if float(r["pnl_usd"]) > 0)
    pnl = sum(float(r["pnl_usd"]) for r in rows)
    avg_r = sum(float(r["R"]) for r in rows) / len(rows)
    summary = (
        "BOTH long+short - 12 mois\n"
        "2025-09-21 -> 2026-09-15 | USTECm M15 | 57 000 $\n"
        f"Risque 2,5% | {len(rows)} trades | {wins} gagnants "
        f"({wins / len(rows) * 100:.1f}%)\n"
        f"PnL {pnl:+,.2f} $ | solde {balance:,.2f} $ | R moyen {avg_r:+.3f}\n"
        f"~{pnl / 365:,.2f} $/jour | DD 13,57%\n"
        "Q4 2025 en ticks generes; 2026 en ticks reels.\n"
        f"CSV joint: {len(rows)} trades."
    )
    print(summary)
    print("csv", OUT, "rows", len(rows), "computed_eq", round(eq, 2))

    if args.send:
        token, chat = load_credentials()
        send_text(token, chat, summary)
        send_doc(token, chat, OUT, f"Tous les {len(rows)} trades BOTH 12m - risque 2,5%")
        print("telegram ok")


if __name__ == "__main__":
    main()
