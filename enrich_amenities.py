#!/usr/bin/env python3
"""
enrich_amenities.py — Enrich listings with nearby amenity counts.

Queries Overpass API for POIs near each geocoded listing and writes
amenities_cache.json keyed by listing ID. The viewer loads this as
a sidecar file and joins by ID at render time.

Usage:
    python enrich_amenities.py
    python enrich_amenities.py --verbose
    python enrich_amenities.py --limit 50 --verbose
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import math
import os
import re
import time

from shared.scraper_template import safe_write_json

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GEOCODED_PATH = os.path.join(PROJECT_ROOT, "geocoded_addresses.json")
CACHE_PATH = os.path.join(PROJECT_ROOT, "amenities_cache.json")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_DELAY = 10.0  # seconds between Overpass requests
MAX_RETRIES = 3

# Radius thresholds in metres
RADIUS_500M = 500
RADIUS_1KM = 1000
EARTH_RADIUS_M = 6_371_000


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two lat/lng points."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Overpass query
# ---------------------------------------------------------------------------

def build_overpass_query(lat: float, lng: float) -> str:
    """Build Overpass QL query for POIs near a point."""
    return (
        "[out:json][timeout:25];\n"
        "(\n"
        f'  node["shop"="supermarket"](around:{RADIUS_1KM},{lat},{lng});\n'
        f'  node["shop"="convenience"](around:{RADIUS_500M},{lat},{lng});\n'
        f'  node["amenity"~"clinic|hospital"](around:{RADIUS_1KM},{lat},{lng});\n'
        f'  node["leisure"="park"](around:{RADIUS_500M},{lat},{lng});\n'
        ");\n"
        "out body;"
    )


def query_overpass(lat: float, lng: float, session=None) -> list:
    """Send an Overpass query and return the elements list."""
    import requests

    query = build_overpass_query(lat, lng)
    post_fn = session.post if session else requests.post
    for attempt in range(MAX_RETRIES + 1):
        resp = post_fn(OVERPASS_URL, data={"data": query}, timeout=30)
        if resp.status_code in (429, 504) and attempt < MAX_RETRIES:
            wait = 2 ** (attempt + 1)
            logger.debug("  Overpass %d, retrying in %ds...", resp.status_code, wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json().get("elements", [])


def compute_convenience_score(counts: dict) -> float:
    """Compute a 0-10 convenience score from amenity counts."""
    return min(10.0, (
        counts.get("supermarkets_500m", 0) * 1.5
        + counts.get("konbini_500m", 0) * 1.0
        + counts.get("clinics_1km", 0) * 0.5
        + counts.get("parks_500m", 0) * 0.75
        + counts.get("supermarkets_1km", 0) * 0.25
    ))


def count_amenities(elements: list, centre_lat: float, centre_lng: float) -> dict:
    """Categorise and count Overpass elements by type and distance."""
    counts = {
        "supermarkets_500m": 0,
        "supermarkets_1km": 0,
        "konbini_500m": 0,
        "clinics_1km": 0,
        "parks_500m": 0,
        "convenience_score": 0.0,
    }

    for el in elements:
        el_lat = el.get("lat")
        el_lng = el.get("lon")
        if el_lat is None or el_lng is None:
            continue
        dist = haversine_distance(centre_lat, centre_lng, el_lat, el_lng)
        tags = el.get("tags", {})

        if tags.get("shop") == "supermarket":
            if dist <= RADIUS_1KM:
                counts["supermarkets_1km"] += 1
            if dist <= RADIUS_500M:
                counts["supermarkets_500m"] += 1
        elif tags.get("shop") == "convenience":
            if dist <= RADIUS_500M:
                counts["konbini_500m"] += 1
        elif tags.get("amenity") in ("clinic", "hospital"):
            if dist <= RADIUS_1KM:
                counts["clinics_1km"] += 1
        elif tags.get("leisure") == "park":
            if dist <= RADIUS_500M:
                counts["parks_500m"] += 1

    counts["convenience_score"] = compute_convenience_score(counts)
    return counts


# ---------------------------------------------------------------------------
# Listing ID generation (matches viewer.js logic)
# ---------------------------------------------------------------------------

def make_listing_id(room: dict) -> str:
    """Generate a deterministic listing ID from room fields.

    Format: {source}__{area}__{building}__{room_type}__{floor}
    (lowercased, non-alphanumeric chars replaced with _, stripped)
    """
    parts = [
        room.get("source", ""),
        room.get("area", ""),
        room.get("building", ""),
        room.get("room_type", ""),
        room.get("floor", ""),
    ]
    return "__".join(
        re.sub(r'^_|_$', '', re.sub(r'[^a-z0-9]+', '_', p.lower()))
        for p in parts
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(limit: int = 200, verbose: bool = False) -> None:
    """Load geocoded data, query Overpass for uncached locations, write sidecar."""
    import requests

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load geocoded addresses
    if not os.path.exists(GEOCODED_PATH):
        logger.error("Geocoded addresses not found at %s", GEOCODED_PATH)
        logger.info("Run geocode_properties.py first.")
        return

    with open(GEOCODED_PATH, encoding="utf-8") as f:
        geocoded = json.load(f)
    logger.info("Loaded %d geocoded addresses", len(geocoded))

    # Load all results files to get listing addresses
    results_files = glob.glob(os.path.join(PROJECT_ROOT, "results*.json"))
    all_rooms = []
    for rf in results_files:
        try:
            with open(rf, encoding="utf-8") as f:
                data = json.load(f)
            rooms = data.get("rooms", [])
            all_rooms.extend(rooms)
        except (json.JSONDecodeError, OSError):
            continue
    logger.info("Loaded %d rooms from %d results files", len(all_rooms), len(results_files))

    # Load existing cache
    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    logger.info("Loaded %d cached listing amenities", len(cache))

    # Build address → listing IDs mapping
    address_to_ids = {}
    for room in all_rooms:
        address = room.get("address", "")
        if not address:
            continue
        lid = make_listing_id(room)
        if address not in address_to_ids:
            address_to_ids[address] = []
        address_to_ids[address].append(lid)

    # Find addresses that have geocoded data and uncached listing IDs
    locations_to_query = {}  # location_key → (lat, lng, [listing_ids])
    for address, listing_ids in address_to_ids.items():
        geo = geocoded.get(address)
        if not geo or not isinstance(geo, dict):
            continue
        lat = geo.get("lat")
        lng = geo.get("lng")
        if lat is None or lng is None:
            continue

        # Check if any listing IDs for this address are uncached
        uncached_ids = [lid for lid in listing_ids if lid not in cache]
        if not uncached_ids:
            continue

        loc_key = f"{lat:.3f},{lng:.3f}"
        if loc_key not in locations_to_query:
            locations_to_query[loc_key] = (lat, lng, [])
        locations_to_query[loc_key][2].extend(uncached_ids)

    logger.info("%d unique locations need Overpass queries", len(locations_to_query))

    # Query Overpass
    session = requests.Session()
    session.headers.update({"User-Agent": "TokyoRentalSearch/1.0"})

    query_keys = list(locations_to_query.keys())[:limit]
    if len(locations_to_query) > limit:
        logger.info("Capped to %d queries (--limit)", limit)

    for i, loc_key in enumerate(query_keys):
        lat, lng, listing_ids = locations_to_query[loc_key]
        logger.debug("[%d/%d] Querying Overpass for %s", i + 1, len(query_keys), loc_key)

        try:
            elements = query_overpass(lat, lng, session=session)
            amenities = count_amenities(elements, lat, lng)
            # Write amenities for all listing IDs at this location
            for lid in listing_ids:
                cache[lid] = amenities
            logger.debug("  -> %s (%d listings)", amenities, len(listing_ids))
        except Exception:
            logger.exception("  Overpass query failed for %s", loc_key)

        if i < len(query_keys) - 1:
            time.sleep(REQUEST_DELAY)

    # Save cache
    safe_write_json(cache, CACHE_PATH)
    logger.info("Amenities cache now has %d entries, saved to %s", len(cache), CACHE_PATH)


def main():
    parser = argparse.ArgumentParser(
        description="Enrich listings with Overpass amenity data (sidecar JSON)."
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--limit", type=int, default=200, help="Max locations to query")
    args = parser.parse_args()
    run(limit=args.limit, verbose=args.verbose)


if __name__ == "__main__":
    main()
