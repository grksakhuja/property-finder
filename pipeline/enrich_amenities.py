#!/usr/bin/env python3
"""
pipeline/enrich_amenities.py — Enrich normalised listings with nearby amenity counts.

Queries Overpass API for POIs near each geocoded listing and populates the
amenities field with counts of supermarkets, convenience stores, clinics, and parks.

Usage:
    python pipeline/enrich_amenities.py
    python pipeline/enrich_amenities.py --verbose
    python pipeline/enrich_amenities.py --limit 50 --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time

# Ensure project root is on sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.scraper_template import safe_write_json

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LISTINGS_PATH = os.path.join(DATA_DIR, "normalised_listings.json")
CACHE_PATH = os.path.join(DATA_DIR, "amenity_cache.json")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_DELAY = 10.0  # seconds between Overpass requests (generous to avoid 429s)
MAX_RETRIES = 3      # retry on 429/504 with exponential backoff

# Radius thresholds in metres
RADIUS_500M = 500
RADIUS_1KM = 1000

# Earth radius in metres for haversine
EARTH_RADIUS_M = 6_371_000


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two lat/lng points using haversine."""
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
    """Build a single Overpass QL query fetching all POI types around a point.

    Fetches:
    - shop=supermarket within 1km (filtered to 500m in post-processing)
    - shop=convenience within 500m
    - amenity=clinic|hospital within 1km
    - leisure=park within 500m
    """
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


