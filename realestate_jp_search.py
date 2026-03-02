#!/usr/bin/env python3
"""
Real Estate Japan Rental Search Tool

Scrapes realestate.co.jp/en for English-language rental property listings
in target areas around Tokyo. Server-rendered PHP — no JS execution needed.

URL pattern:
  https://realestate.co.jp/en/rent/listing?prefecture={iso}&city={code}&rooms=30&...&page={n}
"""

import datetime
import json
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

from shared.parsers import parse_yen
from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging
from shared.config import Area, get_areas_for_source
from shared.cli import build_arg_parser, filter_areas

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://realestate.co.jp/en/rent/listing"
REQUEST_DELAY = 3  # seconds between page fetches — be respectful (robots.txt)
MAX_PAGES_PER_AREA = 5  # cap at 75 listings per area (15/page)

# rooms=30 means 2LDK minimum (includes 2LDK, 3K, 3DK, 3LDK, etc.)
DEFAULT_PARAMS = {
    "rooms": "30",
    "min_price": "60000",
    "max_price": "200000",
    "building_type": "mansion-apartment",
    "order": "total_monthly_cost_ranking-asc",
}

AREAS = get_areas_for_source("rej")

logger = setup_logging(name="rej-search")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Room:
    layout: str
    building_type: str
    neighborhood: str
    monthly_cost: str
    monthly_cost_value: int
    size: str
    deposit: str
    deposit_value: int
    key_money: str
    key_money_value: int
    floor: str
    year_built: str
    year_built_int: int
    station: str
    detail_url: str


@dataclass
class Property:
    """For Real Estate Japan, each listing is a single unit (no building grouping)."""
    area_name: str
    prefecture: str
    rooms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_year_built(text: str) -> int:
    """Parse '2008' → 2008."""
    if not text:
        return -1
    m = re.search(r"(\d{4})", text)
    return int(m.group(1)) if m else -1


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def build_url(area, page: int = 1) -> str:
    """Build Real Estate Japan search URL."""
    params = dict(DEFAULT_PARAMS)
    params["prefecture"] = area.rej_prefecture
    params["city"] = area.rej_city
    if page > 1:
        params["page"] = str(page)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{BASE_URL}?{query}"


def extract_field_text(listing, label: str) -> str:
    """Extract text value for a labelled field in a listing card.

    The HTML pattern is typically:
      <span>Label</span> <span>Value</span>
    or sometimes the value follows the label span directly.
    """
    # Try finding a span that contains the label text
    for span in listing.find_all("span"):
        span_text = span.get_text(strip=True)
        if span_text == label or label in span_text:
            # Check next sibling
            next_sib = span.find_next_sibling()
            if next_sib:
                return next_sib.get_text(strip=True)
            # Check parent's text after this span
            parent = span.parent
            if parent:
                full_text = parent.get_text(strip=True)
                # Remove the label part
                val = full_text.replace(span_text, "").strip()
                if val:
                    return val
    return ""


def parse_page(html_content: str) -> list[Room]:
    """Parse a single Real Estate Japan results page into Room objects."""
    soup = BeautifulSoup(html_content, "html.parser")
    rooms = []

    for listing in soup.select("div.property-listing"):
        # Layout + type from title
        title_span = listing.select_one(".listing-title span.text-semi-strong")
        title_text = title_span.get_text(strip=True) if title_span else ""
        # "2LDK Apartment" → layout="2LDK", building_type="Apartment"
        parts = title_text.split(None, 1)
        layout = parts[0] if parts else ""
        building_type = parts[1] if len(parts) > 1 else ""

        # Neighborhood
        title_el = listing.select_one(".listing-title")
        neighborhood = ""
        if title_el:
            # Get all direct spans that are not the title span
            spans = title_el.select("span")
            for s in spans:
                if "text-semi-strong" not in (s.get("class") or []):
                    t = s.get_text(strip=True)
                    if t and "in " in t:
                        neighborhood = t.replace("in ", "")
                        break
            if not neighborhood:
                # Fallback: get text after the strong span
                full = title_el.get_text("\n", strip=True)
                lines = full.split("\n")
                if len(lines) > 1:
                    neighborhood = lines[-1].strip()

        # Field values
        monthly_cost_text = extract_field_text(listing, "Monthly Costs")
        size_text = extract_field_text(listing, "Size")
        deposit_text = extract_field_text(listing, "Deposit")
        key_money_text = extract_field_text(listing, "Key Money")
        floor_text = extract_field_text(listing, "Floor")
        year_built_text = extract_field_text(listing, "Year Built")
        station_text = extract_field_text(listing, "Nearest Station")

        monthly_cost_value = parse_yen(monthly_cost_text)
        deposit_value = parse_yen(deposit_text)
        key_money_value = parse_yen(key_money_text)
        year_built_int = parse_year_built(year_built_text)

        # Detail link
        detail_link = listing.select_one('a[href*="/en/rent/view/"]')
        detail_url = ""
        if detail_link and detail_link.get("href"):
            href = detail_link["href"]
            if href.startswith("/"):
                detail_url = f"https://realestate.co.jp{href}"
            else:
                detail_url = href

        if not layout:
            continue  # Skip if we couldn't parse the listing

        rooms.append(Room(
            layout=layout,
            building_type=building_type,
            neighborhood=neighborhood,
            monthly_cost=monthly_cost_text,
            monthly_cost_value=monthly_cost_value,
            size=size_text,
            deposit=deposit_text,
            deposit_value=deposit_value,
            key_money=key_money_text,
            key_money_value=key_money_value,
            floor=floor_text,
            year_built=year_built_text,
            year_built_int=year_built_int,
            station=station_text,
            detail_url=detail_url,
        ))

    return rooms


