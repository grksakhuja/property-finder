#!/usr/bin/env python3
"""
pipeline/generate_profiles.py — Framework for AI neighbourhood profiles.

Defines schema, validation, and I/O helpers for neighbourhood profiles.
Does NOT generate actual profiles — that is done interactively by Claude Code
in a separate session.

Usage:
    python pipeline/generate_profiles.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from typing import Dict, List

# Ensure project root is on sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.config import AREAS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILE_DIMENSIONS = [
    "safety",
    "foreigner_friendliness",
    "daily_convenience",
    "noise_atmosphere",
    "local_character",
    "transport_connectivity",
]

VALID_CONFIDENCE_LEVELS = ("high", "medium", "low")

VALID_RATING_RANGE = range(1, 6)  # 1-5 inclusive

PROFILES_FILENAME = "neighbourhood_profiles.json"
PROFILES_DIR = "data"


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def get_profile_schema() -> dict:
    """Return a dict describing all expected fields for a single profile.

    Each key maps to its expected Python type. Nested dicts describe
    sub-structures. This is used by validate_profile() to check completeness.
    """
    dimension_schema = {"rating": int, "narrative": str}
    return {
        "area_en": str,
        "area_jp": str,
        "prefecture": str,
        "generated_date": str,
        "confidence": str,
        "summary": str,
        "dimensions": {dim: dict(dimension_schema) for dim in PROFILE_DIMENSIONS},
        "sources_consulted": int,
        "notable_points": list,
    }


def get_all_area_names() -> List[str]:
    """Return a list of all area names from the AREAS config."""
    return [area.name for area in AREAS]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_profile(profile: dict, area_name: str) -> List[str]:
    """Validate a single profile dict against the expected schema.

    Returns a list of error strings (empty if valid).
    """
    errors: List[str] = []
    schema = get_profile_schema()

    # Check top-level required fields
    for field, expected_type in schema.items():
        if field == "dimensions":
            continue  # handled separately below
        if field not in profile:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(profile[field], expected_type):
            errors.append(
                f"Field '{field}' should be {expected_type.__name__}, "
                f"got {type(profile[field]).__name__}"
            )

    # Validate confidence level
    if "confidence" in profile and profile["confidence"] not in VALID_CONFIDENCE_LEVELS:
        errors.append(
            f"Invalid confidence '{profile['confidence']}', "
            f"must be one of {VALID_CONFIDENCE_LEVELS}"
        )

    # Validate dimensions
    if "dimensions" not in profile:
        errors.append("Missing required field: dimensions")
    elif not isinstance(profile["dimensions"], dict):
        errors.append("Field 'dimensions' should be dict")
    else:
        dims = profile["dimensions"]
        for dim_name in PROFILE_DIMENSIONS:
            if dim_name not in dims:
                errors.append(f"Missing dimension: {dim_name}")
            elif not isinstance(dims[dim_name], dict):
                errors.append(f"Dimension '{dim_name}' should be dict")
            else:
                dim = dims[dim_name]
                if "rating" not in dim:
                    errors.append(f"Dimension '{dim_name}' missing 'rating'")
                elif not isinstance(dim["rating"], int):
                    errors.append(
                        f"Dimension '{dim_name}' rating should be int, "
                        f"got {type(dim['rating']).__name__}"
                    )
                elif dim["rating"] not in VALID_RATING_RANGE:
                    errors.append(
                        f"Dimension '{dim_name}' rating {dim['rating']} "
                        f"out of range 1-5"
                    )
                if "narrative" not in dim:
                    errors.append(f"Dimension '{dim_name}' missing 'narrative'")
                elif not isinstance(dim["narrative"], str):
                    errors.append(
                        f"Dimension '{dim_name}' narrative should be str, "
                        f"got {type(dim['narrative']).__name__}"
                    )

        # Flag unexpected dimensions
        for dim_name in dims:
            if dim_name not in PROFILE_DIMENSIONS:
                errors.append(f"Unexpected dimension: {dim_name}")

    return errors


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _profiles_path(project_root: str) -> str:
    """Return the full path to the profiles JSON file."""
    return os.path.join(project_root, PROFILES_DIR, PROFILES_FILENAME)


def load_profiles(project_root: str) -> Dict[str, dict]:
    """Load neighbourhood profiles from data/neighbourhood_profiles.json.

    Returns an empty dict if the file does not exist.
    """
    path = _profiles_path(project_root)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profiles(profiles: dict, project_root: str) -> None:
    """Save profiles to data/neighbourhood_profiles.json.

    Creates the data/ directory if it does not exist.
    """
    path = _profiles_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def get_missing_areas(profiles: dict) -> List[str]:
    """Return area names that are not yet profiled."""
    all_names = get_all_area_names()
    return [name for name in all_names if name not in profiles]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Print summary of profiled vs missing areas."""
    all_names = get_all_area_names()
    profiles = load_profiles(PROJECT_ROOT)
    missing = get_missing_areas(profiles)

    print(f"Total areas:    {len(all_names)}")
    print(f"Profiled:       {len(profiles)}")
    print(f"Missing:        {len(missing)}")

    if missing:
        print("\nMissing areas:")
        for name in missing:
            print(f"  - {name}")
    else:
        print("\nAll areas profiled!")

    # Validate existing profiles
    validation_errors = 0
    for area_name, profile in profiles.items():
        errs = validate_profile(profile, area_name)
        if errs:
            validation_errors += len(errs)
            print(f"\nValidation errors for '{area_name}':")
            for err in errs:
                print(f"  - {err}")

    if profiles and validation_errors == 0:
        print("\nAll existing profiles pass validation.")
    elif validation_errors > 0:
        print(f"\n{validation_errors} validation error(s) found.")


if __name__ == "__main__":
    main()
