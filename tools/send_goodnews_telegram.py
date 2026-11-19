import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "tools" / "telegram.env"


def load_credentials():
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    token = values.get("TELEGRAM_BOT_TOKEN")
    chat_id = values.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit(f"Identifiants Telegram manquants dans {ENV}")
    return token, chat_id


token, chat_id = load_credentials()

msg = """📊 ORB — bonnes nouvelles du jour

✅ Test visuel terminé : la config 2R, max 2 trades/jour, risque 0,5 % est confirmée la meilleure sur 10 ans de données réelles :
- OOS 2022-2025 : +22,3 % / DD 5,4 %
- Équité 57 000 $ -> ~75 000 $ (courbe la plus propre)

❌ Améliorations testées (breakeven, TP partiel, time-stops) : toutes dégradent. L'edge = laisser courir à 2R.

📈 Compte Raw Spread activé : USTECr, spread stocké 0,06 pt vs 1,12 pt Standard.
⏳ Test de commission automatique à la réouverture du marché ce soir -> verdict raw vs Standard.
🤖 Scalper HFT MicroScalper prêt (O-U z-score par tick, 500 trades/jour max).

📅 Bot ORB reprend lundi 09:30 NY (bascule compte avant ouverture)."""

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
try:
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        print("telegram OK", r.status)
except Exception as e:
    print("erreur :", e)
