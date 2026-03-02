# MLIT Webland & Reinfolib API Reference
## For building benchmark pricing integration

---

## Overview

There are TWO government APIs for Japanese real estate data:

1. **MLIT Webland** (older, simpler, completely open) — Transaction price history
2. **MLIT Reinfolib** (newer, comprehensive, requires API key) — Transaction prices + land values + zoning + disaster risk + 34 endpoints

Both provide HISTORICAL TRANSACTION data, not live listings. Use these to benchmark what properties actually sold/rented for in target areas vs what UR Housing and private market are asking.

---

## 1. MLIT Webland API

### Key Facts
- **Base URL**: `https://www.land.mlit.go.jp/webland/api/`
- **Auth**: NONE — completely open, no registration needed
- **Method**: GET
- **Response**: JSON
- **Languages**: Japanese (`/webland/api/`) and English (`/webland_english/api/`)
- **Data**: Real estate transaction prices from 2005 Q3 onwards
- **Rate limits**: None documented, but be respectful

### Endpoints

#### 1a. TradeListSearch — Get Transaction Prices

```
GET https://www.land.mlit.go.jp/webland/api/TradeListSearch?from={from}&to={to}&area={pref_code}&city={city_code}
```

**Parameters:**

| Parameter | Required | Format | Description |
|-----------|----------|--------|-------------|
| `from` | Yes | `YYYYQ` | Start quarter (e.g., `20241` = 2024 Q1 = Jan-Mar) |
| `to` | Yes | `YYYYQ` | End quarter (e.g., `20244` = 2024 Q4 = Oct-Dec) |
| `area` | Yes* | `NN` | Prefecture JIS code (e.g., `11`=Saitama, `12`=Chiba, `13`=Tokyo, `14`=Kanagawa) |
| `city` | No | `NNNNN` | Municipality code (5 digits). If omitted, returns all in prefecture. |

*Either `area` or `city` must be provided. If `city` is provided, `area` is not needed.

**Quarter format**: `YYYYQ` where Q is 1-4:
- Q1 = January–March
- Q2 = April–June  
- Q3 = July–September
- Q4 = October–December

**Example request:**
```
GET https://www.land.mlit.go.jp/webland/api/TradeListSearch?from=20241&to=20244&city=11203
```
(Kawaguchi City, all of 2024)

**Response fields:**

```json
{
  "status": "OK",
  "data": [
    {
      "Type": "中古マンション等",
      "Region": "",
      "MunicipalityCode": "11203",
      "Prefecture": "埼玉県",
      "Municipality": "川口市",
      "DistrictName": "芝中田",
      "TradePrice": "20000000",
      "PricePerUnit": "",
      "FloorPlan": "２ＬＤＫ",
      "Area": "55",
      "UnitPrice": "290000",
      "LandShape": "",
      "Frontage": "",
      "TotalFloorArea": "",
      "BuildingYear": "平成１５年",
      "Structure": "ＲＣ",
      "Use": "",
      "Purpose": "住宅",
      "Direction": "",
      "Classification": "",
      "Breadth": "",
      "CityPlanning": "第１種住居地域",
      "CoverageRatio": "60",
      "FloorAreaRatio": "200",
      "Period": "2024年第２四半期",
      "Renovation": "",
      "Remarks": ""
    }
  ]
}
```

**Key response fields for rental benchmarking:**

| Field | Description | Example |
|-------|-------------|---------|
| `Type` | Transaction type | `宅地(土地と建物)` (Residential land+building), `中古マンション等` (Pre-owned condo), `宅地(土地)` (Land only) |
| `Municipality` | City/ward name | `川口市` |
| `DistrictName` | District within city | `芝中田` |
| `TradePrice` | Transaction price in yen (string) | `"20000000"` (¥20M) |
| `FloorPlan` | Room layout | `２ＬＤＫ`, `３ＬＤＫ` |
| `Area` | Floor area in sqm (string) | `"55"` |
| `UnitPrice` | Price per sqm (string, for condos) | `"290000"` |
| `BuildingYear` | Year built (Japanese era) | `平成１５年` (2003) |
| `Structure` | Building type | `ＲＣ` (reinforced concrete), `ＳＲＣ`, `木造` (wood) |
| `CityPlanning` | Zoning designation | `第１種住居地域` |
| `Period` | Transaction quarter | `2024年第２四半期` |

