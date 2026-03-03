#!/usr/bin/env python3
"""
SUUMO Rental Search Tool

Scrapes suumo.jp for rental property listings in target areas around Tokyo.
Uses server-rendered HTML — no JS execution needed.

URL pattern: https://suumo.jp/chintai/{prefecture}/sc_{city}/?md=07&pc=50&page={n}
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

from shared.parsers import parse_yen, parse_building_age, parse_size_sqm
from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging
from shared.config import Area, get_areas_for_source, get_target_room_types
from shared.cli import build_arg_parser, filter_areas
from shared.scraper_template import safe_write_json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://suumo.jp/chintai"
REQUEST_DELAY = 0.5  # seconds between page fetches
MAX_PAGES_PER_AREA = 5  # cap at 250 listings per area (50/page)
DEFAULT_WORKERS = 3  # parallel workers for area scraping

# Room type codes for SUUMO md parameter
# md=07 → 2LDK, md=08 → 3K, md=09 → 3DK, md=10 → 3LDK
ROOM_TYPE_CODES = ["07", "08", "09", "10"]
ROOM_TYPE_FILTER = get_target_room_types()

SOURCE_AREAS = get_areas_for_source("suumo")

logger = setup_logging(name="suumo-search")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Room:
    floor: str
    rent: str
    rent_value: int
    admin_fee: str
    admin_fee_value: int
    total_value: int
    deposit: str
    deposit_value: int
    key_money: str
    key_money_value: int
    layout: str
    size: str
    detail_url: str


@dataclass
class Property:
    name: str
    address: str
    access: str
    building_age: str
    building_age_years: int
    total_floors: str
    area_name: str
    prefecture: str
    rooms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def build_url(area, page: int = 1) -> str:
    """Build SUUMO search URL for an area + page."""
    prefecture = quote(area.prefecture, safe="")
    code = quote(area.suumo_code, safe="")
    md_params = "&".join(f"md={c}" for c in ROOM_TYPE_CODES)
    url = f"{BASE_URL}/{prefecture}/{code}/?{md_params}&pc=50"
    if page > 1:
        url += f"&page={page}"
    return url


def get_total_count(soup: BeautifulSoup) -> int:
    """Extract total listing count from pagination, e.g. '7,492件'."""
    hit_el = soup.select_one(".paginate_set-hit")
    if hit_el:
        text = hit_el.get_text(strip=True)
        digits = re.sub(r"[^\d]", "", text)
        if digits:
            return int(digits)
    return 0


def parse_page(html_content: str, area: "Area") -> list[Property]:
    """Parse a single SUUMO results page into Property objects."""
    soup = BeautifulSoup(html_content, "html.parser")
    properties = []

    for cassette in soup.select("div.cassetteitem"):
        # Building-level data
        name_el = cassette.select_one(".cassetteitem_content-title")
        name = name_el.get_text(strip=True) if name_el else ""

        addr_el = cassette.select_one(".cassetteitem_detail-col1")
        address = addr_el.get_text(strip=True) if addr_el else ""

        access_els = cassette.select(".cassetteitem_detail-col2 .cassetteitem_detail-text")
        access_lines = [el.get_text(strip=True) for el in access_els]
        access = " / ".join(access_lines)

        col3 = cassette.select(".cassetteitem_detail-col3 div")
        building_age_text = col3[0].get_text(strip=True) if len(col3) > 0 else ""
        total_floors_text = col3[1].get_text(strip=True) if len(col3) > 1 else ""
        building_age_years = parse_building_age(building_age_text)

        # Unit-level data (rows in table)
        rooms = []
        for row in cassette.select("table.cassetteitem_other tbody tr"):
            tds = row.select("td")
            if len(tds) < 9:
                continue

            floor_text = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            rent_el = row.select_one(".cassetteitem_price--rent .cassetteitem_other-emphasis")
            rent_text = rent_el.get_text(strip=True) if rent_el else ""
            rent_value = parse_yen(rent_text)

            admin_el = row.select_one(".cassetteitem_price--administration")
            admin_text = admin_el.get_text(strip=True) if admin_el else ""
            admin_value = parse_yen(admin_text)

            deposit_el = row.select_one(".cassetteitem_price--deposit")
            deposit_text = deposit_el.get_text(strip=True) if deposit_el else ""
            deposit_value = parse_yen(deposit_text)

            key_el = row.select_one(".cassetteitem_price--gratuity")
            key_text = key_el.get_text(strip=True) if key_el else ""
            key_value = parse_yen(key_text)

            layout_el = row.select_one(".cassetteitem_madori")
            layout_text = layout_el.get_text(strip=True) if layout_el else ""

            size_el = row.select_one(".cassetteitem_menseki")
            size_text = size_el.get_text(strip=True) if size_el else ""

            # Detail link
            link_el = row.select_one("a.js-cassette_link_href[href]")
            detail_url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    detail_url = f"https://suumo.jp{href}"
                else:
                    detail_url = href

            # Filter by room type
            if ROOM_TYPE_FILTER:
                if not any(ft in layout_text for ft in ROOM_TYPE_FILTER):
                    continue

            total_value = rent_value + admin_value

            rooms.append(Room(
                floor=floor_text,
                rent=rent_text,
                rent_value=rent_value,
                admin_fee=admin_text,
                admin_fee_value=admin_value,
                total_value=total_value,
                deposit=deposit_text,
                deposit_value=deposit_value,
                key_money=key_text,
                key_money_value=key_value,
                layout=layout_text,
                size=size_text,
                detail_url=detail_url,
            ))

        if rooms:
            properties.append(Property(
                name=name,
                address=address,
                access=access,
                building_age=building_age_text,
                building_age_years=building_age_years,
                total_floors=total_floors_text,
                area_name=area.name,
                prefecture=area.prefecture,
                rooms=rooms,
            ))

    return properties


def search_area(area: "Area", session: requests.Session, *,
                max_pages: int = 0, delay: float = 0) -> list[Property]:
    """Scrape all pages for an area (up to max_pages)."""
    if max_pages <= 0:
        max_pages = MAX_PAGES_PER_AREA
    if delay <= 0:
        delay = REQUEST_DELAY
    all_properties = []

    for page_num in range(1, max_pages + 1):
        url = build_url(area, page_num)

        try:
            resp = fetch_page(session, url)
        except requests.RequestException as e:
            logger.error("Request failed (page %d): %s", page_num, e)
            break

        properties = parse_page(resp.text, area)
        if not properties:
            if page_num == 1:
                logger.info("  No listings found")
            break

        all_properties.extend(properties)
        room_count = sum(len(p.rooms) for p in properties)
        logger.info("  Page %d: %d buildings, %d units", page_num, len(properties), room_count)

        # Check if there are more pages
        soup = BeautifulSoup(resp.text, "html.parser")
        total = get_total_count(soup)
        fetched_so_far = page_num * 50
        if total == 0 or fetched_so_far >= total:
            break

        if page_num < max_pages:
            time.sleep(delay)

    return all_properties


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(all_properties: list[Property]):
    """Print formatted table of results grouped by area."""
    if not all_properties:
        print("\nNo listings found.")
        return

    by_area: dict[str, list[Property]] = {}
    for prop in all_properties:
        by_area.setdefault(prop.area_name, []).append(prop)

    total_rooms = sum(len(p.rooms) for p in all_properties)
    print(f"\n{'='*100}")
    filter_str = f" [{', '.join(ROOM_TYPE_FILTER)}]" if ROOM_TYPE_FILTER else ""
    print(f"SUUMO Search Results{filter_str} - {len(all_properties)} buildings, {total_rooms} units")
    print(f"{'='*100}")

    for area_name, props in by_area.items():
        area_rooms = sum(len(p.rooms) for p in props)
        if area_rooms == 0:
            continue
        print(f"\n--- {area_name} ({len(props)} buildings, {area_rooms} units) ---\n")

        table_rows = []
        for prop in props:
            for room in prop.rooms:
                total_display = f"Y{room.total_value:,}" if room.rent_value > 0 else "TBD"
                move_in = room.rent_value + room.deposit_value + room.key_money_value
                move_in_display = f"Y{move_in:,}" if room.rent_value > 0 else "TBD"
                table_rows.append([
                    prop.name[:25],
                    prop.access.split(" / ")[0][:40] if prop.access else "",
                    room.layout,
                    room.size,
                    room.floor,
                    room.rent,
                    room.admin_fee,
                    total_display,
                    room.deposit,
                    room.key_money,
                    move_in_display,
                    prop.building_age,
                ])

        table_rows.sort(key=lambda r: (0 if r[7] == "TBD" else 1, parse_yen(r[7]) if r[7] != "TBD" else 0))

        print(tabulate(
            table_rows,
            headers=["Property", "Access", "Type", "Size", "Floor",
                     "Rent", "Admin", "Total", "Deposit", "Key$",
                     "Move-in", "Age"],
            tablefmt="simple",
        ))

    print(f"\n{'='*100}")


def save_results(all_properties: list[Property], filename: str = "results_suumo.json"):
    """Save structured results to JSON, compatible with viewer.html."""
    data = {
        "source": "suumo",
        "search_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "room_type_filter": ROOM_TYPE_FILTER,
        "total_properties": len(all_properties),
        "total_rooms": sum(len(p.rooms) for p in all_properties),
        "areas": {},
    }

    for prop in all_properties:
        area = prop.area_name
        if area not in data["areas"]:
            data["areas"][area] = []

        prop_dict = {
            "name": prop.name,
            "address": prop.address,
            "access": prop.access,
            "building_age": prop.building_age,
            "building_age_years": prop.building_age_years,
            "total_floors": prop.total_floors,
            "rooms": [asdict(r) for r in prop.rooms],
        }
        data["areas"][area].append(prop_dict)

    safe_write_json(data, filename)

    print(f"\nResults saved to {filename}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_arg_parser("suumo-search", "Search SUUMO rental listings")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")
        for h in logger.handlers:
            h.setLevel("DEBUG")

    areas = filter_areas(SOURCE_AREAS, args.areas)
    max_pages = args.max_pages if args.max_pages is not None else MAX_PAGES_PER_AREA
    delay = args.delay if args.delay is not None else REQUEST_DELAY
    output_file = args.output or "results_suumo.json"

    logger.info("SUUMO Rental Search")
    if ROOM_TYPE_FILTER:
        logger.info("Filtering for: %s", ", ".join(ROOM_TYPE_FILTER))
    logger.info("Searching %d areas (max %d pages each)...", len(areas), max_pages)

    if args.dry_run:
        for area in areas:
            logger.info("[DRY RUN] %s", build_url(area))
        return

    session = create_session(extra_headers={
        "Accept-Language": "ja,en;q=0.9",
    })

    all_properties: list[Property] = []
    max_workers = args.workers if args.workers is not None else DEFAULT_WORKERS

    def _search_one(area):
        logger.info("[%s] Searching...", area.name)
        return area, search_area(area, session, max_pages=max_pages, delay=delay)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_search_one, area): area for area in areas}
        for future in as_completed(futures):
            area, props = future.result()
            if props:
                room_count = sum(len(p.rooms) for p in props)
                logger.info("[%s] Total: %d buildings with %d units", area.name, len(props), room_count)
                all_properties.extend(props)
            else:
                logger.info("[%s] No listings", area.name)

    print_results(all_properties)
    save_results(all_properties, output_file)


if __name__ == "__main__":
    main()
