#!/usr/bin/env python3
"""
UR Housing Rental Price Search Tool

Queries the UR (Urban Renaissance Agency) public API to find available
rental properties and their prices in target areas around Tokyo.

API base: https://chintai.r6.ur-net.go.jp/chintai/api/
Endpoint: bukken/result/bukken_result/ (POST, form data)
"""

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict

import requests
from tabulate import tabulate

from shared.parsers import parse_yen
from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging
from shared.config import Area, get_areas_for_source, get_target_room_types
from shared.cli import build_arg_parser, filter_areas
from shared.scraper_template import safe_write_json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "https://chintai.r6.ur-net.go.jp/chintai/api"
SITE_URL = "https://www.ur-net.go.jp"
REQUEST_DELAY = 0  # seconds between API calls (JSON API, very fast)
DEFAULT_WORKERS = 5  # parallel workers for area scraping

# Prefecture code mapping (tdfk uses JIS prefecture codes):
# 11 = Saitama, 12 = Chiba, 13 = Tokyo, 14 = Kanagawa

# Room type filter — loaded from scoring_config.json
ROOM_TYPE_FILTER = get_target_room_types()

AREAS = get_areas_for_source("ur")

logger = setup_logging(name="ur-search")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Room:
    room_id: str
    room_name: str
    room_type: str
    floor: str
    floorspace: str
    rent: str
    rent_value: int
    commonfee: str
    commonfee_value: int
    total_value: int
    shikikin: str
    url: str = ""


@dataclass
class Property:
    shisya: str
    danchi: str
    shikibetu: str
    name: str
    address: str
    traffic: str
    area_name: str
    tdfk_name: str = ""
    rooms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_traffic(text: str) -> str:
    """Extract station access lines from HTML like '<li>JR...駅 徒歩12分</li>'."""
    if not text:
        return ""
    # Extract text from each <li>
    lines = re.findall(r"<li>(.*?)</li>", text, re.DOTALL)
    if lines:
        return " / ".join(html.unescape(line.strip()) for line in lines)
    # Fallback: strip all tags
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text).strip()


def clean_floorspace(text: str) -> str:
    """Convert HTML entities in floorspace like '50&#13217;' to '50㎡'."""
    if not text:
        return ""
    return html.unescape(text)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def search_area(area: "Area", session: requests.Session) -> list[Property]:
    """
    Query the bukken_result API for an area.
    Returns a list of Property objects with their vacant rooms.
    """
    url = f"{API_URL}/bukken/result/bukken_result/"
    data = {
        "mode": "area",
        "skcs": area.ur_skcs,
        "block": area.ur_block,
        "tdfk": area.ur_tdfk,
        "orderByField": "0",
        "pageSize": "100",
        "pageIndex": "0",
        "shisya": "",
        "danchi": "",
        "shikibetu": "",
        "pageIndexRoom": "0",
        "sp": "",
    }

    try:
        resp = fetch_page(session, url, method="POST", data=data)
        result = resp.json()
    except requests.RequestException as e:
        logger.error("API request failed: %s", e)
        return []
    except json.JSONDecodeError:
        logger.error("Invalid JSON response")
        return []

    if not result or not isinstance(result, list):
        return []

    properties = []
    for item in result:
        rooms_data = item.get("room", [])
        if not rooms_data:
            continue  # No vacancies on this property at all

        rooms = []
        for r in rooms_data:
            room_type = r.get("type", "")

            # Filter by room type if configured
            if ROOM_TYPE_FILTER:
                if not any(ft in room_type for ft in ROOM_TYPE_FILTER):
                    continue

            rent_str = r.get("rent", "")
            fee_str = r.get("commonfee", "")
            rent_val = parse_yen(rent_str)
            fee_val = parse_yen(fee_str)

            room_name_parts = []
            if r.get("roomNmMain"):
                room_name_parts.append(r["roomNmMain"])
            if r.get("roomNmSub"):
                room_name_parts.append(r["roomNmSub"])

            room_link = r.get("roomLinkPc", r.get("roomDetailLink", ""))
            room_url = f"{SITE_URL}{room_link}" if room_link else ""

            rooms.append(Room(
                room_id=r.get("id", ""),
                room_name=" ".join(room_name_parts) if room_name_parts else "",
                room_type=room_type,
                floor=r.get("floor", ""),
                floorspace=clean_floorspace(r.get("floorspace", "")),
                rent=rent_str,
                rent_value=rent_val,
                commonfee=fee_str,
                commonfee_value=fee_val,
                total_value=rent_val + fee_val,
                shikikin=item.get("shikikin", ""),
                url=room_url,
            ))

        if not rooms:
            continue  # Had rooms but none matched the filter

        prop = Property(
            shisya=item.get("shisya", ""),
            danchi=item.get("danchi", ""),
            shikibetu=item.get("shikibetu", ""),
            name=item.get("danchiNm", ""),
            address=item.get("place", ""),
            traffic=clean_traffic(item.get("traffic", "")),
            area_name=area.name,
            tdfk_name=area.prefecture,
            rooms=rooms,
        )
        properties.append(prop)

    return properties


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(all_properties: list[Property]):
    """Print formatted table of results grouped by area."""
    if not all_properties:
        print("\nNo vacant properties found.")
        return

    by_area: dict[str, list[Property]] = {}
    for prop in all_properties:
        by_area.setdefault(prop.area_name, []).append(prop)

    total_rooms = sum(len(p.rooms) for p in all_properties)
    print(f"\n{'='*90}")
    filter_str = f" [{', '.join(ROOM_TYPE_FILTER)}]" if ROOM_TYPE_FILTER else ""
    print(f"UR Housing Search Results{filter_str} - {len(all_properties)} properties, {total_rooms} vacant rooms")
    print(f"{'='*90}")

    for area_name, props in by_area.items():
        area_rooms = sum(len(p.rooms) for p in props)
        if area_rooms == 0:
            continue
        print(f"\n--- {area_name} ({len(props)} properties, {area_rooms} rooms) ---\n")

        table_rows = []
        room_urls = []
        for prop in props:
            for room in prop.rooms:
                rent_display = room.rent if room.rent else "お問合せ"
                total_display = f"Y{room.total_value:,}" if room.rent_value > 0 else "TBD"
                table_rows.append([
                    prop.name[:25],
                    prop.traffic.split(" / ")[0][:40] if prop.traffic else "",
                    room.room_name[:15] if room.room_name else "",
                    room.room_type,
                    room.floorspace,
                    room.floor,
                    rent_display,
                    room.commonfee,
                    total_display,
                    room.url,
                ])

        table_rows.sort(key=lambda r: (0 if r[8] == "TBD" else 1, parse_yen(r[8])))

        print(tabulate(
            table_rows,
            headers=["Property", "Access", "Room", "Type", "Size",
                     "Floor", "Rent", "Common Fee", "Total", "Link"],
            tablefmt="simple",
        ))

    print(f"\n{'='*90}")