**Notes:**
- Prices are SALE prices, not rental. But you can derive rental yield benchmarks
- Filter by `Type` containing `マンション` for condos (most relevant for apartment comparison)
- `BuildingYear` uses Japanese era — need conversion: 平成(Heisei) starts 1989, 令和(Reiwa) starts 2019
- Empty strings are common for non-applicable fields

#### 1b. CitySearch — Get Municipality Codes

```
GET https://www.land.mlit.go.jp/webland/api/CitySearch?area={pref_code}
```

**Parameters:**

| Parameter | Required | Format | Description |
|-----------|----------|--------|-------------|
| `area` | Yes | `NN` | Prefecture JIS code |

**Response:**
```json
{
  "status": "OK",
  "data": [
    {"id": "11101", "name": "さいたま市西区"},
    {"id": "11102", "name": "さいたま市北区"},
    {"id": "11103", "name": "さいたま市大宮区"},
    {"id": "11203", "name": "川口市"},
    ...
  ]
}
```

### Prefecture Codes (JIS) for Target Areas

| Code | Prefecture | Target Cities |
|------|-----------|---------------|
| `11` | Saitama (埼玉県) | Kawaguchi (11203), Wako (11229), Urawa/Saitama-shi wards (11101-11109), Kawagoe (11201), Toda (11224), Warabi (11223), Asaka (11227), Niiza (11230) |
| `12` | Chiba (千葉県) | Ichikawa (12203), Funabashi (12204), Urayasu (12227), Matsudo (12207) |
| `13` | Tokyo (東京都) | Kita-ku (13117), Itabashi-ku (13119), Nerima-ku (13120), Adachi-ku (13121), Edogawa-ku (13123) |
| `14` | Kanagawa (神奈川県) | Kawasaki wards (14131-14137), Yokohama wards (14101-14118) |

### Python Sample Code

```python
import requests
import json
import time

WEBLAND_BASE = "https://www.land.mlit.go.jp/webland/api"

def get_city_codes(pref_code: str) -> list[dict]:
    """Get all municipality codes for a prefecture."""
    url = f"{WEBLAND_BASE}/CitySearch?area={pref_code}"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    return data.get("data", [])

def get_transactions(city_code: str, from_q: str, to_q: str) -> list[dict]:
    """Get transaction data for a city/ward within a date range.
    
    Args:
        city_code: 5-digit municipality code (e.g., '11203' for Kawaguchi)
        from_q: Start quarter in YYYYQ format (e.g., '20241')
        to_q: End quarter in YYYYQ format (e.g., '20244')
    """
    url = f"{WEBLAND_BASE}/TradeListSearch?from={from_q}&to={to_q}&city={city_code}"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    return data.get("data", [])

def filter_condos_2ldk(transactions: list[dict]) -> list[dict]:
    """Filter for condo transactions with 2LDK+ layouts."""
    target_types = ["中古マンション等"]
    target_plans = ["２ＬＤＫ", "３ＬＤＫ", "２ＳＬＤＫ", "３ＤＫ"]
    
    results = []
    for t in transactions:
        if t.get("Type") in target_types:
            plan = t.get("FloorPlan", "")
            if any(fp in plan for fp in target_plans):
                results.append(t)
    return results

def convert_japanese_year(year_str: str) -> int:
    """Convert Japanese era year to Western year.
    e.g., '平成１５年' -> 2003, '令和３年' -> 2021
    """
    import re
    # Normalize full-width digits
    normalized = year_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    
    if '令和' in normalized:
        match = re.search(r'(\d+)', normalized)
        if match:
            return 2018 + int(match.group(1))
    elif '平成' in normalized:
        match = re.search(r'(\d+)', normalized)
        if match:
            return 1988 + int(match.group(1))
    elif '昭和' in normalized:
        match = re.search(r'(\d+)', normalized)
        if match:
            return 1925 + int(match.group(1))
    return 0

# --- Example usage ---
if __name__ == "__main__":
    # Target cities for benchmarking
    TARGET_CITIES = {
        "11203": "Kawaguchi",
        "11229": "Wako", 
        "12203": "Ichikawa",
        "12204": "Funabashi",
        "12227": "Urayasu",
    }
    
    for city_code, name in TARGET_CITIES.items():
        print(f"\n--- {name} ({city_code}) ---")
        transactions = get_transactions(city_code, "20241", "20244")
        condos = filter_condos_2ldk(transactions)
        
        if condos:
            prices = [int(c["TradePrice"]) for c in condos if c.get("TradePrice")]
            areas = [int(c["Area"]) for c in condos if c.get("Area")]
            
            print(f"  Total condo transactions (2LDK+): {len(condos)}")
            if prices:
                print(f"  Price range: ¥{min(prices):,} - ¥{max(prices):,}")
                print(f"  Median price: ¥{sorted(prices)[len(prices)//2]:,}")
            if areas:
                print(f"  Size range: {min(areas)}-{max(areas)} sqm")
        else:
            print(f"  No matching transactions found")
        
        time.sleep(1)  # Be respectful
```

