#!/usr/bin/env python3
"""
server.py — Static file server for the Tokyo Rental Search viewer.

Usage:
    python server.py              # start on port 8080
    python server.py --port 9000  # custom port
"""

import argparse
import sys
from pathlib import Path

from flask import Flask, abort, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)

# ---------------------------------------------------------------------------
# Static file serving (allowlisted files only)
# ---------------------------------------------------------------------------
ALLOWED_STATIC_FILES = {
    "viewer.html", "viewer.js", "viewer.css",
    "scoring_config.json", "geocoded_addresses.json", "amenities_cache.json",
}
ALLOWED_STATIC_PREFIXES = {"results_", "area_pois"}
ALLOWED_STATIC_EXTENSIONS = {".json"}


def _is_allowed_static(filepath: str) -> bool:
    """Check if a filepath is allowed to be served."""
    p = Path(filepath)
    if p.parent != Path("."):
        return False
    name = p.name
    if name in ALLOWED_STATIC_FILES:
        return True
    if p.suffix in ALLOWED_STATIC_EXTENSIONS:
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

    print(f"Serving viewer at http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