def query_overpass(lat: float, lng: float, session=None) -> list[dict]:
    """Send an Overpass query and return the elements list.

    Args:
        lat: Latitude of the centre point.
        lng: Longitude of the centre point.
        session: Optional requests.Session (uses requests.post if None).

    Returns:
        List of OSM element dicts from the Overpass response.

    Raises:
        requests.HTTPError: On non-2xx response.
    """
    import requests

    query = build_overpass_query(lat, lng)
    post_fn = session.post if session else requests.post
    for attempt in range(MAX_RETRIES + 1):
        resp = post_fn(OVERPASS_URL, data={"data": query}, timeout=30)
        if resp.status_code in (429, 504) and attempt < MAX_RETRIES:
            wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
            logger.debug("  Overpass %d, retrying in %ds...", resp.status_code, wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        return data.get("elements", [])


# ---------------------------------------------------------------------------
# Count amenities from Overpass elements
# ---------------------------------------------------------------------------

def compute_convenience_score(counts: dict) -> float:
    """Compute a 0-10 convenience score from amenity counts.

    Weighted sum: supermarkets_500m * 1.5, konbini_500m * 1.0,
    clinics_1km * 0.5, parks_500m * 0.75, supermarkets_1km * 0.25.
    Capped at 10.0.
    """
    return min(10.0, (
        counts.get("supermarkets_500m", 0) * 1.5
        + counts.get("konbini_500m", 0) * 1.0
        + counts.get("clinics_1km", 0) * 0.5
        + counts.get("parks_500m", 0) * 0.75
        + counts.get("supermarkets_1km", 0) * 0.25
    ))


def count_amenities(
    elements: list[dict], centre_lat: float, centre_lng: float
) -> dict:
    """Categorise and count Overpass elements by type and distance.

    Returns dict with keys: supermarkets_500m, supermarkets_1km, konbini_500m,
    clinics_1km, parks_500m, convenience_score.
    """
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
# Location key helpers
# ---------------------------------------------------------------------------

def round_location(lat: float, lng: float) -> str:
    """Round lat/lng to 3 decimal places and return as cache key string."""
    return f"{lat:.3f},{lng:.3f}"


def parse_location_key(key: str) -> tuple[float, float]:
    """Parse a 'lat,lng' cache key back into floats."""
    lat_s, lng_s = key.split(",")
    return float(lat_s), float(lng_s)


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    """Load amenity cache from disk. Returns empty dict if file missing."""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    """Write amenity cache to disk using safe_write_json."""
    safe_write_json(cache, CACHE_PATH)


# ---------------------------------------------------------------------------
# Main enrichment logic
# ---------------------------------------------------------------------------

def extract_unique_locations(listings: list[dict]) -> dict[str, tuple[float, float]]:
    """Extract unique geocoded locations eligible for Overpass queries.

    Skips listings where geocode is None or confidence is 'city'.
    Deduplicates by rounding lat/lng to 3 decimal places.

    Returns:
        Dict mapping location key -> (lat, lng) tuple.
    """
    locations: dict[str, tuple[float, float]] = {}
    for listing in listings:
        geocode = listing.get("geocode")
        if not geocode:
            continue
        confidence = geocode.get("confidence")
        if confidence not in ("precise", "neighbourhood"):
            continue
        lat = geocode.get("lat")
        lng = geocode.get("lng")
        if lat is None or lng is None:
            continue
        key = round_location(lat, lng)
        if key not in locations:
            locations[key] = (lat, lng)
    return locations


def enrich_listings(listings: list[dict], cache: dict) -> list[dict]:
    """Populate the amenities field on each listing from the cache.

    Listings with confidence 'city' or null geocode get amenities=None.
    """
    for listing in listings:
        geocode = listing.get("geocode")
        if not geocode:
            listing["amenities"] = None
            continue
        confidence = geocode.get("confidence")
        if confidence not in ("precise", "neighbourhood"):
            listing["amenities"] = None
            continue
        lat = geocode.get("lat")
        lng = geocode.get("lng")
        if lat is None or lng is None:
            listing["amenities"] = None
            continue
        key = round_location(lat, lng)
        cached = cache.get(key)
        if cached:
            amenities = dict(cached)
            # Backfill convenience_score for older cache entries
            if amenities.get("convenience_score") is None:
                amenities["convenience_score"] = compute_convenience_score(amenities)
            listing["amenities"] = amenities
        else:
            listing["amenities"] = None
    return listings


def run(limit: int = 200, verbose: bool = False) -> None:
    """Main entry point: load listings, query Overpass, enrich, save."""
    import requests

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load listings
    if not os.path.exists(LISTINGS_PATH):
        logger.error("Normalised listings not found at %s", LISTINGS_PATH)
        sys.exit(1)

    with open(LISTINGS_PATH, encoding="utf-8") as f:
        listings = json.load(f)
    logger.info("Loaded %d listings", len(listings))

    # Load cache
    cache = load_cache()
    logger.info("Loaded %d cached locations", len(cache))

    # Extract unique locations
    locations = extract_unique_locations(listings)
    logger.info("Found %d unique geocoded locations", len(locations))

    # Filter out already-cached locations
    to_query = {k: v for k, v in locations.items() if k not in cache}
    logger.info("%d locations need Overpass queries", len(to_query))

    # Apply limit
    query_keys = list(to_query.keys())[:limit]
    if len(to_query) > limit:
        logger.info("Capped to %d queries (--limit)", limit)

    # Query Overpass for each uncached location
    session = requests.Session()
    session.headers.update({"User-Agent": "TokyoRentalSearch/1.0"})

    for i, key in enumerate(query_keys):
        lat, lng = to_query[key]
        logger.debug(
            "[%d/%d] Querying Overpass for %s (%.4f, %.4f)",
            i + 1, len(query_keys), key, lat, lng,
        )
        try:
            elements = query_overpass(lat, lng, session=session)
            amenities = count_amenities(elements, lat, lng)
            cache[key] = amenities
            logger.debug("  -> %s", amenities)
        except Exception:
            logger.exception("  Overpass query failed for %s", key)

        if i < len(query_keys) - 1:
            time.sleep(REQUEST_DELAY)

    # Save updated cache
    save_cache(cache)
    logger.info("Cache now has %d locations", len(cache))

    # Enrich listings
    listings = enrich_listings(listings, cache)
    enriched_count = sum(1 for l in listings if l.get("amenities") is not None)
    logger.info("Enriched %d / %d listings with amenity data", enriched_count, len(listings))

    # Write back
    safe_write_json(listings, LISTINGS_PATH)
    logger.info("Wrote updated listings to %s", LISTINGS_PATH)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Enrich normalised listings with Overpass amenity data."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max locations to query (default: 200)",
    )
    args = parser.parse_args()
    run(limit=args.limit, verbose=args.verbose)


if __name__ == "__main__":
    main()
