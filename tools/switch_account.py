"""Bascule le terminal MT5 entre le compte demo ORB (Trial16) et le compte
Raw Spread (Trial15), et relance l'EA correspondant.

Usage :
  C:\\Python314\\python.exe tools\\switch_account.py raw      -> Raw Spread 474927957
  C:\\Python314\\python.exe tools\\switch_account.py orb      -> demo ORB 473001893
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

TERMINAL = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
DATA = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)

ACCOUNTS = {
    "orb": {
        "login": "473001893",
        "server": "Exness-MT5Trial16",
        "ini": "BOTH_start.ini",
    },
    "raw": {
        "login": "474927957",
        "server": "Exness-MT5Trial15",
        "ini": "RAW_start.ini",
    },
}


def kill_terminal():
    subprocess.run(["taskkill", "/IM", "terminal64.exe", "/F"], capture_output=True)
    time.sleep(3)


def write_login_ini(name, info, password):
    common = (
        "[Common]\n"
        f"Login={info['login']}\n"
        f"Password={password}\n"
        f"Server={info['server']}\n"
        "EnableExperts=1\n"
    )
    (DATA / "login_switch.ini").write_text(common, encoding="utf-16")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("account", choices=["orb", "raw"])
    ap.add_argument("--password", default="", help="mot de passe du compte cible")
    ap.add_argument("--expert", default="", help="EA a charger (defaut selon compte)")
    args = ap.parse_args()

    info = ACCOUNTS[args.account]
    password = args.password
    if not password:
        # si le compte a deja ete ouvert sur ce terminal, MT5 garde les
        # identifiants : relancer sans password suffit dans ce cas
        print("pas de password fourni -> tentative avec identifiants memorises")

    if args.expert:
        info = dict(info)
        info["ini"] = args.expert

    kill_terminal()
    write_login_ini(args.account, info, password)
    subprocess.Popen([str(TERMINAL), f"/config:{DATA / 'login_switch.ini'}"])
    time.sleep(8)
    print("terminal relance sur", info["server"], "login", info["login"])
    print("verifier avec : /api/live -> account.login =", info["login"])


if __name__ == "__main__":
    main()
