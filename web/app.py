import argparse
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

import mt5_service
import results_service

app = Flask(__name__, template_folder="templates", static_folder="static")
app.json.sort_keys = False


@app.after_request
def add_headers(response):
    if response.mimetype == "application/json":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    # Autoriser le frontend statique hébergé sur Vercel à lire l'API locale
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    live = mt5_service.live_snapshot()
    return jsonify(
        {
            "ok": bool(live.get("ok")),
            "time": datetime.now(timezone.utc).isoformat(),
            "terminal_running": live.get("terminal_running", False),
            "mt5_connected": bool(live.get("server", {}).get("connected")),
            "error": live.get("error"),
        }
    )


@app.route("/api/live")
def live():
    return jsonify(mt5_service.live_snapshot())


@app.route("/api/results")
def results():
    return jsonify(results_service.results_payload())


@app.route("/api/config")
def config_api():
    live = mt5_service.live_snapshot()
    return jsonify(
        {
            "ok": True,
            "config": live.get("config", {}),
            "ea": live.get("ea", {}),
            "terminal_running": live.get("terminal_running", False),
        }
    )


@app.route("/api/report")
def report_api():
    return jsonify({"ok": True, "html": results_service.report_html()})


@app.route("/report")
def report_page():
    return render_template("report.html", report=results_service.report_html())


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"ok": False, "error": "route inconnue"}), 404


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dashboard ORB BOTH")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)
