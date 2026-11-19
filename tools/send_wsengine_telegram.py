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

msg = """🤖 WALL STREET ENGINE — moteur d'analyse institutionnel (4 couches)

COUCHE 1 CONTEXTE : regime EMA20/50, ATR percentile 1 an, veille, overnight, gap.
COUCHE 2 MICROSTRUCTURE : delta de la bougie d'ouverture (acheteurs vs vendeurs), volume relatif x20j, range OR en ATR.
COUCHE 3 SCORING : 2 500 setups candidats testes 10 ans, fit IS 2016-2021 -> validation OOS 2022-2026.
COUCHE 4 NOTE DU MATIN : briefing 09:25 / 09:45 / verdict (ws_morning_note.py).

⚠️ RESULTATS HONNETES (les plus importants) :
- Score multi-facteurs : NE generalise PAS en OOS (quintiles non monotones)
- Entree confirmee a la cloture de la bougie : +14,5% vs +22,3% baseline -> l'entree tardive coute trop
- Deux filtres microstructure semblaient doubler la perf (+35% OOS) : c'etait du LOOKAHEAD (delta connu seulement a la cloture). Pieges detects et corriges.
- Regle retenue : un facteur n'est valide que s'il est connu AVANT l'entree.

📌 CONCLUSION : a la resolution M15, le baseline 2R max2 reste intouchable. Le vrai tick-par-tick demande le flux d'ordres reel -> DOM_Recorder attaché lundi sur USTECr capture bid/ask/volumes, et apres 1-2 semaines le moteur calculera : delta reel par tick, imbalance du carnet, absorption, footprint.

📝 Exemple note du matin 09/04/2025 (pause tarifs) : trend filtre encore "BAISSIER" -> NO-TRADE, la bougie +2093 pts manquee. Lecon : le filtre trend est en retard sur les retournements violents."""

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
with urllib.request.urlopen(url, data=data, timeout=30) as r:
    print("telegram OK", r.status)
