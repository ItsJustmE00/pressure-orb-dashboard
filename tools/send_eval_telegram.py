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

msg = """🧮 ORB 2R max2 — évaluation sans bruit (216 trades réels 2022-2026)

1) WALK-FORWARD ANNUEL
2022 : +14,3% (63% WR) | 2023 : -0,3% | 2024 : +2,3% | 2025 : +8,4% | 2026 : +4,4%
4 années positives sur 5, 2023 neutre. Edge réel mais variable selon régime.

2) L'EDGE N'EST PAS DU BRUIT
t-stat = 3,15 (> 2,0 requis)
Bootstrap 10 000 tirages : P(edge<=0) = 0,1%
DD réel 5,4% = DD médian des séquences mélangées (4,0%)

3) KELLY RÉEL (distribution des R)
f* = 18% du solde/trade -> half-Kelly = 8,8%
On trade actuellement à 0,5% : très conservateur.

4) PROJECTION 1 AN (bootstrap jour-par-jour, 10 000 essais)
0,5% : médiane 81k$ (depuis 57k) | 1% : 114k$ | 2% : 219k$ (95% DD 27%) | 4% : 707k$ (DD p95 48%)

5) CHEMIN VERS 1M (24,6k -> 1M, MC 10 000 chemins)
0,5% : ~10,5 ans | 1% : ~5,3 ans | 2% : ~2,7 ans | 4% : ~1,4 an | 8% : ~0,8 an
⚠️ Au-delà de 2%, les drawdowns deviennent profonds (DD p95 27% à 2%, 48% à 4%)
⚠️ Le bootstrap suppose que l'edge 2022-2026 persiste tel quel — le vrai risque est la dégradation de l'edge, pas la variance.

Recommandation : monter progressivement 0,5% -> 1% après 2 mois de forward propre, puis 2% max.
Le forward test mesure le winrate réel ; le scalper HFT + test commission raw arrivent ce soir."""

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
with urllib.request.urlopen(url, data=data, timeout=30) as r:
    print("telegram OK", r.status)
