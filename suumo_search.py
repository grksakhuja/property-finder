#!/usr/bin/env python3
"""
SUUMO Rental Search Tool

Scrapes suumo.jp for rental property listings in target areas around Tokyo.
Uses server-rendered HTML — no JS execution needed.

URL pattern: https://suumo.jp/chintai/{prefecture}/sc_{city}/?md=07&pc=50&page={n}
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

BASE_URL = "https://suumo.jp/chintai"
REQUEST_DELAY = 2  # seconds between page fetches
MAX_PAGES_PER_AREA = 5  # cap at 250 listings per area (50/page)

# Room type codes for SUUMO md parameter
# md=07 → 2LDK, md=08 → 3K, md=09 → 3DK, md=10 → 3LDK
ROOM_TYPE_CODES = ["07", "08", "09", "10"]
ROOM_TYPE_FILTER = ["2LDK", "2SLDK", "3LDK", "3DK", "3K"]

AREAS = [
    # --- SAITAMA ---
    {"name": "Kawaguchi (川口市)",           "prefecture": "saitama", "code": "sc_kawaguchi"},
    {"name": "Wako (和光市)",               "prefecture": "saitama", "code": "sc_wako"},
    {"name": "Urawa (浦和区)",              "prefecture": "saitama", "code": "sc_saitamashiurawa"},
    {"name": "Omiya (大宮区)",              "prefecture": "saitama", "code": "sc_saitamashiomiya"},
    {"name": "Kawagoe (川越市)",            "prefecture": "saitama", "code": "sc_kawagoe"},
    {"name": "Toda (戸田市)",               "prefecture": "saitama", "code": "sc_toda"},
    {"name": "Warabi (蕨市)",               "prefecture": "saitama", "code": "sc_warabi"},
    {"name": "Saitama Minami-ku (南区)",    "prefecture": "saitama", "code": "sc_saitamashiminami"},
    {"name": "Saitama Chuo-ku (中央区)",    "prefecture": "saitama", "code": "sc_saitamashichuo"},
    {"name": "Asaka (朝霞市)",              "prefecture": "saitama", "code": "sc_asaka"},
    {"name": "Niiza (新座市)",              "prefecture": "saitama", "code": "sc_niiza"},

    # --- CHIBA ---
    {"name": "Ichikawa (市川市)",           "prefecture": "chiba", "code": "sc_ichikawa"},
    {"name": "Funabashi (船橋市)",          "prefecture": "chiba", "code": "sc_funabashi"},
    {"name": "Urayasu (浦安市)",            "prefecture": "chiba", "code": "sc_urayasu"},
    {"name": "Matsudo (松戸市)",            "prefecture": "chiba", "code": "sc_matsudo"},

    # --- KANAGAWA — Kawasaki ---
    {"name": "Kawasaki-ku (川崎区)",        "prefecture": "kanagawa", "code": "sc_kawasakishikawasaki"},
    {"name": "Saiwai-ku (幸区)",            "prefecture": "kanagawa", "code": "sc_kawasakishisaiwai"},
    {"name": "Nakahara-ku (中原区)",        "prefecture": "kanagawa", "code": "sc_kawasakishinakahara"},
    {"name": "Takatsu-ku (高津区)",         "prefecture": "kanagawa", "code": "sc_kawasakishitakatsu"},

    # --- KANAGAWA — Yokohama ---
    {"name": "Yokohama Tsurumi-ku (鶴見区)",  "prefecture": "kanagawa", "code": "sc_yokohamashitsurumi"},
    {"name": "Yokohama Kanagawa-ku (神奈川区)","prefecture": "kanagawa", "code": "sc_yokohamashikanagawa"},
    {"name": "Yokohama Nishi-ku (西区)",      "prefecture": "kanagawa", "code": "sc_yokohamashinishi"},
    {"name": "Yokohama Naka-ku (中区)",       "prefecture": "kanagawa", "code": "sc_yokohamashinaka"},
    {"name": "Yokohama Minami-ku (南区)",     "prefecture": "kanagawa", "code": "sc_yokohamashiminami"},
    {"name": "Yokohama Hodogaya-ku (保土ケ谷区)","prefecture": "kanagawa", "code": "sc_yokohamashihodogaya"},
    {"name": "Yokohama Kohoku-ku (港北区)",   "prefecture": "kanagawa", "code": "sc_yokohamashikohoku"},
    {"name": "Yokohama Konan-ku (港南区)",    "prefecture": "kanagawa", "code": "sc_yokohamashikonan"},
    {"name": "Yokohama Aoba-ku (青葉区)",     "prefecture": "kanagawa", "code": "sc_yokohamashiaoba"},

    # --- KANAGAWA — Shonan ---
    {"name": "Kamakura (鎌倉市)",           "prefecture": "kanagawa", "code": "sc_kamakura"},
    {"name": "Fujisawa (藤沢市)",           "prefecture": "kanagawa", "code": "sc_fujisawa"},
    {"name": "Chigasaki (茅ヶ崎市)",        "prefecture": "kanagawa", "code": "sc_chigasaki"},

    # --- TOKYO border ---
    {"name": "Kita-ku (北区)",              "prefecture": "tokyo", "code": "sc_kita"},
    {"name": "Itabashi-ku (板橋区)",        "prefecture": "tokyo", "code": "sc_itabashi"},
    {"name": "Nerima-ku (練馬区)",          "prefecture": "tokyo", "code": "sc_nerima"},
    {"name": "Adachi-ku (足立区)",          "prefecture": "tokyo", "code": "sc_adachi"},
    {"name": "Edogawa-ku (江戸川区)",       "prefecture": "tokyo", "code": "sc_edogawa"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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
# Parsers
# ---------------------------------------------------------------------------

def parse_man_yen(text: str) -> int:
    """Parse '8.2万円' → 82000, '5000円' → 5000, '-' → 0."""
    if not text or text.strip() == "-":
        return 0
    text = text.strip().replace(",", "")
    # Format: X.Y万円 (万 = 10,000)
    m = re.search(r"([\d.]+)万円", text)
    if m:
        return int(float(m.group(1)) * 10000)
    # Format: plain yen like 5000円
    m = re.search(r"([\d]+)円", text)
    if m:
        return int(m.group(1))
    return 0


def parse_building_age(text: str) -> int:
    """Parse '築20年' → 20, '新築' → 0."""
    if not text:
        return -1
    text = text.strip()
    if "新築" in text:
        return 0
    m = re.search(r"築(\d+)年", text)
    return int(m.group(1)) if m else -1


def parse_size_sqm(text: str) -> float:
    """Parse '50.28m²' or '50.28m2' → 50.28."""
    if not text:
        return 0.0
    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else 0.0


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def build_url(area: dict, page: int = 1) -> str:
    """Build SUUMO search URL for an area + page."""
    prefecture = area["prefecture"]
    code = area["code"]
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


def parse_page(html_content: str, area: dict) -> list[Property]:
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
            rent_value = parse_man_yen(rent_text)

            admin_el = row.select_one(".cassetteitem_price--administration")
            admin_text = admin_el.get_text(strip=True) if admin_el else ""
            admin_value = parse_man_yen(admin_text)

            deposit_el = row.select_one(".cassetteitem_price--deposit")
            deposit_text = deposit_el.get_text(strip=True) if deposit_el else ""
            deposit_value = parse_man_yen(deposit_text)

            key_el = row.select_one(".cassetteitem_price--gratuity")
            key_text = key_el.get_text(strip=True) if key_el else ""
            key_value = parse_man_yen(key_text)

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
                area_name=area["name"],
                prefecture=area["prefecture"],
                rooms=rooms,
            ))

    return properties


def search_area(area: dict) -> list[Property]:
    """Scrape all pages for an area (up to MAX_PAGES_PER_AREA)."""
    all_properties = []

    for page_num in range(1, MAX_PAGES_PER_AREA + 1):
        url = build_url(area, page_num)

        try:
            resp = SESSION.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] Request failed (page {page_num}): {e}", file=sys.stderr)
            break

        properties = parse_page(resp.text, area)
        if not properties:
            if page_num == 1:
                print(f"  No listings found")
            break

        all_properties.extend(properties)
        room_count = sum(len(p.rooms) for p in properties)
        print(f"  Page {page_num}: {len(properties)} buildings, {room_count} units")

        # Check if there are more pages
        soup = BeautifulSoup(resp.text, "html.parser")
        total = get_total_count(soup)
        fetched_so_far = page_num * 50
        if total == 0 or fetched_so_far >= total:
            break

        if page_num < MAX_PAGES_PER_AREA:
            time.sleep(REQUEST_DELAY)

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

        table_rows.sort(key=lambda r: (0 if r[7] == "TBD" else 1, parse_man_yen(r[7]) if r[7] != "TBD" else 0))

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

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {filename}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("SUUMO Rental Search")
    print("=" * 40)
    if ROOM_TYPE_FILTER:
        print(f"Filtering for: {', '.join(ROOM_TYPE_FILTER)}")
    print(f"Searching {len(AREAS)} areas (max {MAX_PAGES_PER_AREA} pages each)...")
    print()

    all_properties: list[Property] = []

    for i, area in enumerate(AREAS):
        print(f"\n[{area['name']}] Searching...")

        props = search_area(area)

        if props:
            room_count = sum(len(p.rooms) for p in props)
            print(f"  Total: {len(props)} buildings with {room_count} units")
            all_properties.extend(props)
        else:
            print(f"  No listings")

        # Rate limiting between areas
        if i < len(AREAS) - 1:
            time.sleep(REQUEST_DELAY)

    print_results(all_properties)
    save_results(all_properties)


if __name__ == "__main__":
    main()
