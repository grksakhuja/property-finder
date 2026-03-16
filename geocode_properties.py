#!/usr/bin/env python3
"""
geocode_properties.py — Geocode property addresses via CSIS + Nominatim.

Reads all results*.json files, extracts unique addresses, geocodes via
U-Tokyo CSIS (Japanese addresses) or OpenStreetMap Nominatim (English),
and caches results in geocoded_addresses.json.

Usage:
    python geocode_properties.py               # geocode new addresses only
    python geocode_properties.py --retry-failed # re-attempt previously failed lookups
    python geocode_properties.py --dry-run      # show what would be geocoded
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import xml.etree.ElementTree as ET

import requests

# ---------------------------------------------------------------------------
# Security: Path anchoring
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(PROJECT_ROOT, "geocoded_addresses.json")

# ---------------------------------------------------------------------------
# U-Tokyo CSIS geocoder config (primary for Japanese addresses)
# ---------------------------------------------------------------------------
CSIS_URL = "https://geocode.csis.u-tokyo.ac.jp/cgi-bin/simple_geocode.cgi"
CSIS_MIN_DELAY = 0.5  # conservative — no documented rate limit

# ---------------------------------------------------------------------------
# Nominatim config — ToS compliance (primary for English, fallback for JP)
# ---------------------------------------------------------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "finding-property-tokyo/1.0 (local-dev)"
NOMINATIM_MIN_DELAY = 1.1  # seconds between requests
MAX_NEW_PER_RUN = 200       # cap to respect Nominatim's service
INCREMENTAL_SAVE_INTERVAL = 20

# Japan bounding box for coordinate validation
JAPAN_LAT_MIN, JAPAN_LAT_MAX = 24.0, 46.0
JAPAN_LNG_MIN, JAPAN_LNG_MAX = 122.0, 154.0

# ---------------------------------------------------------------------------
# Address validation
# ---------------------------------------------------------------------------
MAX_ADDRESS_LEN = 200
_VALID_ADDRESS_RE = re.compile(
    r'^[\w\s\u3000-\u9FFF\uF900-\uFAFF\u30A0-\u30FF\u3040-\u309F'
    r'\uFF00-\uFFEF\u4E00-\u9FFF\-\.,/\(\)#\u00C0-\u024F\']+$'
)

# Prefecture kanji for UR addresses (UR omits prefecture)
PREFECTURE_KANJI = {
    "saitama": "埼玉県",
    "chiba": "千葉県",
    "kanagawa": "神奈川県",
    "tokyo": "東京都",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("geocoder")


def validate_address(address: str) -> str | None:
    """Validate and sanitize an address string. Returns None if invalid."""
    if not isinstance(address, str):
        return None
    address = unicodedata.normalize("NFC", address)
    # Strip control characters
    address = "".join(" " if unicodedata.category(c) == "Cc" else c for c in address)
    address = " ".join(address.split())
    if not address or len(address) > MAX_ADDRESS_LEN:
        return None
    if not _VALID_ADDRESS_RE.match(address):
        return None
    return address


def is_path_safe(path: str) -> bool:
    """Check that a resolved path is inside PROJECT_ROOT."""
    real = os.path.realpath(path)
    return real.startswith(os.path.realpath(PROJECT_ROOT) + os.sep)


def load_cache() -> dict:
    """Load geocoding cache from disk."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Cache file unreadable, starting fresh: %s", e)
        return {}