def search_area(area: "Area", session: requests.Session) -> list[Room]:
    """Scrape all pages for an area (up to MAX_PAGES_PER_AREA)."""
    all_rooms = []

    for page_num in range(1, MAX_PAGES_PER_AREA + 1):
        url = build_url(area, page_num)

        try:
            resp = fetch_page(session, url, allow_redirects=True)
        except requests.RequestException as e:
            logger.error("Request failed (page %d): %s", page_num, e)
            break

        rooms = parse_page(resp.text)
        if not rooms:
            if page_num == 1:
                logger.info("  No listings found")
            break

        all_rooms.extend(rooms)
        logger.info("  Page %d: %d listings", page_num, len(rooms))

        # If fewer than 15 results, no more pages
        if len(rooms) < 15:
            break

        if page_num < MAX_PAGES_PER_AREA:
            time.sleep(REQUEST_DELAY)

    return all_rooms


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(all_areas: dict[str, list[Room]]):
    """Print formatted table of results grouped by area."""
    total_rooms = sum(len(rooms) for rooms in all_areas.values())
    if total_rooms == 0:
        print("\nNo listings found.")
        return

    print(f"\n{'='*110}")
    print(f"Real Estate Japan Search Results - {total_rooms} listings across {len(all_areas)} areas")
    print(f"{'='*110}")

    for area_name, rooms in all_areas.items():
        if not rooms:
            continue
        print(f"\n--- {area_name} ({len(rooms)} listings) ---\n")

        table_rows = []
        for room in rooms:
            cost_display = f"Y{room.monthly_cost_value:,}" if room.monthly_cost_value > 0 else "TBD"
            move_in = room.monthly_cost_value + room.deposit_value + room.key_money_value
            move_in_display = f"Y{move_in:,}" if room.monthly_cost_value > 0 else "TBD"
            table_rows.append([
                room.layout,
                room.neighborhood[:30],
                room.station[:35] if room.station else "",
                room.size,
                room.floor,
                cost_display,
                room.deposit,
                room.key_money,
                move_in_display,
                room.year_built,
            ])

        print(tabulate(
            table_rows,
            headers=["Type", "Neighborhood", "Station", "Size", "Floor",
                     "Monthly", "Deposit", "Key$", "Move-in", "Built"],
            tablefmt="simple",
        ))

    print(f"\n{'='*110}")


def save_results(all_areas: dict[str, list[Room]], area_lookup: dict,
                 filename: str = "results_realestate_jp.json"):
    """Save structured results to JSON, compatible with viewer.html."""
    total_rooms = sum(len(rooms) for rooms in all_areas.values())

    data = {
        "source": "realestate_jp",
        "search_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "room_type_filter": ["2LDK+"],
        "total_properties": total_rooms,  # Each listing is a unit
        "total_rooms": total_rooms,
        "areas": {},
    }

    for area_name, rooms in all_areas.items():
        if not rooms:
            continue
        area_info = area_lookup.get(area_name)
        pref = area_info.prefecture if area_info else "unknown"

        listings = []
        for room in rooms:
            listing = {
                "name": f"{room.layout} {room.building_type}".strip(),
                "address": room.neighborhood,
                "access": room.station,
                "building_age": room.year_built,
                "building_age_years": (datetime.datetime.now().year - room.year_built_int) if room.year_built_int > 0 else -1,
                "rooms": [{
                    "floor": room.floor,
                    "rent": room.monthly_cost,
                    "rent_value": room.monthly_cost_value,
                    "admin_fee": "",
                    "admin_fee_value": 0,
                    "total_value": room.monthly_cost_value,
                    "deposit": room.deposit,
                    "deposit_value": room.deposit_value,
                    "key_money": room.key_money,
                    "key_money_value": room.key_money_value,
                    "layout": room.layout,
                    "size": room.size,
                    "detail_url": room.detail_url,
                }],
            }
            listings.append(listing)

        data["areas"][area_name] = listings

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {filename}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global REQUEST_DELAY, MAX_PAGES_PER_AREA
    parser = build_arg_parser("rej-search", "Search Real Estate Japan rental listings")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")
        for h in logger.handlers:
            h.setLevel("DEBUG")

    areas = filter_areas(AREAS, args.areas)
    if args.max_pages is not None:
        MAX_PAGES_PER_AREA = args.max_pages
    if args.delay is not None:
        REQUEST_DELAY = args.delay
    output_file = args.output or "results_realestate_jp.json"

    logger.info("Real Estate Japan Rental Search")
    logger.info("Searching %d areas (max %d pages each)...", len(areas), MAX_PAGES_PER_AREA)
    logger.info("Filter: 2LDK+, ¥60,000-¥200,000, Mansion/Apartment")

    if args.dry_run:
        for area in areas:
            logger.info("[DRY RUN] %s", build_url(area))
        return

    session = create_session(extra_headers={
        "Accept-Language": "en-US,en;q=0.9",
    })

    all_areas: dict[str, list[Room]] = {}
    area_lookup: dict[str, dict] = {}

    for i, area in enumerate(areas):
        logger.info("[%s] Searching...", area.name)
        area_lookup[area.name] = area

        rooms = search_area(area, session)
        all_areas[area.name] = rooms

        if rooms:
            logger.info("  Total: %d listings", len(rooms))
        else:
            logger.info("  No listings")

        # Rate limiting between areas
        if i < len(areas) - 1:
            time.sleep(REQUEST_DELAY)

    print_results(all_areas)
    save_results(all_areas, area_lookup, output_file)


if __name__ == "__main__":
    main()
