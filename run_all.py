#!/usr/bin/env python3
"""
run_all.py — Orchestrator that runs all scrapers in parallel.

Runs UR, SUUMO, Real Estate Japan, and build_pois as independent subprocesses.
Passes through common flags (--verbose, --dry-run, --areas) to each scraper.

Usage:
    python run_all.py                    # run all scrapers in parallel
    python run_all.py -v                 # verbose mode
    python run_all.py --areas Kawaguchi  # filter to one area
    python run_all.py --sequential       # run one at a time (debugging)
"""

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRAPERS = [
    {"name": "UR", "cmd": [sys.executable, "ur_rental_search.py"]},
    {"name": "SUUMO", "cmd": [sys.executable, "suumo_search.py"]},
    {"name": "REJ", "cmd": [sys.executable, "realestate_jp_search.py"]},
    {"name": "BestEstate", "cmd": [sys.executable, "best_estate_search.py"]},
    {"name": "GaijinPot", "cmd": [sys.executable, "gaijinpot_search.py"]},
    {"name": "Wagaya", "cmd": [sys.executable, "wagaya_search.py"]},
    {"name": "VillageHouse", "cmd": [sys.executable, "villagehouse_search.py"]},
    {"name": "POIs", "cmd": [sys.executable, "build_pois.py"]},
]


def build_scraper_args(scraper_name: str, args: argparse.Namespace) -> list[str]:
    """Build extra CLI args to pass through to a scraper subprocess."""
    extra = []
    # build_pois doesn't share the common CLI
    if scraper_name == "POIs":
        return extra
    if args.verbose:
        extra.append("--verbose")
    if args.dry_run:
        extra.append("--dry-run")
    if args.areas:
        extra.extend(["--areas"] + args.areas)
    return extra


def run_scraper(scraper: dict, extra_args: list[str]) -> dict:
    """Run a single scraper subprocess and capture its output."""
    cmd = scraper["cmd"] + extra_args
    name = scraper["name"]
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout per scraper
        )
        elapsed = time.monotonic() - start
        return {
            "name": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed": elapsed,
        }
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return {
            "name": name,
            "returncode": -1,
            "stdout": "",
            "stderr": "TIMEOUT after 600s",
            "elapsed": elapsed,
        }


def main():
    parser = argparse.ArgumentParser(
        prog="run_all",
        description="Run all Tokyo rental scrapers in parallel",
    )
    parser.add_argument(
        "--areas", nargs="+", metavar="NAME",
        help="Filter to specific area names (passed to each scraper)")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose output for each scraper")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Pass --dry-run to each scraper")
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run scrapers sequentially instead of in parallel (for debugging)")
    args = parser.parse_args()

    total_start = time.monotonic()
    print(f"Running {len(SCRAPERS)} scrapers {'sequentially' if args.sequential else 'in parallel'}...")

    results = []

    if args.sequential:
        for scraper in SCRAPERS:
            extra = build_scraper_args(scraper["name"], args)
            print(f"\n--- Starting {scraper['name']} ---")
            result = run_scraper(scraper, extra)
            results.append(result)
            if result["stdout"]:
                print(result["stdout"])
            if result["stderr"]:
                print(result["stderr"], file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=len(SCRAPERS)) as executor:
            futures = {}
            for scraper in SCRAPERS:
                extra = build_scraper_args(scraper["name"], args)
                future = executor.submit(run_scraper, scraper, extra)
                futures[future] = scraper["name"]

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                status = "OK" if result["returncode"] == 0 else "FAILED"
                print(f"  {result['name']}: {status} ({result['elapsed']:.1f}s)")
                if args.verbose and result["stdout"]:
                    print(result["stdout"])
                if result["stderr"] and result["returncode"] != 0:
                    print(result["stderr"], file=sys.stderr)

    total_elapsed = time.monotonic() - total_start

    # Summary
    print(f"\n{'='*60}")
    print(f"Scraper Pipeline Summary ({total_elapsed:.1f}s total)")
    print(f"{'='*60}")
    for r in sorted(results, key=lambda x: x["name"]):
        status = "OK" if r["returncode"] == 0 else f"FAILED (exit {r['returncode']})"
        print(f"  {r['name']:8s}  {status:20s}  {r['elapsed']:.1f}s")

    failed = [r for r in results if r["returncode"] != 0]
    if failed:
        print(f"\n{len(failed)} scraper(s) failed.")
        sys.exit(1)
    else:
        print(f"\nAll {len(results)} scrapers completed successfully.")

    # Run geocoder as final non-fatal step
    print(f"\n{'='*60}")
    print("Running geocoder (non-fatal)...")
    print(f"{'='*60}")
    try:
        geo_result = subprocess.run(
            [sys.executable, "geocode_properties.py"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max
        )
        if geo_result.returncode == 0:
            print("  Geocoder: OK")
            if args.verbose and geo_result.stdout:
                print(geo_result.stdout)
        else:
            print(f"  Geocoder: FAILED (exit {geo_result.returncode})")
            if geo_result.stderr:
                print(geo_result.stderr, file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("  Geocoder: TIMEOUT (30 min)")
    except Exception as exc:
        print(f"  Geocoder: ERROR ({exc})")


if __name__ == "__main__":
    main()
