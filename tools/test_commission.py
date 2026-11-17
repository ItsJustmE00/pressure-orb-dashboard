"""Test de commission empirique sur le compte Raw Spread USTEC.

Connexion au compte 474927957 (Exness-MT5Trial15), puis :
1. mesure du spread raw live
2. si le marche est ouvert : 1 trade test 0.05 lot achete + ferme
3. lecture de la commission reelle dans l'historique des deals
4. verdict : scalping viable ou mort

Usage : C:\\Python314\\python.exe tools\\test_commission.py --password XXXX
"""
import argparse
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5

LOGIN = 474927957
SERVER = "Exness-MT5Trial15"
SYMBOL = "USTECr"


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", required=True)
    ap.add_argument("--volume", type=float, default=0.05)
    ap.add_argument("--wait-open", action="store_true",
                    help="attendre l'ouverture du marche si ferme")
    args = ap.parse_args()

    if not mt5.initialize(login=LOGIN, password=args.password, server=SERVER):
        log(f"echec connexion : {mt5.last_error()}")
        return 1
    acc = mt5.account_info()
    log(f"connecte : login={acc.login} server={acc.server} "
        f"balance={acc.balance} type={acc.trade_mode}")

    if not mt5.symbol_select(SYMBOL, True):
        log(f"symbole {SYMBOL} indisponible : {mt5.last_error()}")
        return 1
    info = mt5.symbol_info(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)
    spread = (tick.ask - tick.bid) / info.point
    log(f"spread raw actuel : {spread:.2f} pts "
        f"(bid={tick.bid} ask={tick.ask} point={info.point})")
    log(f"volume min : {info.volume_min}  tick value : {info.trade_tick_value}")

    def market_open():
        t = mt5.symbol_info_tick(SYMBOL)
        if t is None:
            return False
        age = time.time() - t.time
        return age < 120

    if not market_open():
        if not args.wait_open:
            log("marche FERME -> pas de trade test possible maintenant. "
                "Relancer avec --wait-open apres la reouverture.")
            mt5.shutdown()
            return 0
        log("attente ouverture du marche...")
        while not market_open():
            time.sleep(30)
        log("marche ouvert !")

    # rafraichi le spread a l'ouverture
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.symbol_info(SYMBOL)
    spread = (tick.ask - tick.bid) / info.point
    log(f"spread a l'ouverture : {spread:.2f} pts")

    # trade test : achat 0.05 lot, fermeture immediate
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": args.volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "deviation": 50,
        "magic": 999001,
        "comment": "commission test",
        "type_filling": mt5.ORDER_FILLING_IOC,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"echec ouverture : retcode={getattr(res, 'retcode', None)} "
            f"{mt5.last_error()}")
        mt5.shutdown()
        return 1
    log(f"trade ouvert : deal_in={res.deal} price={res.price}")

    time.sleep(2)
    tick = mt5.symbol_info_tick(SYMBOL)
    close_req = dict(req)
    close_req.update({
        "type": mt5.ORDER_TYPE_SELL,
        "price": tick.bid,
        "position": res.order,
    })
    res2 = mt5.order_send(close_req)
    if res2 is None or res2.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"echec fermeture : retcode={getattr(res2, 'retcode', None)} "
            f"{mt5.last_error()}")
        mt5.shutdown()
        return 1
    log(f"trade ferme : deal_out={res2.deal}")

    # lecture de la commission reelle
    time.sleep(2)
    if not mt5.history_select(res2.deal - 10, res2.deal + 10):
        log("impossible de lire l'historique")
        mt5.shutdown()
        return 1
    total_commission = 0.0
    for i in range(mt5.history_deals_total()):
        ticket = mt5.history_deal_get_ticket(i)
        if ticket == 0:
            continue
        deal = mt5.history_deals_get(ticket=ticket)
        if deal is None:
            continue
        if deal.symbol == SYMBOL:
            total_commission += deal.commission
            log(f"deal {deal.ticket} entry={deal.entry} vol={deal.volume} "
                f"commission={deal.commission} profit={deal.profit}")

    rt_cost_usd = abs(total_commission) + spread * args.volume * info.trade_tick_value * (info.point / info.trade_tick_size)
    log(f"commission aller-retour totale : {total_commission:.4f} USD")
    log(f"cout all-in estime pour {args.volume} lot : "
        f"{abs(total_commission):.4f} comm + spread {spread:.2f} pts x "
        f"{args.volume} lot")
    per_lot = abs(total_commission) / args.volume / 2  # par lot par side
    log(f"commission normalisee : {per_lot:.4f} USD/lot/side "
        f"(Exness officiel USTEC raw : 0.3125)")

    verdict_pts = (abs(total_commission) / args.volume /
                   (info.trade_tick_value * (info.point / info.trade_tick_size))) + spread
    log(f"cout all-in : {verdict_pts:.2f} pts par lot aller-retour")
    if verdict_pts <= 1.3:
        log("VERDICT : comparable ou meilleur que Standard (1.12) -> "
            "scalping viable, on bascule sur raw")
    else:
        log("VERDICT : plus cher que Standard (1.12 pts) -> "
            "on reste sur Standard pour le scalping")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
