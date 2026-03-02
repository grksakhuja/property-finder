"""Shared CLI argument parser for scrapers."""

import argparse


def build_arg_parser(prog: str, description: str) -> argparse.ArgumentParser:
    """Build an ArgumentParser with common scraper flags.

    Args:
        prog: Program name (e.g. "suumo-search").
        description: One-line description.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--areas", nargs="+", metavar="NAME",
        help="Filter to specific area names (partial match)")
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Override max pages per area")
    parser.add_argument(
        "--delay", type=float, default=None,
        help="Override request delay in seconds")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Override output JSON filename")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show URLs without fetching")
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Number of parallel workers for area scraping (default: scraper-specific)")
    return parser


def filter_areas(areas, names):
    """Filter areas list by partial name match against user-provided names."""
    if not names:
        return areas
    result = []
    for area in areas:
        if any(n.lower() in area.name.lower() for n in names):
            result.append(area)
    return result
