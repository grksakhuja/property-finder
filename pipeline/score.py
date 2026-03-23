#!/usr/bin/env python3
"""
pipeline/score.py — Compute percentile-based scores for normalised listings.

Reads data/normalised_listings.json (with enrichment fields populated),
optionally data/neighbourhood_profiles.json, and scoring_config.json.
Produces data/scored_listings.json with scores and grades.

Usage:
    python pipeline/score.py
    python pipeline/score.py --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------
def get_grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


# ---------------------------------------------------------------------------
# Percentile computation
# ---------------------------------------------------------------------------
def compute_percentiles(values: list[float], invert: bool = False) -> dict[int, float]:
    """Compute percentile rank (0-100) for each index in the values list.

    Args:
        values: list of non-null numeric values with original indices preserved via tuple
        invert: if True, lower values get higher percentile (e.g. commute time)
    """
    if not values:
        return {}

    # values is list of (original_index, value)
    sorted_items = sorted(values, key=lambda x: x[1])
    n = len(sorted_items)

    percentiles = {}
    for rank, (idx, val) in enumerate(sorted_items):
        if n == 1:
            pct = 50.0
        else:
            pct = (rank / (n - 1)) * 100
        if invert:
            pct = 100 - pct
        percentiles[idx] = round(pct, 1)

    return percentiles


# ---------------------------------------------------------------------------
# Dimension extractors — return (index, value) pairs for non-null data
# ---------------------------------------------------------------------------
def extract_commute_values(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract estimated door-to-door commute time."""
    result = []
    for i, l in enumerate(listings):
        commute = l.get("commute")
        if commute and commute.get("estimated_door_to_door") is not None:
            result.append((i, commute["estimated_door_to_door"]))
    return result


