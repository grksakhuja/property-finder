#!/usr/bin/env python3
"""
pipeline/enrich_commute.py — Enrich normalised listings with commute data.

Reads data/normalised_listings.json and scoring_config.json, populates the
`commute` field on each listing from config lookup (known areas or prefecture
defaults), then writes the updated listings back.

Usage:
    python pipeline/enrich_commute.py
    python pipeline/enrich_commute.py --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Ensure project root is on sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

DEFAULT_WALK_MINUTES = 10


def load_commute_config(project_root: str) -> dict:
    """Load commute section from scoring_config.json."""
    config_path = os.path.join(project_root, "scoring_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["commute"]


def build_commute_field(listing: dict, known: dict, prefecture_defaults: dict) -> dict:
    """Build commute field for a single listing.

    Looks up area_en in known, falls back to prefecture in prefectureDefault.
    Returns the commute dict to attach to the listing.
    """
    area_en = listing.get("area_en", "")
    prefecture = listing.get("prefecture", "")

    entry = known.get(area_en)
    if entry:
        total_minutes = entry["min"]
        transfers = entry["transfers"]
        line = entry.get("line")
    else:
        pref_entry = prefecture_defaults.get(prefecture)
        if pref_entry:
            total_minutes = pref_entry["min"]
            transfers = pref_entry["transfers"]
            line = pref_entry.get("line")
        else:
            logger.warning(
                "No commute data for area_en=%r prefecture=%r", area_en, prefecture
            )
            return None

    walk_claimed = listing.get("walk_minutes_claimed", -1)
    if walk_claimed == -1:
        walk_claimed = DEFAULT_WALK_MINUTES

    return {
        "total_minutes": total_minutes,
        "transfers": transfers,
        "line": line,
        "walk_to_station_claimed": walk_claimed,
        "estimated_door_to_door": walk_claimed + total_minutes,
        "source": "config_lookup",
    }


def enrich_commute(
    listings: list[dict], commute_config: dict
) -> tuple[int, int, int]:
    """Enrich listings with commute data in-place.

    Returns (enriched_count, skipped_count, total_count).
    """
    known = commute_config.get("known", {})
    prefecture_defaults = commute_config.get("prefectureDefault", {})

    enriched = 0
    skipped = 0
    for listing in listings:
        commute = build_commute_field(listing, known, prefecture_defaults)
        if commute:
            listing["commute"] = commute
            enriched += 1
        else:
            skipped += 1

    return enriched, skipped, len(listings)


def run_enrich_commute(
    project_root: str | None = None, verbose: bool = False
) -> list[dict]:
    """Run commute enrichment pipeline. Returns updated listings."""
    if project_root is None:
        project_root = PROJECT_ROOT

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load inputs
    listings_path = os.path.join(project_root, "data", "normalised_listings.json")
    with open(listings_path, "r", encoding="utf-8") as f:
        listings = json.load(f)
    logger.info("Loaded %d listings from %s", len(listings), listings_path)

    commute_config = load_commute_config(project_root)
    logger.info(
        "Loaded commute config: %d known areas, %d prefecture defaults",
        len(commute_config.get("known", {})),
        len(commute_config.get("prefectureDefault", {})),
    )

    # Enrich
    enriched, skipped, total = enrich_commute(listings, commute_config)
    logger.info(
        "Enriched %d/%d listings (%d skipped)", enriched, total, skipped
    )

    # Write back
    with open(listings_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", listings_path)

    return listings


def main():
    parser = argparse.ArgumentParser(
        description="Enrich normalised listings with commute data"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    run_enrich_commute(verbose=args.verbose)


if __name__ == "__main__":
    main()