def save_cache(cache: dict) -> None:
    """Atomically write cache to disk with file locking."""
    dirpath = os.path.dirname(os.path.abspath(CACHE_FILE))
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(cache, f, ensure_ascii=False, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.rename(tmp_path, CACHE_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def normalize_address_for_geocoding(raw_address: str, source: str,
                                     prefecture: str = "") -> str | None:
    """Normalize a property address into a geocoding query string.

    Per-source rules:
    - UR: Prepend prefecture kanji (UR addresses lack it)
    - SUUMO/BestEstate: Use as-is (complete Japanese addresses)
    - REJ/GaijinPot/Wagaya/VillageHouse: English — strip prefix, append Japan
    """
    addr = validate_address(raw_address)
    if not addr:
        return None

    english_sources = {"rej", "gaijinpot", "wagaya", "villagehouse"}

    if source == "ur":
        pref_kanji = PREFECTURE_KANJI.get(prefecture, "")
        if pref_kanji and not addr.startswith(pref_kanji):
            addr = pref_kanji + addr
    elif source in english_sources:
        # Strip common prefixes like "in "
        addr = re.sub(r'^in\s+', '', addr, flags=re.IGNORECASE)
        if not addr.lower().endswith("japan"):
            addr = addr.rstrip(",. ") + ", Japan"

    return addr


def extract_addresses_from_results() -> dict[str, dict]:
    """Read all results*.json and extract unique (raw_address → metadata) pairs."""
    import glob
    addresses = {}  # raw_address → {"source": ..., "prefecture": ...}

    pattern = os.path.join(PROJECT_ROOT, "results*.json")
    for filepath in sorted(glob.glob(pattern)):
        if not is_path_safe(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping %s: %s", os.path.basename(filepath), e)
            continue

        source = data.get("source", "").lower()
        if not source:
            continue

        for area_name, properties in data.get("areas", {}).items():
            if not isinstance(properties, list):
                continue
            for prop in properties:
                raw = prop.get("address", "")
                if not raw or raw in addresses:
                    continue
                # Determine prefecture from area name (best effort)
                pref = _guess_prefecture(area_name)
                addresses[raw] = {"source": source, "prefecture": pref}

    return addresses


def _guess_prefecture(area_name: str) -> str:
    """Guess prefecture from area name (mirrors viewer.js getPrefecture).

    Returns empty string if prefecture cannot be determined — callers
    handle this gracefully (e.g. normalize_address_for_geocoding skips
    prefecture prepend when empty).
    """
    saitama = ['Kawaguchi', 'Wako', 'Urawa', 'Omiya', 'Kawagoe', 'Toda',
               'Warabi', 'Asaka', 'Niiza', 'Saitama Minami', 'Saitama Chuo']
    chiba = ['Ichikawa', 'Funabashi', 'Urayasu', 'Matsudo']
    kanagawa = ['Kawasaki', 'Saiwai', 'Nakahara', 'Takatsu', 'Yokohama',
                'Kamakura', 'Fujisawa', 'Chigasaki']
    tokyo = ['Kita-ku', 'Itabashi-ku', 'Nerima-ku', 'Adachi-ku', 'Edogawa-ku']
    if any(a in area_name for a in saitama):
        return 'saitama'
    if any(a in area_name for a in chiba):
        return 'chiba'
    if any(a in area_name for a in kanagawa):
        return 'kanagawa'
    if any(a in area_name for a in tokyo):
        return 'tokyo'
    return ''


def _is_japanese_address(query: str) -> bool:
    """True if address contains Japanese script (kanji/kana)."""
    return any('\u3000' <= c <= '\u9FFF' or '\uF900' <= c <= '\uFAFF' for c in query)


def _simplify_japanese_address(query: str) -> str | None:
    """Strip building number suffixes for a broader geocode attempt.

    Returns simplified address or None if nothing meaningful remains.
    """
    simplified = re.sub(
        r'[\d\-]+[\(（].*?[\)）]$|[\d\-]+番.*$|[\d\-]+号.*$|[\d\-]+$',
        '', query,
    ).rstrip()
    # Only return if we actually shortened it and something remains
    if simplified and simplified != query:
        return simplified
    return None


def geocode_address_csis(session: requests.Session, query: str,
                         last_csis_time: list) -> tuple | None:
    """Geocode a Japanese address via U-Tokyo CSIS.

    Returns (lat, lng) or None. Updates last_csis_time[0] in-place.
    """
    now = time.monotonic()
    elapsed = now - last_csis_time[0]
    if elapsed < CSIS_MIN_DELAY:
        time.sleep(CSIS_MIN_DELAY - elapsed)
    last_csis_time[0] = time.monotonic()

    try:
        resp = session.get(CSIS_URL, params={"addr": query}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("CSIS request failed for %r: %s", query[:60], e)
        return None

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        logger.warning("CSIS returned invalid XML for %r", query[:60])
        return None

    candidate = root.find(".//candidate")
    if candidate is None:
        return None

    lat_el = candidate.find("latitude")
    lng_el = candidate.find("longitude")
    if lat_el is None or lng_el is None or lat_el.text is None or lng_el.text is None:
        return None

    try:
        lat = float(lat_el.text)
        lng = float(lng_el.text)
    except (ValueError, TypeError):
        return None

    if not (JAPAN_LAT_MIN <= lat <= JAPAN_LAT_MAX and
            JAPAN_LNG_MIN <= lng <= JAPAN_LNG_MAX):
        logger.warning("CSIS coords outside Japan for %r: (%.4f, %.4f)",
                        query[:60], lat, lng)
        return None

    return (lat, lng)


def geocode_address(session: requests.Session, query: str,
                    last_request_time: list) -> tuple | None:
    """Geocode a single address via Nominatim with rate limiting.

    Returns (lat, lng) or None. Updates last_request_time[0] in-place.
    """
    # Enforce minimum delay
    now = time.monotonic()
    elapsed = now - last_request_time[0]
    if elapsed < NOMINATIM_MIN_DELAY:
        time.sleep(NOMINATIM_MIN_DELAY - elapsed)

    last_request_time[0] = time.monotonic()

    try:
        resp = session.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "jp",
                "accept-language": "en",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Request failed for %r: %s", query[:60], e)
        return None

    try:
        results = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None

    if not results or not isinstance(results, list):
        return None

    try:
        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
    except (KeyError, ValueError, TypeError):
        return None

    # Validate coordinates are within Japan bounding box
    if not (JAPAN_LAT_MIN <= lat <= JAPAN_LAT_MAX and
            JAPAN_LNG_MIN <= lng <= JAPAN_LNG_MAX):
        logger.warning("Coordinates outside Japan for %r: (%.4f, %.4f)",
                        query[:60], lat, lng)
        return None

    return (lat, lng)


def main():
    parser = argparse.ArgumentParser(
        description="Geocode property addresses via CSIS + Nominatim")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-attempt previously failed lookups (null entries)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be geocoded without making requests")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("Extracting addresses from results files...")
    all_addresses = extract_addresses_from_results()
    logger.info("Found %d unique addresses across all sources", len(all_addresses))

    if not all_addresses:
        logger.info("No addresses to geocode.")
        return

    cache = load_cache()
    logger.info("Cache has %d entries", len(cache))

    # Determine which addresses need geocoding
    to_geocode = []
    for raw_addr, meta in all_addresses.items():
        if raw_addr in cache:
            entry = cache[raw_addr]
            # Skip if already geocoded (has lat/lng)
            if entry is not None and "lat" in entry:
                continue
            # Skip failed lookups unless --retry-failed
            if entry is not None and "lat" not in entry:
                if not args.retry_failed:
                    continue
            # null entry = failed lookup
            if entry is None and not args.retry_failed:
                continue
        to_geocode.append((raw_addr, meta))

    logger.info("%d addresses need geocoding", len(to_geocode))

    if not to_geocode:
        logger.info("All addresses already cached. Nothing to do.")
        return

    # Cap at MAX_NEW_PER_RUN
    if len(to_geocode) > MAX_NEW_PER_RUN:
        logger.info("Capping at %d addresses per run (of %d total)",
                     MAX_NEW_PER_RUN, len(to_geocode))
        to_geocode = to_geocode[:MAX_NEW_PER_RUN]

    if args.dry_run:
        for raw_addr, meta in to_geocode:
            query = normalize_address_for_geocoding(
                raw_addr, meta["source"], meta["prefecture"])
            logger.info("[DRY RUN] %s → query: %s", raw_addr[:60], query)
        return

    # Create a plain session (no 429 retry — we respect rate limits)
    session = requests.Session()
    session.headers.update({"User-Agent": NOMINATIM_USER_AGENT})

    last_request_time = [0.0]   # Nominatim rate-limit tracker
    last_csis_time = [0.0]      # CSIS rate-limit tracker
    geocoded_count = 0
    failed_count = 0

    # Estimate: JP addresses use CSIS (0.5s), EN use Nominatim (1.1s)
    jp_count = sum(1 for _, m in to_geocode
                   if m["source"] not in {"rej", "gaijinpot", "wagaya", "villagehouse"})
    en_count = len(to_geocode) - jp_count
    estimated_time = jp_count * CSIS_MIN_DELAY + en_count * NOMINATIM_MIN_DELAY
    logger.info("Estimated time: %.0f seconds (%.1f minutes) — %d JP (CSIS), %d EN (Nominatim)",
                estimated_time, estimated_time / 60, jp_count, en_count)

    for i, (raw_addr, meta) in enumerate(to_geocode, 1):
        query = normalize_address_for_geocoding(
            raw_addr, meta["source"], meta["prefecture"])

        if not query:
            logger.debug("Invalid address skipped: %s", raw_addr[:60])
            cache[raw_addr] = None
            failed_count += 1
            continue

        # Route: CSIS primary for Japanese, Nominatim for English
        if _is_japanese_address(query):
            result = geocode_address_csis(session, query, last_csis_time)
            provider = "csis"
            # If CSIS fails, try simplified address (strip building number)
            if not result:
                simplified = _simplify_japanese_address(query)
                if simplified:
                    logger.debug("CSIS retry with simplified: %s", simplified[:60])
                    result = geocode_address_csis(session, simplified, last_csis_time)
            # Nominatim fallback if CSIS still failed
            if not result:
                result = geocode_address(session, query, last_request_time)
                provider = "nominatim"
        else:
            result = geocode_address(session, query, last_request_time)
            provider = "nominatim"

        if result:
            lat, lng = result
            cache[raw_addr] = {"lat": lat, "lng": lng, "q": query, "provider": provider}
            geocoded_count += 1
            logger.debug("[%d/%d] OK (%s): %s → (%.4f, %.4f)",
                         i, len(to_geocode), provider, raw_addr[:50], lat, lng)
        else:
            cache[raw_addr] = None
            failed_count += 1
            logger.debug("[%d/%d] FAILED: %s (query: %s)",
                         i, len(to_geocode), raw_addr[:50], query)

        # Incremental save
        if i % INCREMENTAL_SAVE_INTERVAL == 0:
            save_cache(cache)
            logger.info("Progress: %d/%d (saved checkpoint)", i, len(to_geocode))

    # Final save
    save_cache(cache)

    logger.info("Geocoding complete: %d succeeded, %d failed, %d total cached",
                geocoded_count, failed_count, len(cache))


if __name__ == "__main__":
    main()