def extract_affordability_values(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract total monthly rent."""
    result = []
    for i, l in enumerate(listings):
        total = l.get("total_monthly")
        if total and total > 0:
            result.append((i, total))
    return result


def extract_space_value(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract yen per sqm (lower is better value)."""
    result = []
    for i, l in enumerate(listings):
        sqm = l.get("size_sqm")
        total = l.get("total_monthly")
        if sqm and sqm > 0 and total and total > 0:
            result.append((i, total / sqm))
    return result


def extract_station_access(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract walk minutes to station."""
    result = []
    for i, l in enumerate(listings):
        walk = l.get("walk_minutes_claimed")
        if walk is not None and walk >= 0:
            result.append((i, walk))
    return result


def extract_move_in_cost(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract move-in cost."""
    result = []
    for i, l in enumerate(listings):
        cost = l.get("move_in_cost")
        if cost is not None and cost >= 0:
            result.append((i, cost))
    return result


def extract_building_quality(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract building age in years (lower age = better quality)."""
    result = []
    for i, l in enumerate(listings):
        age = l.get("building_age_years")
        if age is not None and age >= 0:
            result.append((i, age))
    return result


def extract_daily_convenience(listings: list[dict]) -> list[tuple[int, float]]:
    """Extract a convenience proxy from amenity counts."""
    result = []
    for i, l in enumerate(listings):
        amenities = l.get("amenities")
        if not amenities:
            continue
        # Simple convenience proxy: weighted sum of nearby amenities
        score = (
            (amenities.get("konbini_500m", 0) or 0) * 3
            + (amenities.get("supermarkets_500m", 0) or 0) * 2
            + (amenities.get("clinics_1km", 0) or 0) * 1
            + (amenities.get("parks_500m", 0) or 0) * 1
        )
        result.append((i, score))
    return result


# ---------------------------------------------------------------------------
# Room type scoring (categorical, not percentile)
# ---------------------------------------------------------------------------
def score_room_type(room_type: str | None, config: dict) -> float | None:
    """Score room type from config preferences. Returns 0-100 or None."""
    if not room_type:
        return None
    room_type_prefs = config.get("roomType", {})
    for key, multiplier in room_type_prefs.items():
        if key in (room_type or ""):
            return round(multiplier * 100, 1)
    return 30.0  # default for unknown types


# ---------------------------------------------------------------------------
# Area character scoring (from neighbourhood profiles)
# ---------------------------------------------------------------------------
def score_area_character(area_name: str, profiles: dict) -> float | None:
    """Score area character from neighbourhood profile ratings (1-5 → 0-100)."""
    profile = profiles.get(area_name)
    if not profile:
        return None
    dims = profile.get("dimensions", {})
    if not dims:
        return None
    ratings = [d.get("rating") for d in dims.values() if d.get("rating") is not None]
    if not ratings:
        return None
    avg = sum(ratings) / len(ratings)
    # Convert 1-5 scale to 0-100: (rating - 1) / 4 * 100
    return round((avg - 1) / 4 * 100, 1)


# ---------------------------------------------------------------------------
# Hazard penalty
# ---------------------------------------------------------------------------
def compute_hazard_penalty(listing: dict) -> float:
    """Compute hazard penalty. Returns negative value (0, -5, or -15)."""
    hazard = listing.get("hazard")
    if not hazard or not hazard.get("data_available"):
        return 0
    penalty = 0
    for risk_field in ("flood_risk", "liquefaction_risk"):
        risk = hazard.get(risk_field)
        if risk == "high":
            penalty = min(penalty, -15)
        elif risk == "moderate":
            penalty = min(penalty, -5)
    return penalty


# ---------------------------------------------------------------------------
# Main scoring
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "commute": 20,
    "affordability": 20,
    "space_value": 12,
    "room_type": 8,
    "station_access": 8,
    "move_in_cost": 6,
    "building_quality": 6,
    "daily_convenience": 10,
    "area_character": 10,
}


def score_listings(
    listings: list[dict],
    config: dict,
    profiles: dict | None = None,
    weights: dict | None = None,
) -> list[dict]:
    """Score all listings in-place. Returns the same list.

    Each listing gets a 'scores' dict and a 'grade' string.
    """
    if profiles is None:
        profiles = {}
    if weights is None:
        weights = config.get("weights", {})
        # Prefer new dimension weight keys, fallback to defaults
        w = {}
        for dim in DEFAULT_WEIGHTS:
            w[dim] = weights.get(dim, DEFAULT_WEIGHTS[dim])
        weights = w

    # Step 1: Compute percentiles for continuous dimensions
    dim_extractors = {
        "commute": (extract_commute_values, True),       # lower is better
        "affordability": (extract_affordability_values, True),  # lower is better
        "space_value": (extract_space_value, True),       # lower yen/sqm is better
        "station_access": (extract_station_access, True), # lower walk is better
        "move_in_cost": (extract_move_in_cost, True),     # lower is better
        "building_quality": (extract_building_quality, True),  # lower age is better
        "daily_convenience": (extract_daily_convenience, False),  # higher is better
    }

    percentile_scores: dict[str, dict[int, float]] = {}
    for dim_name, (extractor, invert) in dim_extractors.items():
        values = extractor(listings)
        percentile_scores[dim_name] = compute_percentiles(values, invert=invert)

    # Step 2: Compute scores for each listing
    total_dimensions = len(DEFAULT_WEIGHTS)
    for i, listing in enumerate(listings):
        scores: dict[str, float | None] = {}
        scored_count = 0

        # Continuous dimensions from percentiles
        for dim_name in dim_extractors:
            pct = percentile_scores[dim_name].get(i)
            scores[dim_name] = pct
            if pct is not None:
                scored_count += 1

        # Room type (categorical)
        rt_score = score_room_type(listing.get("room_type"), config)
        scores["room_type"] = rt_score
        if rt_score is not None:
            scored_count += 1

        # Area character (from profiles)
        ac_score = score_area_character(listing.get("area_name", ""), profiles)
        scores["area_character"] = ac_score
        if ac_score is not None:
            scored_count += 1

        # Hazard penalty
        penalty = compute_hazard_penalty(listing)
        scores["hazard_penalty"] = penalty

        # Composite score: weighted average of available sub-scores
        weighted_sum = 0
        weight_sum = 0
        for dim_name in DEFAULT_WEIGHTS:
            sub = scores.get(dim_name)
            if sub is not None:
                w = weights.get(dim_name, 0)
                weighted_sum += sub * w
                weight_sum += w

        composite = 0.0
        if weight_sum > 0:
            composite = (weighted_sum / weight_sum) + penalty
            composite = max(0, min(100, composite))
        composite = round(composite, 1)

        scores["composite"] = composite
        scores["scored_dimensions"] = scored_count
        scores["total_dimensions"] = total_dimensions

        listing["scores"] = scores
        listing["grade"] = get_grade(composite)

    return listings


def run_score(project_root: str | None = None, verbose: bool = False) -> list[dict]:
    """Run the scoring pipeline. Returns scored listings."""
    if project_root is None:
        project_root = PROJECT_ROOT

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load normalised listings
    listings_path = os.path.join(project_root, "data", "normalised_listings.json")
    with open(listings_path, "r", encoding="utf-8") as f:
        listings = json.load(f)
    logger.info("Loaded %d listings", len(listings))

    # Load scoring config
    config_path = os.path.join(project_root, "scoring_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Load neighbourhood profiles (optional)
    profiles = {}
    profiles_path = os.path.join(project_root, "data", "neighbourhood_profiles.json")
    if os.path.exists(profiles_path):
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        logger.info("Loaded %d neighbourhood profiles", len(profiles))

    # Score
    score_listings(listings, config, profiles)

    # Stats
    grades = {}
    for l in listings:
        g = l.get("grade", "?")
        grades[g] = grades.get(g, 0) + 1
    logger.info("Grade distribution: %s", grades)

    # Write output
    output_path = os.path.join(project_root, "data", "scored_listings.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s (%d listings)", output_path, len(listings))

    return listings


def main():
    parser = argparse.ArgumentParser(description="Score normalised listings")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    run_score(verbose=args.verbose)


if __name__ == "__main__":
    main()
