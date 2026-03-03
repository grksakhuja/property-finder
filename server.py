#!/usr/bin/env python3
"""
server.py — Flask backend for the Tokyo Rental Search viewer.

Serves static files and provides API endpoints to trigger scrapers
from the browser UI. Replaces `python -m http.server 8000`.

Usage:
    python server.py              # start on port 8000
    python server.py --port 9000  # custom port
"""

import argparse
import logging
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)

# Populated in main() before app.run(); used for CSRF origin validation
allowed_origins: set = set()

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------
SCRAPER_REGISTRY = {
    "best_estate": {
        "name": "Best Estate",
        "cmd": [sys.executable, "best_estate_search.py"],
        "category": "foreigner_friendly",
    },
    "rej": {
        "name": "Real Estate Japan",
        "cmd": [sys.executable, "realestate_jp_search.py"],
        "category": "foreigner_friendly",
    },
    "gaijinpot": {
        "name": "GaijinPot",
        "cmd": [sys.executable, "gaijinpot_search.py"],
        "category": "foreigner_friendly",
    },
    "wagaya": {
        "name": "Wagaya Japan",
        "cmd": [sys.executable, "wagaya_search.py"],
        "category": "foreigner_friendly",
    },
    "villagehouse": {
        "name": "Village House",
        "cmd": [sys.executable, "villagehouse_search.py"],
        "category": "foreigner_friendly",
    },
    "suumo": {
        "name": "SUUMO",
        "cmd": [sys.executable, "suumo_search.py"],
        "category": "japanese_only",
    },
    "ur": {
        "name": "UR Housing",
        "cmd": [sys.executable, "ur_rental_search.py"],
        "category": "japanese_only",
    },
    "pois": {
        "name": "Update POIs (Map Data)",
        "cmd": [sys.executable, "build_pois.py"],
        "category": "utility",
    },
}

# ---------------------------------------------------------------------------
# Scrape job state (module-level, protected by lock)
# ---------------------------------------------------------------------------
scrape_lock = threading.Lock()
scrape_state: dict = {"running": False, "scrapers": {}}


def _run_single_scraper(key: str) -> None:
    """Run one scraper subprocess, updating scrape_state in-place."""
    entry = SCRAPER_REGISTRY[key]
    with scrape_lock:
        scrape_state["scrapers"][key] = "running"

    try:
        result = subprocess.run(
            entry["cmd"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        status = "done" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        logging.warning("Scraper %s timed out after 600s", key)
        status = "failed"
    except Exception as exc:
        logging.exception("Scraper %s failed: %s", key, exc)
        status = "failed"

    with scrape_lock:
        scrape_state["scrapers"][key] = status


def _run_scrape_job(keys: list[str]) -> None:
    """Run selected scrapers in parallel, then mark job as finished."""
    try:
        with ThreadPoolExecutor(max_workers=min(len(keys), 4)) as executor:
            executor.map(_run_single_scraper, keys)
    finally:
        with scrape_lock:
            scrape_state["running"] = False


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.route("/api/scrapers", methods=["GET"])
def api_scrapers():
    """Return the scraper registry with categories."""
    out = {}
    for key, entry in SCRAPER_REGISTRY.items():
        out[key] = {"name": entry["name"], "category": entry["category"]}
    return jsonify(out)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """Start a scrape job with the selected scrapers."""
    # Basic CSRF protection: reject cross-origin requests
    origin = request.headers.get("Origin", "")
    if origin and origin not in allowed_origins:
        return jsonify({"error": "Cross-origin requests not allowed"}), 403

    data = request.get_json(silent=True) or {}
    keys = data.get("scrapers", [])

    # Validate keys
    valid_keys = [k for k in keys if k in SCRAPER_REGISTRY]
    if not valid_keys:
        return jsonify({"error": "No valid scrapers selected"}), 400

    with scrape_lock:
        if scrape_state["running"]:
            return jsonify({"error": "A scrape job is already running"}), 409
        scrape_state["running"] = True
        scrape_state["scrapers"] = {k: "pending" for k in valid_keys}

    thread = threading.Thread(target=_run_scrape_job, args=(valid_keys,), daemon=True)
    thread.start()

    return jsonify({"status": "started", "scrapers": valid_keys})


@app.route("/api/scrape/status", methods=["GET"])
def api_scrape_status():
    """Poll current scrape job progress."""
    with scrape_lock:
        return jsonify({
            "running": scrape_state["running"],
            "scrapers": dict(scrape_state["scrapers"]),
        })


# ---------------------------------------------------------------------------
# Static file serving (allowlisted files only)
# ---------------------------------------------------------------------------
ALLOWED_STATIC_FILES = {"viewer.html", "viewer.js", "viewer.css", "scoring_config.json", "geocoded_addresses.json"}
ALLOWED_STATIC_PREFIXES = {"results_", "area_pois"}
ALLOWED_STATIC_EXTENSIONS = {".json"}


def _is_allowed_static(filepath: str) -> bool:
    """Check if a filepath is allowed to be served."""
    name = Path(filepath).name
    if name in ALLOWED_STATIC_FILES:
        return True
    ext = Path(filepath).suffix
    if ext in ALLOWED_STATIC_EXTENSIONS:
        if any(name.startswith(prefix) for prefix in ALLOWED_STATIC_PREFIXES):
            return True
    return False


@app.route("/")
def serve_index():
    return send_from_directory(str(PROJECT_ROOT), "viewer.html")


@app.route("/<path:filepath>")
def serve_static(filepath):
    if not _is_allowed_static(filepath):
        abort(404)
    return send_from_directory(str(PROJECT_ROOT), filepath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Tokyo Rental Search viewer server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind (default: 127.0.0.1, use 0.0.0.0 for LAN access)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    if args.debug and args.host != "127.0.0.1":
        print("WARNING: --debug with non-loopback host exposes Werkzeug debugger to the network.")
        print("         Use --host 127.0.0.1 (default) or remove --debug.")
        sys.exit(1)

    allowed_origins.update({
        f"http://localhost:{args.port}",
        f"http://127.0.0.1:{args.port}",
    })

    print(f"Serving viewer at http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
