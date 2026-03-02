#!/usr/bin/env python3
"""
build_pois.py — Overpass API scraper for area POIs around Tokyo rental search areas.

Uses a SINGLE batched Overpass query covering all areas simultaneously (instead of
37 individual queries). POIs are then assigned to the nearest area centre.

Outputs area_pois_raw.json then curates into area_pois.json with manual enrichments.

Usage:
    python3 build_pois.py
"""

import json
import math
import time

import re

from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging
from shared.config import AREAS as ALL_AREAS

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _short_name(full_name: str) -> str:
    """Extract short area name: 'Kawaguchi (川口市)' → 'Kawaguchi'."""
    return re.sub(r"\s*\(.*\)$", "", full_name)


# Build AREA_CENTRES from unified config (only areas with lat/lng)
AREA_CENTRES = {
    _short_name(a.name): (a.lat, a.lng)
    for a in ALL_AREAS
    if a.lat != 0.0 and a.lng != 0.0
    # Skip REJ-only broad city entries that duplicate ward-level entries
    and a.name not in ("Kawasaki (川崎市)", "Yokohama (横浜市)")
}

RADIUS = 3000  # metres


def haversine(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lng points."""
    R = 6371000
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + \
        math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 2 * R * math.asin(math.sqrt(a))


def build_bbox():
    """Compute a single bounding box covering all areas + radius buffer."""
    lats = [c[0] for c in AREA_CENTRES.values()]
    lngs = [c[1] for c in AREA_CENTRES.values()]
    # ~0.027 degrees ≈ 3km at Tokyo's latitude
    buf = 0.03
    return (min(lats) - buf, min(lngs) - buf, max(lats) + buf, max(lngs) + buf)


def build_batch_query():
    """Single Overpass query using a bounding box covering all areas."""
    s, w, n, e = build_bbox()
    return f"""
[out:json][timeout:90][bbox:{s},{w},{n},{e}];
(
  node["railway"="station"];
  way["railway"="station"];
  node["shop"="supermarket"]["name"];
  way["shop"="supermarket"]["name"];
  node["leisure"="park"]["name"];
  way["leisure"="park"]["name"];
  node["shop"="mall"];
  way["shop"="mall"];
  node["shop"="department_store"];
  way["shop"="department_store"];
  node["amenity"="hospital"]["name"];
  way["amenity"="hospital"]["name"];
);
out center;
"""


logger = setup_logging(name="build-pois")


def query_overpass(query, session):
    """Send query to Overpass API (retries handled by shared http_client)."""
    try:
        resp = fetch_page(session, OVERPASS_URL, method="POST", timeout=120, data={"data": query})
        return resp.json()
    except Exception as e:
        logger.error("Overpass query failed: %s", e)
        return None


def categorize_element(el):
    """Categorize an Overpass element into a POI category."""
    tags = el.get("tags", {})
    lat = el.get("lat") or (el.get("center", {}).get("lat"))
    lng = el.get("lon") or (el.get("center", {}).get("lon"))
    if not lat or not lng:
        return None

    name = tags.get("name", "")
    name_en = tags.get("name:en", "")
    display_name = name_en if name_en else name
    if not display_name:
        return None

    result = {"name": display_name, "name_jp": name, "lat": round(lat, 4), "lng": round(lng, 4)}

    if tags.get("railway") == "station":
        lines = []
        for key in ["railway:line", "line", "operator"]:
            if key in tags:
                lines.append(tags[key])
        result["cat"] = "station"
        result["lines"] = lines
        return result
    elif tags.get("shop") == "supermarket":
        result["cat"] = "supermarket"
        return result
    elif tags.get("leisure") == "park":
        result["cat"] = "park"
        return result
    elif tags.get("shop") in ("mall", "department_store"):
        result["cat"] = "shopping"
        return result
    elif tags.get("amenity") == "hospital":
        result["cat"] = "hospital"
        return result
    return None


def assign_pois_to_areas(all_pois):
    """Assign each POI to its nearest area centre (within RADIUS)."""
    area_pois = {name: [] for name in AREA_CENTRES}
    for poi in all_pois:
        best_area = None
        best_dist = RADIUS + 1
        for area_name, (alat, alng) in AREA_CENTRES.items():
            d = haversine(poi["lat"], poi["lng"], alat, alng)
            if d < best_dist:
                best_dist = d
                best_area = area_name
        if best_area and best_dist <= RADIUS:
            area_pois[best_area].append(poi)
    return area_pois


def deduplicate(pois, max_per_cat=8):
    """Deduplicate POIs by name and limit per category."""
    seen = set()
    result = {}
    for poi in pois:
        key = (poi["cat"], poi["name"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        cat = poi["cat"]
        if cat not in result:
            result[cat] = []
        if len(result[cat]) < max_per_cat:
            result[cat].append(poi)
    return result


def main():
    session = create_session(
        max_retries=3,
        backoff_factor=5.0,
        extra_headers={"User-Agent": "finding-property-tokyo/1.0"},
    )

    print(f"Fetching POIs for {len(AREA_CENTRES)} areas in a single batch query...")
    bbox = build_bbox()
    print(f"Bounding box: {bbox[0]:.3f},{bbox[1]:.3f} to {bbox[2]:.3f},{bbox[3]:.3f}")

    query = build_batch_query()
    result = query_overpass(query, session)

    if not result:
        print("FAILED — Overpass API did not respond. Try again later.")
        return

    elements = result.get("elements", [])
    print(f"Received {len(elements)} raw elements from Overpass")

    # Categorize all elements
    all_pois = []
    for el in elements:
        poi = categorize_element(el)
        if poi:
            all_pois.append(poi)
    print(f"Categorized {len(all_pois)} POIs (stations, shops, parks, hospitals)")

    # Assign to nearest area
    area_pois = assign_pois_to_areas(all_pois)

    # Build raw data
    raw_data = {}
    for area_name, (lat, lng) in AREA_CENTRES.items():
        pois = area_pois[area_name]
        categorized = deduplicate(pois)
        station_count = len(categorized.get("station", []))
        shop_count = len(categorized.get("supermarket", [])) + len(categorized.get("shopping", []))
        park_count = len(categorized.get("park", []))
        print(f"  {area_name}: {station_count} stations, {shop_count} shops, {park_count} parks")
        raw_data[area_name] = {
            "lat": lat,
            "lng": lng,
            "pois": categorized,
            "total_found": len(pois),
        }

    # Write raw output
    with open("area_pois_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"\nWrote area_pois_raw.json ({len(raw_data)} areas)")

    # Curate into final format
    curate(raw_data)


def curate(raw_data):
    """Transform raw Overpass data into the final area_pois.json with manual enrichments."""
    output = {
        "office": {
            "name": "Yotsuya Station (PayPay Office)",
            "lat": 35.686,
            "lng": 139.730,
            "note": "Comore Yotsuya Tower, 1-6-1 Yotsuya, Shinjuku-ku. Lines: JR Chuo, JR Sobu, Marunouchi, Namboku."
        },
        "hubs": [
            {"name": "Shibuya", "lat": 35.658, "lng": 139.702, "icon": "hub"},
            {"name": "Shinjuku", "lat": 35.690, "lng": 139.700, "icon": "hub"},
            {"name": "Ikebukuro", "lat": 35.730, "lng": 139.711, "icon": "hub"},
            {"name": "Yokohama", "lat": 35.466, "lng": 139.622, "icon": "hub"},
            {"name": "Tokyo Station", "lat": 35.681, "lng": 139.767, "icon": "hub"},
        ],
        "areas": {}
    }

    MANUAL_POIS = {
        "Kawaguchi": [
            {"name": "Indian grocery district", "cat": "expat", "lat": 35.807, "lng": 139.720, "note": "South Asian shops, spice stores & restaurants near Kawaguchi station"},
            {"name": "Aeon Mall Kawaguchi", "cat": "shopping", "lat": 35.810, "lng": 139.730},
        ],
        "Wako": [
            {"name": "Trains originate here", "cat": "transit", "lat": 35.787, "lng": 139.606, "note": "Tobu Tojo trains start at Wako — guaranteed seats during rush hour"},
        ],
        "Funabashi": [
            {"name": "LaLaport Tokyo Bay", "cat": "shopping", "lat": 35.679, "lng": 139.988, "note": "Massive shopping complex, 570+ stores"},
        ],
        "Omiya": [
            {"name": "Railway Museum", "cat": "culture", "lat": 35.921, "lng": 139.618, "note": "Japan's national railway museum"},
        ],
        "Nakahara-ku": [
            {"name": "Shin-Maruko izakaya street", "cat": "dining", "lat": 35.578, "lng": 139.665, "note": "Old-school charming izakaya streets"},
        ],
        "Urawa": [
            {"name": "Urawa Reds Stadium", "cat": "culture", "lat": 35.863, "lng": 139.714, "note": "Saitama Stadium 2002, home of Urawa Red Diamonds"},
        ],
        "Kawagoe": [
            {"name": "Little Edo district", "cat": "culture", "lat": 35.921, "lng": 139.483, "note": "Preserved Edo-period warehouse district"},
        ],
        "Yokohama Naka-ku": [
            {"name": "Yokohama Chinatown", "cat": "dining", "lat": 35.443, "lng": 139.646, "note": "Largest Chinatown in Japan, 500+ restaurants"},
        ],
    }

    KNOWN_STATIONS = {
        "Kawaguchi": [
            {"name": "Kawaguchi", "lat": 35.806, "lng": 139.721, "lines": ["JR Keihin-Tohoku"]},
            {"name": "Kawaguchi-Motogo", "lat": 35.815, "lng": 139.718, "lines": ["Saitama Railway", "Namboku"]},
            {"name": "Nishi-Kawaguchi", "lat": 35.813, "lng": 139.713, "lines": ["JR Keihin-Tohoku"]},
        ],
        "Wako": [
            {"name": "Wakoshi", "lat": 35.787, "lng": 139.606, "lines": ["Tobu Tojo", "Yurakucho", "Fukutoshin"]},
        ],
        "Urawa": [
            {"name": "Urawa", "lat": 35.858, "lng": 139.657, "lines": ["JR Keihin-Tohoku", "JR Utsunomiya"]},
            {"name": "Minami-Urawa", "lat": 35.845, "lng": 139.647, "lines": ["JR Musashino", "JR Keihin-Tohoku"]},
        ],
        "Omiya": [
            {"name": "Omiya", "lat": 35.906, "lng": 139.631, "lines": ["JR Keihin-Tohoku", "JR Takasaki", "JR Utsunomiya", "Tobu Noda", "New Shuttle"]},
        ],
        "Kawagoe": [
            {"name": "Kawagoe", "lat": 35.908, "lng": 139.486, "lines": ["JR Kawagoe", "Tobu Tojo"]},
            {"name": "Hon-Kawagoe", "lat": 35.919, "lng": 139.483, "lines": ["Seibu Shinjuku"]},
        ],
        "Toda": [
            {"name": "Toda-Koen", "lat": 35.817, "lng": 139.678, "lines": ["JR Saikyo"]},
        ],
        "Warabi": [
            {"name": "Warabi", "lat": 35.826, "lng": 139.680, "lines": ["JR Keihin-Tohoku"]},
        ],
        "Asaka": [
            {"name": "Asaka", "lat": 35.797, "lng": 139.593, "lines": ["Tobu Tojo"]},
            {"name": "Asakadai", "lat": 35.808, "lng": 139.593, "lines": ["Tobu Tojo"]},
        ],
        "Niiza": [
            {"name": "Niiza", "lat": 35.793, "lng": 139.565, "lines": ["JR Musashino"]},
            {"name": "Shiki", "lat": 35.783, "lng": 139.574, "lines": ["Tobu Tojo"]},
        ],
        "Ichikawa": [
            {"name": "Ichikawa", "lat": 35.732, "lng": 139.912, "lines": ["JR Sobu"]},
            {"name": "Motoyawata", "lat": 35.727, "lng": 139.930, "lines": ["JR Sobu", "Toei Shinjuku"]},
        ],
        "Funabashi": [
            {"name": "Funabashi", "lat": 35.701, "lng": 139.985, "lines": ["JR Sobu", "Tobu Noda"]},
            {"name": "Nishi-Funabashi", "lat": 35.717, "lng": 139.967, "lines": ["JR Musashino", "Tokyo Metro Tozai"]},
        ],
        "Urayasu": [
            {"name": "Shin-Urayasu", "lat": 35.647, "lng": 139.895, "lines": ["JR Keiyo"]},
            {"name": "Urayasu", "lat": 35.657, "lng": 139.899, "lines": ["Tokyo Metro Tozai"]},
        ],
        "Matsudo": [
            {"name": "Matsudo", "lat": 35.784, "lng": 139.901, "lines": ["JR Joban", "Shin-Keisei"]},
        ],
        "Nakahara-ku": [
            {"name": "Musashi-Kosugi", "lat": 35.576, "lng": 139.660, "lines": ["JR Shonan-Shinjuku", "JR Yokosuka", "JR Nambu", "Tokyu Toyoko", "Tokyu Meguro"]},
            {"name": "Shin-Maruko", "lat": 35.580, "lng": 139.668, "lines": ["Tokyu Toyoko", "Tokyu Meguro"]},
        ],
        "Kawasaki-ku": [
            {"name": "Kawasaki", "lat": 35.531, "lng": 139.699, "lines": ["JR Tokaido", "JR Keihin-Tohoku", "JR Nambu", "Keikyu"]},
        ],
        "Kita-ku": [
            {"name": "Akabane", "lat": 35.777, "lng": 139.721, "lines": ["JR Keihin-Tohoku", "JR Saikyo"]},
            {"name": "Oji", "lat": 35.753, "lng": 139.738, "lines": ["JR Keihin-Tohoku", "Namboku"]},
        ],
        "Itabashi-ku": [
            {"name": "Itabashi", "lat": 35.752, "lng": 139.716, "lines": ["JR Saikyo"]},
            {"name": "Narimasu", "lat": 35.773, "lng": 139.633, "lines": ["Tobu Tojo"]},
        ],
        "Nerima-ku": [
            {"name": "Nerima", "lat": 35.737, "lng": 139.654, "lines": ["Seibu Ikebukuro", "Oedo"]},
        ],
        "Adachi-ku": [
            {"name": "Kita-Senju", "lat": 35.749, "lng": 139.805, "lines": ["JR Joban", "Tokyo Metro Chiyoda", "Tokyo Metro Hibiya", "Tsukuba Express", "Tobu Skytree"]},
        ],
        "Edogawa-ku": [
            {"name": "Koiwa", "lat": 35.730, "lng": 139.879, "lines": ["JR Sobu"]},
            {"name": "Kasai", "lat": 35.660, "lng": 139.862, "lines": ["Tokyo Metro Tozai"]},
        ],
    }

    for area_name, area_data in raw_data.items():
        lat = area_data["lat"]
        lng = area_data["lng"]
        raw_pois = area_data.get("pois", {})

        stations = KNOWN_STATIONS.get(area_name, [])
        if not stations:
            for s in raw_pois.get("station", []):
                stations.append({
                    "name": s["name"],
                    "lat": s["lat"],
                    "lng": s["lng"],
                    "lines": s.get("lines", []),
                })

        # Manual POIs first (higher value), then Overpass data
        pois = []
        for mp in MANUAL_POIS.get(area_name, []):
            pois.append(mp)

        existing_names = {p["name"].lower() for p in pois}
        for cat in ["shopping", "supermarket", "park", "hospital"]:
            for p in raw_pois.get(cat, [])[:4]:
                if p["name"].lower() not in existing_names:
                    pois.append({
                        "name": p["name"],
                        "cat": cat,
                        "lat": p["lat"],
                        "lng": p["lng"],
                    })
                    existing_names.add(p["name"].lower())

        output["areas"][area_name] = {
            "lat": lat,
            "lng": lng,
            "stations": stations,
            "pois": pois[:12],
        }

    with open("area_pois.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Wrote area_pois.json ({len(output['areas'])} areas, {sum(len(a['stations']) for a in output['areas'].values())} stations)")


if __name__ == "__main__":
    main()