def save_results(all_properties: list[Property], filename: str = "results.json"):
    """Save structured results to JSON."""
    data = {
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
            "access": prop.traffic,
            "property_code": f"{prop.shisya}_{prop.danchi}{prop.shikibetu}",
            "url": f"{SITE_URL}/chintai/kanto/{prop.tdfk_name}/{prop.shisya}_{prop.danchi}{prop.shikibetu}.html",
            "rooms": [asdict(r) for r in prop.rooms],
        }
        data["areas"][area].append(prop_dict)

    safe_write_json(data, filename)

    print(f"\nResults saved to {filename}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global REQUEST_DELAY
    parser = build_arg_parser("ur-search", "Search UR Housing rental listings")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")
        for h in logger.handlers:
            h.setLevel("DEBUG")

    areas = filter_areas(AREAS, args.areas)
    if args.delay is not None:
        REQUEST_DELAY = args.delay
    output_file = args.output or "results.json"

    logger.info("UR Housing Rental Price Search")
    if ROOM_TYPE_FILTER:
        logger.info("Filtering for: %s", ", ".join(ROOM_TYPE_FILTER))
    logger.info("Searching %d areas...", len(areas))

    if args.dry_run:
        url = f"{API_URL}/bukken/result/bukken_result/"
        for area in areas:
            logger.info("[DRY RUN] POST %s  skcs=%s tdfk=%s", url, area.ur_skcs, area.ur_tdfk)
        return

    session = create_session(extra_headers={
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ja,en;q=0.9",
        "Referer": f"{SITE_URL}/chintai/kanto/",
        "Origin": SITE_URL,
        "X-Requested-With": "XMLHttpRequest",
    })

    all_properties: list[Property] = []
    max_workers = args.workers if args.workers is not None else DEFAULT_WORKERS

    def _search_one(area):
        logger.info("[%s] Searching...", area.name)
        return area, search_area(area, session)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_search_one, area): area for area in areas}
        for future in as_completed(futures):
            try:
                area, props = future.result()
            except Exception as e:
                area = futures[future]
                logger.error("[%s] Unexpected error: %s", area.name, e)
                continue
            if props:
                room_count = sum(len(p.rooms) for p in props)
                logger.info("[%s] Found %d properties with %d vacant rooms", area.name, len(props), room_count)
                for p in props:
                    logger.info("    - %s: %d room(s)", p.name, len(p.rooms))
                all_properties.extend(props)
            else:
                logger.info("[%s] No vacancies", area.name)

    print_results(all_properties)
    save_results(all_properties, output_file)


if __name__ == "__main__":
    main()