---

## 2. MLIT Reinfolib API (Newer, More Comprehensive)

### Key Facts
- **Base URL**: `https://www.reinfolib.mlit.go.jp/` (exact API URLs in per-endpoint docs)
- **Auth**: API key required — register at `https://www.reinfolib.mlit.go.jp/api/request/`
- **Auth method**: HTTP header `Ocp-Apim-Subscription-Key: {your_api_key}`
- **Response formats**: GeoJSON and PBF (Protocol Buffer Format / binary vector tiles)
- **Rate limits**: Not specified, but throttled if excessive. Space requests out.
- **Data**: 34 APIs covering prices, zoning, facilities, disaster risk, population

### Registration Process
1. Go to `https://www.reinfolib.mlit.go.jp/api/request/`
2. Agree to API terms of use
3. Fill in required fields (name, email, intended use)
4. Wait for approval email with API key
5. Use key in `Ocp-Apim-Subscription-Key` header

### Key APIs for Our Use Case

| ID | API Name | Relevance |
|----|----------|-----------|
| XIT001 | Transaction price info | ★★★★★ — Direct transaction price data, replaces Webland |
| XIT002 | Municipality codes | ★★★★☆ — City/ward code lookup |
| XPT001 | Transaction price points (map) | ★★★★☆ — Geospatial transaction locations |
| XPT002 | Land price survey points (map) | ★★★★☆ — Official land values with coordinates |
| XCT001 | Appraisal report info | ★★★☆☆ — Official government land appraisals |
| XKT002 | Zoning (用途地域) | ★★★☆☆ — What's allowed to be built where |
| XKT015 | Station passenger counts | ★★★☆☆ — How busy stations are |
| XKT013 | Future population projections (250m mesh) | ★★★☆☆ — Will the area grow or shrink? |
| XKT026 | Flood risk zones | ★★★☆☆ — Flood hazard maps for safety assessment |
| XKT028 | Tsunami risk zones | ★★☆☆☆ — Relevant for coastal Chiba/Kanagawa areas |

### Python Sample Code (Reinfolib)

```python
import urllib.request
import gzip
import json

REINFOLIB_API_KEY = "YOUR_API_KEY_HERE"

def reinfolib_request(url: str) -> dict:
    """Make an authenticated request to Reinfolib API."""
    req = urllib.request.Request(url)
    req.add_header("Ocp-Apim-Subscription-Key", REINFOLIB_API_KEY)
    
    with urllib.request.urlopen(req) as response:
        data = response.read()
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if "gzip" in encoding:
            data = gzip.decompress(data)
        return json.loads(data)

# Example: Get transaction prices
# (exact URL format depends on the specific endpoint — check individual API docs)
```

### CORS Note
The Reinfolib docs explicitly warn: do NOT make API requests from browser-side JavaScript (CORS errors). All requests should be server-side (Python, Node.js, curl, etc.).

---

## 3. Comparison: Webland vs Reinfolib

