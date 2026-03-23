#!/usr/bin/env python3
"""
pipeline/enrich_hazard.py — Enrich normalised listings with hazard data.

Reads data/normalised_listings.json and checks for GIS hazard data in
data/hazard_data/. If no GIS data is available (current stub state), sets
all listings to data_available=false with null risk values.

Future implementation will use shapely for point-in-polygon lookups against
flood and liquefaction shapefiles to classify risk as "low", "moderate",
or "high".

Usage:
    python pipeline/enrich_hazard.py
    python pipeline/enrich_hazard.py --verbose
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys

# Ensure project root is on sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

# Supported GIS file extensions for hazard data
GIS_EXTENSIONS = ("*.shp", "*.geojson", "*.gpkg")

# ---------------------------------------------------------------------------
# Hazard data detection
# ---------------------------------------------------------------------------


def has_hazard_data(project_root: str) -> bool:
    """Check if data/hazard_data/ exists and contains GIS files."""
    hazard_dir = os.path.join(project_root, "data", "hazard_data")
    if not os.path.isdir(hazard_dir):
        logger.debug("Hazard data directory not found: %s", hazard_dir)
        return False

    for ext in GIS_EXTENSIONS:
        matches = glob.glob(os.path.join(hazard_dir, "**", ext), recursive=True)
        if matches:
            logger.debug("Found GIS files: %s", matches[:5])
            return True

    logger.debug("No GIS files found in %s", hazard_dir)
    return False


# ---------------------------------------------------------------------------
# Stub hazard enrichment (no GIS data available)
# ---------------------------------------------------------------------------


def build_stub_hazard() -> dict:
    """Build a stub hazard field when no GIS data is available."""
    return {
        "flood_risk": None,
        "liquefaction_risk": None,
        "data_available": False,
    }


# ---------------------------------------------------------------------------
# Point-in-polygon hazard classification
# ---------------------------------------------------------------------------

VALID_RISK_LEVELS = ("low", "moderate", "high")


def load_hazard_shapes(hazard_dir: str) -> dict[str, list[dict]]:
    """Load GeoJSON files from hazard_dir and return parsed features by type.

    Returns dict mapping hazard type ("flood", "liquefaction") to list of
    dicts with keys: "geometry" (shapely geometry), "risk_level" (str).

    File naming convention: files containing "flood" map to flood_risk,
    files containing "liquefaction" map to liquefaction_risk.
    """
    from shapely.geometry import shape

    result: dict[str, list[dict]] = {"flood": [], "liquefaction": []}

    geojson_files = glob.glob(os.path.join(hazard_dir, "**", "*.geojson"), recursive=True)
    for filepath in geojson_files:
        basename = os.path.basename(filepath).lower()
        if "flood" in basename:
            hazard_type = "flood"
        elif "liquefaction" in basename:
            hazard_type = "liquefaction"
        else:
            logger.debug("Skipping unrecognised hazard file: %s", filepath)
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse %s, skipping", filepath)
            continue

        features = data.get("features", [])
        for feat in features:
            geom_data = feat.get("geometry")
            props = feat.get("properties", {})
            if not geom_data:
                continue
            try:
                geom = shape(geom_data)
            except Exception:
                continue
            risk_level = props.get("risk_level", "moderate")
            if risk_level not in VALID_RISK_LEVELS:
                risk_level = "moderate"
            result[hazard_type].append({"geometry": geom, "risk_level": risk_level})

    logger.debug(
        "Loaded hazard shapes: %d flood, %d liquefaction",
        len(result["flood"]),
        len(result["liquefaction"]),
    )
    return result


def classify_risk(lat: float, lng: float, features: list[dict]) -> str | None:
    """Check if a point falls within any hazard polygon.

    Returns the risk_level of the first containing polygon, or None.
    For overlapping polygons, returns the highest risk level found.
    """
    from shapely.geometry import Point

    if not features:
        return None

    point = Point(lng, lat)  # shapely uses (x, y) = (lng, lat)

    risk_order = {"high": 3, "moderate": 2, "low": 1}
    best_risk = None
    best_rank = 0

    for feat in features:
        if feat["geometry"].contains(point):
            rank = risk_order.get(feat["risk_level"], 0)
            if rank > best_rank:
                best_rank = rank
                best_risk = feat["risk_level"]

    return best_risk


# ---------------------------------------------------------------------------
# Enrichment entry point
# ---------------------------------------------------------------------------


def enrich_hazard(listings: list[dict], project_root: str) -> tuple[int, int]:
    """Enrich listings with hazard data in-place.

    Returns (enriched_count, total_count).
    """
    hazard_dir = os.path.join(project_root, "data", "hazard_data")
    gis_available = has_hazard_data(project_root)

    shapes = None
    if gis_available:
        shapes = load_hazard_shapes(hazard_dir)
        logger.info("Loaded GIS hazard data for classification")

    enriched = 0
    for listing in listings:
        if shapes:
            geocode = listing.get("geocode")
            if geocode and geocode.get("lat") is not None and geocode.get("lng") is not None:
                lat = geocode["lat"]
                lng = geocode["lng"]
                listing["hazard"] = {
                    "flood_risk": classify_risk(lat, lng, shapes["flood"]),
                    "liquefaction_risk": classify_risk(lat, lng, shapes["liquefaction"]),
                    "data_available": True,
                }
            else:
                listing["hazard"] = {
                    "flood_risk": None,
                    "liquefaction_risk": None,
                    "data_available": True,
                }
        else:
            listing["hazard"] = build_stub_hazard()
        enriched += 1

    return enriched, len(listings)


def run_enrich_hazard(
    project_root: str | None = None, verbose: bool = False
) -> list[dict]:
    """Run hazard enrichment pipeline. Returns updated listings."""
    if project_root is None:
        project_root = PROJECT_ROOT

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load listings
    listings_path = os.path.join(project_root, "data", "normalised_listings.json")
    with open(listings_path, "r", encoding="utf-8") as f:
        listings = json.load(f)
    logger.info("Loaded %d listings from %s", len(listings), listings_path)

    # Enrich
    enriched, total = enrich_hazard(listings, project_root)
    logger.info("Enriched %d/%d listings with hazard data (stub)", enriched, total)

    # Write back
    with open(listings_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", listings_path)

    return listings


def main():
    parser = argparse.ArgumentParser(
        description="Enrich normalised listings with hazard data"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    run_enrich_hazard(verbose=args.verbose)


if __name__ == "__main__":
    main()
