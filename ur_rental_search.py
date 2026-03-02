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
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "https://chintai.r6.ur-net.go.jp/chintai/api"
SITE_URL = "https://www.ur-net.go.jp"
REQUEST_DELAY = 2  # seconds between API calls — be respectful

# Prefecture code mapping (tdfk uses JIS prefecture codes):
# 11 = Saitama, 12 = Chiba, 13 = Tokyo, 14 = Kanagawa

# Room type filter — set to None to show all, or e.g. ["2LDK", "3LDK"]
ROOM_TYPE_FILTER = ["2LDK", "2SLDK", "3LDK", "3DK"]

AREAS = [
    # --- SAITAMA (tdfk=11) ---
    {"name": "Kawaguchi (川口市)",           "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "203"},
    {"name": "Wako (和光市)",               "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "229"},
    {"name": "Urawa (浦和区)",              "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "107"},
    {"name": "Omiya (大宮区)",              "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "103"},
    {"name": "Kawagoe (川越市)",            "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "201"},
    {"name": "Toda (戸田市)",               "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "224"},
    {"name": "Warabi (蕨市)",               "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "223"},
    {"name": "Saitama Minami-ku (南区)",    "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "108"},
    {"name": "Saitama Chuo-ku (中央区)",    "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "105"},
    {"name": "Asaka (朝霞市)",              "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "227"},
    {"name": "Niiza (新座市)",              "block": "kanto", "tdfk": "11", "tdfk_name": "saitama",  "skcs": "230"},

    # --- CHIBA (tdfk=12) ---
    {"name": "Ichikawa (市川市)",           "block": "kanto", "tdfk": "12", "tdfk_name": "chiba",    "skcs": "203"},
    {"name": "Funabashi (船橋市)",          "block": "kanto", "tdfk": "12", "tdfk_name": "chiba",    "skcs": "204"},
    {"name": "Urayasu (浦安市)",            "block": "kanto", "tdfk": "12", "tdfk_name": "chiba",    "skcs": "227"},
    {"name": "Matsudo (松戸市)",            "block": "kanto", "tdfk": "12", "tdfk_name": "chiba",    "skcs": "207"},

    # --- KANAGAWA (tdfk=14) — Kawasaki ---
    {"name": "Kawasaki-ku (川崎区)",        "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "131"},
    {"name": "Saiwai-ku (幸区)",            "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "132"},
    {"name": "Nakahara-ku (中原区)",        "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "133"},
    {"name": "Takatsu-ku (高津区)",         "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "134"},

    # --- KANAGAWA — Yokohama ---
    {"name": "Yokohama Nishi-ku (西区)",    "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "103"},
    {"name": "Yokohama Naka-ku (中区)",     "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "104"},
    {"name": "Yokohama Kanagawa-ku (神奈川区)", "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "102"},
    {"name": "Yokohama Kohoku-ku (港北区)", "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "109"},
    {"name": "Yokohama Tsuzuki-ku (都筑区)","block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "118"},
    {"name": "Yokohama Aoba-ku (青葉区)",   "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "117"},
    {"name": "Yokohama Minami-ku (南区)",   "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "105"},
    {"name": "Yokohama Hodogaya-ku (保土ケ谷区)", "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "106"},
    {"name": "Yokohama Isogo-ku (磯子区)",  "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "107"},

    # --- KANAGAWA — Shonan / Other ---
    {"name": "Kamakura (鎌倉市)",           "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "204"},
    {"name": "Fujisawa (藤沢市)",           "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "205"},
    {"name": "Chigasaki (茅ヶ崎市)",        "block": "kanto", "tdfk": "14", "tdfk_name": "kanagawa", "skcs": "207"},

    # --- TOKYO border areas (tdfk=13) ---
    {"name": "Kita-ku (北区)",              "block": "kanto", "tdfk": "13", "tdfk_name": "tokyo",    "skcs": "117"},
    {"name": "Itabashi-ku (板橋区)",        "block": "kanto", "tdfk": "13", "tdfk_name": "tokyo",    "skcs": "119"},
    {"name": "Nerima-ku (練馬区)",          "block": "kanto", "tdfk": "13", "tdfk_name": "tokyo",    "skcs": "120"},
    {"name": "Adachi-ku (足立区)",          "block": "kanto", "tdfk": "13", "tdfk_name": "tokyo",    "skcs": "121"},
    {"name": "Edogawa-ku (江戸川区)",       "block": "kanto", "tdfk": "13", "tdfk_name": "tokyo",    "skcs": "123"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ja,en;q=0.9",
    "Referer": f"{SITE_URL}/chintai/kanto/",
    "Origin": SITE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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

def parse_yen(text: str) -> int:
    """Parse a yen string like '101,800円' or '¥101,800' to integer."""
    if not text:
        return 0
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


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

def search_area(area: dict) -> list[Property]:
    """
    Query the bukken_result API for an area.
    Returns a list of Property objects with their vacant rooms.
    """
    url = f"{API_URL}/bukken/result/bukken_result/"
    data = {
        "mode": "area",
        "skcs": area["skcs"],
        "block": area["block"],
        "tdfk": area["tdfk"],
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
        resp = SESSION.post(url, data=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as e:
        print(f"  [ERROR] API request failed: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print(f"  [ERROR] Invalid JSON response", file=sys.stderr)
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
            area_name=area["name"],
            tdfk_name=area["tdfk_name"],
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

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {filename}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("UR Housing Rental Price Search")
    print("=" * 40)
    if ROOM_TYPE_FILTER:
        print(f"Filtering for: {', '.join(ROOM_TYPE_FILTER)}")
    print(f"Searching {len(AREAS)} areas...")
    print()

    all_properties: list[Property] = []

    for i, area in enumerate(AREAS):
        print(f"\n[{area['name']}] Searching...")

        props = search_area(area)

        if props:
            room_count = sum(len(p.rooms) for p in props)
            print(f"  Found {len(props)} properties with {room_count} vacant rooms")
            for p in props:
                print(f"    - {p.name}: {len(p.rooms)} room(s)")
            all_properties.extend(props)
        else:
            print(f"  No vacancies")

        # Rate limiting between requests (skip delay after last)
        if i < len(AREAS) - 1:
            time.sleep(REQUEST_DELAY)

    print_results(all_properties)
    save_results(all_properties)


if __name__ == "__main__":
    main()
