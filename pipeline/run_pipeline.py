#!/usr/bin/env python3
"""
pipeline/run_pipeline.py — Run the full enrichment pipeline.

Steps:
  1. normalise.py     — normalise raw scraper results
  2. enrich_commute   — attach commute data from config
  3. enrich_amenities — query Overpass for nearby amenities
  4. enrich_hazard    — stub hazard data
  5. score            — percentile-based scoring + grading

Usage:
    python pipeline/run_pipeline.py
    python pipeline/run_pipeline.py --verbose
    python pipeline/run_pipeline.py --skip-amenities  # skip slow Overpass queries
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)


def run_pipeline(
    project_root: str | None = None,
    verbose: bool = False,
    skip_amenities: bool = False,
) -> None:
    """Run all pipeline steps in sequence."""
    if project_root is None:
        project_root = PROJECT_ROOT

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    steps = []

    # Step 1: Normalise
    from pipeline.normalise import run_normalise
    steps.append(("Normalise", lambda: run_normalise(project_root, verbose)))

    # Step 2: Commute enrichment
    from pipeline.enrich_commute import run_enrich_commute
    steps.append(("Enrich Commute", lambda: run_enrich_commute(project_root, verbose)))

    # Step 3: Amenity enrichment (optional — slow due to Overpass queries)
    if not skip_amenities:
        from pipeline.enrich_amenities import run
        steps.append(("Enrich Amenities", lambda: run(limit=200, verbose=verbose)))

    # Step 4: Hazard enrichment (stub)
    from pipeline.enrich_hazard import run_enrich_hazard
    steps.append(("Enrich Hazard", lambda: run_enrich_hazard(project_root, verbose)))

    # Step 5: Scoring
    from pipeline.score import run_score
    steps.append(("Score", lambda: run_score(project_root, verbose)))

    total_start = time.monotonic()

    for step_name, step_fn in steps:
        logger.info("=" * 60)
        logger.info("Running: %s", step_name)
        logger.info("=" * 60)
        start = time.monotonic()
        try:
            step_fn()
            elapsed = time.monotonic() - start
            logger.info("%s completed in %.1fs", step_name, elapsed)
        except Exception:
            logger.exception("%s FAILED", step_name)
            sys.exit(1)

    total = time.monotonic() - total_start
    logger.info("=" * 60)
    logger.info("Pipeline complete in %.1fs", total)
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run full enrichment pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--skip-amenities", action="store_true",
        help="Skip Overpass amenity queries (faster for testing)",
    )
    args = parser.parse_args()
    run_pipeline(verbose=args.verbose, skip_amenities=args.skip_amenities)


if __name__ == "__main__":
    main()