| Feature | Webland | Reinfolib |
|---------|---------|-----------|
| Auth | None | API key |
| Ease of use | Very easy | Moderate |
| Data freshness | Same source | Same source |
| Response format | JSON | GeoJSON + PBF |
| Geospatial data | No coordinates | Yes (lat/lng) |
| Additional data | Transactions only | + Zoning, disaster, facilities, population |
| English support | Yes | Limited |
| Best for | Quick transaction benchmarking | Comprehensive area analysis |

### Recommendation
- **Start with Webland** — it's completely open and gives you transaction price benchmarks immediately
- **Register for Reinfolib** in parallel — the API key approval takes time, and once you have it, the geospatial + zoning + disaster data adds significant value for area comparison

---

## 4. City Codes for Target Areas

Use these codes with both Webland and Reinfolib:

### Saitama (Prefecture 11)
| Code | Area | UR Properties? |
|------|------|---------------|
| 11203 | Kawaguchi (川口市) | Yes — コンフォール東鳩ヶ谷 |
| 11229 | Wako (和光市) | No current vacancies |
| 11107 | Saitama Urawa-ku (浦和区) | No current vacancies |
| 11103 | Saitama Omiya-ku (大宮区) | No current vacancies |
| 11201 | Kawagoe (川越市) | Yes — アクティ川越 |
| 11224 | Toda (戸田市) | No current vacancies |
| 11223 | Warabi (蕨市) | No current vacancies |
| 11108 | Saitama Minami-ku (南区) | Yes — うらわイーストシティ |
| 11227 | Asaka (朝霞市) | Yes — コンフォール東朝霞 |
| 11230 | Niiza (新座市) | Yes — 新座 |

### Chiba (Prefecture 12)
| Code | Area | UR Properties? |
|------|------|---------------|
| 12203 | Ichikawa (市川市) | Yes — エステート市川大洲 |
| 12204 | Funabashi (船橋市) | No current vacancies |
| 12227 | Urayasu (浦安市) | Yes — 望海の街, コンフォール舞浜 |
| 12207 | Matsudo (松戸市) | No current vacancies |

### Kanagawa (Prefecture 14)
| Code | Area | UR Properties? |
|------|------|---------------|
| 14131 | Kawasaki-ku | No current vacancies |
| 14132 | Saiwai-ku | No current vacancies |
| 14133 | Nakahara-ku | No current vacancies |
| 14134 | Takatsu-ku | No current vacancies |
| 14103 | Yokohama Nishi-ku | No current vacancies |
| 14104 | Yokohama Naka-ku | Yes — ビューコート小港, ベイサイト本牧 |
| 14102 | Yokohama Kanagawa-ku | Yes — 西菅田 |
| 14109 | Yokohama Kohoku-ku | No current vacancies |
| 14118 | Yokohama Tsuzuki-ku | Yes — ビュープラザセンター北 |
| 14105 | Yokohama Minami-ku | Yes — 南永田第二 |
| 14107 | Yokohama Isogo-ku | Yes — 磯子杉田台 |

---

## 5. Integration Architecture

The target flow for the unified spreadsheet:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│ UR Housing   │     │ MLIT Webland │     │ MLIT Reinfolib   │
│ (live rooms) │     │ (benchmarks) │     │ (rich geo data)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────────┘
       │                    │                     │
       ▼                    ▼                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    Python Aggregator                         │
│  ur_rental_search.py + mlit_webland.py + reinfolib.py       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Unified XLSX    │
              │ + JSON output   │
              └─────────────────┘
```

Each data source provides a different piece:
- **UR Housing**: What's available RIGHT NOW, at what price, with zero hidden costs
- **Webland**: What comparable properties SOLD FOR in the same areas (benchmark)
- **Reinfolib**: What ZONE it's in, what FACILITIES are nearby, what DISASTER RISKS exist
- **Private market JSON**: What private landlords are ASKING (to compare against UR)

---

## 6. Existing Python Wrappers

- **j_realty_api** — Python wrapper for Webland (search PyPI/GitHub)
- **jpstat** (R package) — Has `webland_trade()` and `webland_city()` functions, R only
- **urchintai-client** — Third-party Python async client for UR (uses older hostname, needs updating)

---

*Document created: 2026-03-01*
*For use by: Agent building MLIT API integration scripts*
