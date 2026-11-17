import argparse
import re
from pathlib import Path

DEFAULT_LOGS = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\Tester\logs"
)
RE_DEAL = re.compile(r"deal #(\d+) (buy|sell) ([\d.]+) (\S+) at ([\d.]+) done")
RE_FINAL = re.compile(r"final balance ([\d.]+) USD")


def parse(log, target, risk, deposit):
    buf = []
    segments = []
    with log.open("r", encoding="utf-16", errors="replace") as f:
        for line in f:
            m = RE_DEAL.search(line)
            if m:
                buf.append(m.groups())
                continue
            fm = RE_FINAL.search(line)
            if fm:
                segments.append((float(fm.group(1)), buf))
                buf = []
    if not segments:
        raise SystemExit(f"no final balance in {log}")
    if target is None:
        balance, deals = segments[-1]
    else:
        balance, deals = min(segments, key=lambda x: abs(x[0] - target))
    print("target", balance, "deals", len(deals))
    pos = None
    eq = deposit
    peak = eq
    maxdd = 0.0
    rs = []
    wins = 0
    for ticket, side, vol, sym, price in deals:
        vol = float(vol)
        price = float(price)
        if pos is None:
            pos = {"side": side, "vol": vol, "price": price, "eq": eq}
            continue
        if pos["side"] == side:
            continue
        pnl = (
            (price - pos["price"]) * pos["vol"]
            if pos["side"] == "buy"
            else (pos["price"] - price) * pos["vol"]
        )
        risk_money = pos["eq"] * risk
        r = pnl / risk_money if risk_money > 0 else 0.0
        rs.append(r)
        eq += pnl
        peak = max(peak, eq)
        maxdd = max(maxdd, 1.0 - eq / peak)
        if pnl > 0:
            wins += 1
        pos = None
    print(f"closed={len(rs)} wins={wins} win_rate={wins/len(rs)*100:.1f}%")
    print(f"computed_end={eq:,.2f} actual_end={balance:,.2f} diff={balance-eq:,.2f}")
    print(f"sum_pnl={eq-deposit:,.2f} maxdd_closed={maxdd*100:.2f}%")
    print(
        f"avgR={sum(rs)/len(rs):+.3f} medR={sorted(rs)[len(rs)//2]:+.3f} "
        f"minR={min(rs):+.2f} maxR={max(rs):+.2f}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--target", type=float, default=None)
    ap.add_argument("--risk", type=float, default=0.03)
    ap.add_argument("--deposit", type=float, default=57000.0)
    args = ap.parse_args()
    log = args.log
    if log is None:
        log = max(DEFAULT_LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime)
    print("log", log)
    parse(log, args.target, args.risk, args.deposit)


if __name__ == "__main__":
    main()
