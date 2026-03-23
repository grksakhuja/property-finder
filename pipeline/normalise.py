#!/usr/bin/env python3
"""
pipeline/normalise.py — Normalise raw scraper results into canonical listing format.

Reads all results_*.json + results.json (UR), applies SOURCE_FIELDS mapping,
generates stable IDs, parses size/walk/age, populates geocode from cache,
and writes data/normalised_listings.json.

Usage:
    python pipeline/normalise.py
    python pipeline/normalise.py --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import unicodedata

# Ensure project root is on sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.config import AREAS, Area

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source file → source key mapping
# ---------------------------------------------------------------------------
SOURCE_FILES = [
    ("results.json", "ur"),
    ("results_suumo.json", "suumo"),
    ("results_realestate_jp.json", "rej"),
    ("results_best_estate.json", "best_estate"),
    ("results_gaijinpot.json", "gaijinpot"),
    ("results_wagaya.json", "wagaya"),
    ("results_villagehouse.json", "villagehouse"),
]

# ---------------------------------------------------------------------------
# SOURCE_FIELDS — mirrors viewer.js SOURCE_FIELDS exactly
# ---------------------------------------------------------------------------
SOURCE_FIELDS = {
    "ur": {
        "layout": "room_type", "size": "floorspace", "url": "url",
        "fee": "commonfee", "feeVal": "commonfee_value",
        "deposit": "shikikin", "roomName": "room_name",
        "hasAge": False, "hasMoveIn": False,
    },
    "suumo": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": True, "hasMoveIn": True,
    },
    "rej": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": True, "hasMoveIn": True, "fallbackFee": True,
    },
    "best_estate": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": True, "hasMoveIn": True, "fallbackFee": True,
    },
    "gaijinpot": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": True, "hasMoveIn": True, "fallbackFee": True,
    },
    "wagaya": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": True, "hasMoveIn": True, "fallbackFee": True,
    },
    "villagehouse": {
        "layout": "layout", "size": "size", "url": "detail_url",
        "fee": "admin_fee", "feeVal": "admin_fee_value",
        "deposit": "deposit", "roomName": None,
        "hasAge": False, "hasMoveIn": True, "fallbackFee": True,
    },
}

# EN-address sources that don't need JP->EN address translation
EN_SOURCES = {"rej", "gaijinpot", "wagaya", "villagehouse"}

# ---------------------------------------------------------------------------
# Area lookup (name → Area object)
# ---------------------------------------------------------------------------
_AREA_MAP: dict[str, Area] = {a.name: a for a in AREAS}


def get_area(area_name: str) -> Area | None:
    """Look up Area object by canonical name."""
    return _AREA_MAP.get(area_name)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
_SIZE_RE = re.compile(r"([\d.]+)")


def parse_size_sqm(size_str: str | None) -> float | None:
    """Parse size string to float sqm. Handles '66.15m2', '66.15m²', '66.15㎡', '75㎡'."""
    if not size_str:
        return None
    m = _SIZE_RE.search(size_str)
    return float(m.group(1)) if m else None


_WALK_JP_RE = re.compile(r"(?:徒歩|歩)(\d+)")
_WALK_EN_RE = re.compile(r"(\d+)\s*(?:-\s*)?min\.?\s*walk", re.IGNORECASE)


def parse_walk_minutes(access: str | None) -> int:
    """Parse walk time from access string. Returns minimum walk time, or -1 if unknown."""
    if not access:
        return -1
    matches = []
    for m in _WALK_JP_RE.finditer(access):
        matches.append(int(m.group(1)))
    for m in _WALK_EN_RE.finditer(access):
        matches.append(int(m.group(1)))
    return min(matches) if matches else -1


def parse_building_age_years(prop: dict, has_age: bool) -> int | None:
    """Extract building age in years. Returns None if not available."""
    if not has_age:
        return None
    age = prop.get("building_age_years")
    if age is not None and age >= 0:
        return age
    return None


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------
def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def generate_id(source: str, area_name: str, building_name: str,
                room_type: str, size_sqm: float | None) -> str:
    """Generate a stable listing ID from key fields."""
    parts = [
        source,
        _slugify(area_name.split("(")[0].strip()),
        _slugify(building_name or "unknown"),
        _slugify(room_type or "unknown"),
        str(size_sqm) if size_sqm else "0",
    ]
    return "__".join(parts)


def deduplicate_ids(listings: list[dict]) -> None:
    """Add suffixes to duplicate IDs in-place."""
    seen: dict[str, int] = {}
    for listing in listings:
        base_id = listing["id"]
        if base_id in seen:
            seen[base_id] += 1
            listing["id"] = f"{base_id}__{seen[base_id]}"
        else:
            seen[base_id] = 0


# ---------------------------------------------------------------------------
# Geocode integration
# ---------------------------------------------------------------------------
def load_geocode_cache(project_root: str) -> dict:
    """Load geocoded_addresses.json cache."""
    cache_path = os.path.join(project_root, "geocoded_addresses.json")
    if not os.path.exists(cache_path):
        logger.info("No geocoded_addresses.json found")
        return {}
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _guess_geocode_address_key(source: str, address: str, area: Area | None) -> str:
    """Build the address key used in geocoded_addresses.json.

    The geocoder (geocode_properties.py) stores entries keyed by the raw
    address string from the scraper output — no transformation applied.
    So the lookup key is simply the raw address.
    """
    return address or ""


def infer_geocode_confidence(source: str, geocode_entry: dict | None) -> str | None:
    """Infer geocode confidence from cache entry.

    - provider=csis → 'precise'
    - provider=nominatim + gaijinpot → 'neighbourhood'
    - provider=nominatim + wagaya/villagehouse/rej → 'city'
    - No provider field (older cache) → infer from source
    """
    if not geocode_entry:
        return None
    provider = geocode_entry.get("provider")
    if provider == "csis":
        return "precise"
    if provider == "nominatim":
        if source == "gaijinpot":
            return "neighbourhood"
        if source in ("wagaya", "villagehouse", "rej"):
            return "city"
        return "neighbourhood"
    # No provider field (older cache entries) — infer from source
    if source in ("ur", "suumo"):
        return "precise"  # JP addresses → likely CSIS
    if source == "gaijinpot":
        return "neighbourhood"
    if source in ("wagaya", "villagehouse", "rej"):
        return "city"
    return "neighbourhood"


def build_geocode_field(source: str, address: str, area: Area | None,
                        cache: dict) -> dict | None:
    """Build the geocode field for a listing from the cache."""
    key = _guess_geocode_address_key(source, address, area)
    entry = cache.get(key)
    if not entry:
        return None
    confidence = infer_geocode_confidence(source, entry)
    return {
        "lat": entry["lat"],
        "lng": entry["lng"],
        "confidence": confidence,
        "provider": entry.get("provider", "unknown"),
    }


# ---------------------------------------------------------------------------
# Main normalisation
# ---------------------------------------------------------------------------
def normalise_source(data: dict, source: str, geocode_cache: dict) -> list[dict]:
    """Normalise one source file into canonical listings."""
    f = SOURCE_FIELDS[source]
    listings = []

    areas_data = data.get("areas", {})
    for area_name, properties in areas_data.items():
        area_obj = get_area(area_name)
        prefecture = area_obj.prefecture if area_obj else _guess_prefecture(area_name)

        for prop in properties:
            building_name = prop.get("name", "")
            address = prop.get("address", "")
            access = prop.get("access", "")
            has_age = f["hasAge"]
            building_age_years = parse_building_age_years(prop, has_age)

            for room in prop.get("rooms", []):
                size_str = room.get(f["size"], "")
                size_sqm = parse_size_sqm(size_str)
                room_type = room.get(f["layout"], "")
                room_name = room.get(f["roomName"], "") if f["roomName"] else ""

                # Financial fields
                rent_value = room.get("rent_value", 0) or 0
                if f.get("fallbackFee"):
                    admin_fee_value = room.get(f["feeVal"]) or 0
                else:
                    admin_fee_value = room.get(f["feeVal"], 0) or 0
                total_monthly = room.get("total_value", 0) or 0

                if f["hasMoveIn"]:
                    deposit_value = room.get("deposit_value", 0) or 0
                    key_money_value = room.get("key_money_value", 0) or 0
                    move_in_cost = rent_value + deposit_value + key_money_value
                else:
                    deposit_value = 0
                    key_money_value = 0
                    move_in_cost = 0

                url_field = f["url"]
                url = room.get(url_field, "")

                listing_id = generate_id(source, area_name, building_name,
                                         room_type, size_sqm)

                geocode = build_geocode_field(source, address, area_obj, geocode_cache)

                listings.append({
                    "id": listing_id,
                    "source": source,
                    "area_name": area_name,
                    "area_en": area_name.split("(")[0].strip(),
                    "prefecture": prefecture,
                    "building_name": building_name,
                    "address": address,
                    "access": access,
                    "room_type": room_type,
                    "floor": room.get("floor", ""),
                    "size_sqm": size_sqm,
                    "building_age_years": building_age_years,
                    "rent_value": rent_value,
                    "admin_fee_value": admin_fee_value,
                    "total_monthly": total_monthly,
                    "deposit_value": deposit_value,
                    "key_money_value": key_money_value,
                    "move_in_cost": move_in_cost,
                    "url": url,
                    "room_name": room_name,
                    "walk_minutes_claimed": parse_walk_minutes(access),
                    "geocode": geocode,
                    "commute": None,
                    "amenities": None,
                    "hazard": None,
                    "scores": None,
                    "grade": None,
                })

    return listings


def _guess_prefecture(area_name: str) -> str:
    """Fallback prefecture guess from area name when Area object not found."""
    saitama = ["Kawaguchi", "Wako", "Urawa", "Omiya", "Kawagoe", "Toda",
               "Warabi", "Saitama", "Asaka", "Niiza"]
    chiba = ["Ichikawa", "Funabashi", "Urayasu", "Matsudo"]
    tokyo = ["Kita-ku", "Itabashi", "Nerima", "Adachi", "Edogawa"]
    for name in saitama:
        if name in area_name:
            return "saitama"
    for name in chiba:
        if name in area_name:
            return "chiba"
    for name in tokyo:
        if name in area_name:
            return "tokyo"
    return "kanagawa"


def run_normalise(project_root: str | None = None, verbose: bool = False) -> list[dict]:
    """Run full normalisation pipeline. Returns list of normalised listings."""
    if project_root is None:
        project_root = PROJECT_ROOT

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    geocode_cache = load_geocode_cache(project_root)
    logger.info("Loaded %d geocode cache entries", len(geocode_cache))

    all_listings = []
    for filename, source in SOURCE_FILES:
        filepath = os.path.join(project_root, filename)
        if not os.path.exists(filepath):
            logger.debug("Skipping %s (not found)", filename)
            continue
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        listings = normalise_source(data, source, geocode_cache)
        all_listings.extend(listings)
        logger.info("  %s: %d listings", source, len(listings))

    deduplicate_ids(all_listings)
    logger.info("Total normalised listings: %d", len(all_listings))

    # Write output
    output_dir = os.path.join(project_root, "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "normalised_listings.json")
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(all_listings, fh, ensure_ascii=False, indent=2)
    logger.info("Wrote %s (%d listings)", output_path, len(all_listings))

    return all_listings


def main():
    parser = argparse.ArgumentParser(description="Normalise scraper results")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    run_normalise(verbose=args.verbose)


if __name__ == "__main__":
    main()
