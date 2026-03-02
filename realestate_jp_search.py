#!/usr/bin/env python3
"""
Real Estate Japan Rental Search Tool

Scrapes realestate.co.jp/en for English-language rental property listings
in target areas around Tokyo. Server-rendered PHP — no JS execution needed.

URL pattern:
  https://realestate.co.jp/en/rent/listing?prefecture={iso}&city={code}&rooms=30&...&page={n}
"""

import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

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

AREAS = [
    # --- SAITAMA (JP-11) ---
    {"name": "Kawaguchi (川口市)",           "prefecture": "JP-11", "city": "11203"},
    {"name": "Kawagoe (川越市)",            "prefecture": "JP-11", "city": "11201"},
    {"name": "Urawa (浦和区)",              "prefecture": "JP-11", "city": "11107"},
    {"name": "Omiya (大宮区)",              "prefecture": "JP-11", "city": "11103"},
    {"name": "Saitama Minami-ku (南区)",    "prefecture": "JP-11", "city": "11108"},

    # --- CHIBA (JP-12) ---
    {"name": "Ichikawa (市川市)",           "prefecture": "JP-12", "city": "12203"},
    {"name": "Funabashi (船橋市)",          "prefecture": "JP-12", "city": "12204"},
    {"name": "Urayasu (浦安市)",            "prefecture": "JP-12", "city": "12227"},
    {"name": "Matsudo (松戸市)",            "prefecture": "JP-12", "city": "12207"},

    # --- KANAGAWA (JP-14) ---
    {"name": "Kawasaki (川崎市)",           "prefecture": "JP-14", "city": "14130"},
    {"name": "Yokohama (横浜市)",           "prefecture": "JP-14", "city": "14100"},
    {"name": "Kamakura (鎌倉市)",           "prefecture": "JP-14", "city": "14204"},
    {"name": "Fujisawa (藤沢市)",           "prefecture": "JP-14", "city": "14205"},

    # --- TOKYO border (JP-13) ---
    {"name": "Kita-ku (北区)",              "prefecture": "JP-13", "city": "13117"},
    {"name": "Itabashi-ku (板橋区)",        "prefecture": "JP-13", "city": "13119"},
    {"name": "Nerima-ku (練馬区)",          "prefecture": "JP-13", "city": "13120"},
    {"name": "Adachi-ku (足立区)",          "prefecture": "JP-13", "city": "13121"},
    {"name": "Edogawa-ku (江戸川区)",       "prefecture": "JP-13", "city": "13123"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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

def parse_yen(text: str) -> int:
    """Parse '¥115,000' or '115,000' → 115000, '¥0' → 0."""
    if not text:
        return 0
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def parse_year_built(text: str) -> int:
    """Parse '2008' → 2008."""
    if not text:
        return -1
    m = re.search(r"(\d{4})", text)
    return int(m.group(1)) if m else -1


def get_pref_name(iso_code: str) -> str:
    """Convert JP-11 → saitama etc."""
    mapping = {
        "JP-11": "saitama",
        "JP-12": "chiba",
        "JP-13": "tokyo",
        "JP-14": "kanagawa",
    }
    return mapping.get(iso_code, "unknown")


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def build_url(area: dict, page: int = 1) -> str:
    """Build Real Estate Japan search URL."""
    params = dict(DEFAULT_PARAMS)
    params["prefecture"] = area["prefecture"]
    params["city"] = area["city"]
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


def parse_page(html_content: str, area: dict) -> list[Room]:
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


def search_area(area: dict) -> list[Room]:
    """Scrape all pages for an area (up to MAX_PAGES_PER_AREA)."""
    all_rooms = []

    for page_num in range(1, MAX_PAGES_PER_AREA + 1):
        url = build_url(area, page_num)

        try:
            resp = SESSION.get(url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] Request failed (page {page_num}): {e}", file=sys.stderr)
            break

        rooms = parse_page(resp.text, area)
        if not rooms:
            if page_num == 1:
                print(f"  No listings found")
            break

        all_rooms.extend(rooms)
        print(f"  Page {page_num}: {len(rooms)} listings")

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
        area_info = area_lookup.get(area_name, {})
        pref = get_pref_name(area_info.get("prefecture", ""))

        listings = []
        for room in rooms:
            listing = {
                "name": f"{room.layout} {room.building_type}".strip(),
                "address": room.neighborhood,
                "access": room.station,
                "building_age": room.year_built,
                "building_age_years": (2026 - room.year_built_int) if room.year_built_int > 0 else -1,
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
    print("Real Estate Japan Rental Search")
    print("=" * 40)
    print(f"Searching {len(AREAS)} areas (max {MAX_PAGES_PER_AREA} pages each)...")
    print(f"Filter: 2LDK+, ¥60,000-¥200,000, Mansion/Apartment")
    print()

    all_areas: dict[str, list[Room]] = {}
    area_lookup: dict[str, dict] = {}

    for i, area in enumerate(AREAS):
        print(f"\n[{area['name']}] Searching...")
        area_lookup[area["name"]] = area

        rooms = search_area(area)
        all_areas[area["name"]] = rooms

        if rooms:
            print(f"  Total: {len(rooms)} listings")
        else:
            print(f"  No listings")

        # Rate limiting between areas
        if i < len(AREAS) - 1:
            time.sleep(REQUEST_DELAY)

    print_results(all_areas)
    save_results(all_areas, area_lookup)


if __name__ == "__main__":
    main()
