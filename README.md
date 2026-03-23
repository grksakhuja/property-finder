# Tokyo Rental Property Finder

Multi-source scraper and interactive viewer for rental properties in the greater Tokyo region. Aggregates listings from seven property sources — including foreigner-friendly sites — and displays them in a browser-based viewer with maps, scoring, and filtering.

## Quick Start

```bash
pip install -r requirements.txt

# Run all scrapers in parallel
python run_all.py

# Or run individual scrapers
python ur_rental_search.py
python suumo_search.py
python realestate_jp_search.py
python best_estate_search.py
python gaijinpot_search.py
python wagaya_search.py
python villagehouse_search.py

# Serve the viewer
python server.py
# Open http://localhost:8080
```

## Data Sources

| Scraper | Source | Notes |
|---|---|---|
| `ur_rental_search.py` | [UR公団](https://www.ur-net.go.jp/chintai/) | Public housing API. No key money, no agent fees, no guarantor needed. |
| `suumo_search.py` | [SUUMO](https://suumo.jp/) | HTML scraper for Japan's largest property listing site. |
| `realestate_jp_search.py` | [RealEstate.co.jp](https://realestate.co.jp/) | English-language listings for the Tokyo area. |
| `best_estate_search.py` | [Best Estate](https://www.best-estate.jp/en/) | Foreigner-friendly. Room-type filtering, nationwide search. |
| `gaijinpot_search.py` | [GaijinPot Apartments](https://apartments.gaijinpot.com/) | 100% English, foreigner-focused listings. |
| `wagaya_search.py` | [Wagaya Japan](https://wagaya-japan.com/) | Foreigner-friendly. Extracts embedded JSON from page source. |
| `villagehouse_search.py` | [Village House](https://www.villagehouse.jp/en/) | Renovated older buildings. Zero deposit, zero key money. |

Each scraper writes a JSON file (`results.json`, `results_suumo.json`, etc.) that the viewer loads.

### Scraper Architecture

The newer scrapers (Best Estate, GaijinPot, Wagaya, Village House) extend `BaseScraper` from `shared/scraper_template.py`, which provides:

- Parallel area fetching via `ThreadPoolExecutor`
- Atomic JSON writes with timestamped backups
- Standardised `StandardProperty` / `StandardRoom` dataclasses
- Built-in pagination, error handling, and CLI integration

The original scrapers (UR, SUUMO, RealEstate.co.jp) are standalone but follow the same patterns.

## Viewer

`viewer.html` is a browser-based single-page interface served by `server.py`. Features:

- **Map** — Leaflet.js with marker clustering, area zones, and POI markers (stations, supermarkets, parks, hospitals)
- **Scoring** — 7-dimension scoring system (commute, budget, size, walk time, room type, building age, move-in cost) with A/B/C/D grades
- **Filtering** — Source, prefecture, area, room type, rent range, size, walk time, building age, and text search
- **Preferences panel** — Interactive sliders for all scoring weights and thresholds
- **Profiles** — Save/load scoring preference profiles to localStorage
- **Favourites** — Save listings to localStorage
- **Bookmarking** — URL hash state for sharing filter configurations
- **Scraper controls** — Trigger scraper runs from the UI with status polling

## Server

`server.py` is a Flask backend that serves the viewer and provides an API for triggering scrapers:

- `GET /` — Serves the viewer
- `GET /api/scrapers` — Lists available scrapers with categories (foreigner-friendly, japanese-only, utility)
- `POST /api/scrape` — Starts scraper jobs (up to 4 in parallel, with CSRF origin validation)
- `GET /api/scrape/status` — Polls scraper job progress
- Static file serving with allowlist (prevents directory traversal)

## Utilities

| Script | Purpose |
|---|---|
| `run_all.py` | Orchestrator — runs all scrapers + POI builder in parallel with timeout guards |
| `build_pois.py` | Fetches POIs (stations, supermarkets, parks, etc.) from Overpass API in a single batched query |
| `geocode_properties.py` | Geocodes addresses via Nominatim with caching, rate limiting, and incremental saves |

## Configuration

### CLI Arguments

All scrapers share a common CLI interface:

```
--areas NAME [NAME ...]   Filter to specific area names (partial match)
--max-pages N             Override max pages per area
--delay SECONDS           Override request delay
--output FILE             Override output JSON filename
--workers N               Parallel workers (template-based scrapers)
-v, --verbose             Enable debug logging
--dry-run                 Show URLs without fetching
```

### Area Definitions

Areas are defined in `shared/config.py`. Each area includes coordinates, prefecture, and source-specific codes so a single area list drives all seven scrapers.

### Scoring Configuration

The viewer scores and ranks rooms based on criteria defined in `scoring_config.json`. This file is loaded on startup and deep-merged over the hardcoded defaults — if the file is missing or fails to load, the built-in defaults are used.

You can override everything or just the parts you care about. For example, to only change budget weight and hard max:

```json
{
  "budget": { "hardMax": 300000 },
  "weights": { "budget": 40 }
}
```

#### Config sections

| Key | What it controls |
|---|---|
| `commute.known` | Per-area commute times, transfer counts, and line names |
| `commute.prefectureDefault` | Fallback commute estimates by prefecture |
| `budget` | Ideal rent range, hard max rent, and move-in cost cap |
| `size` | Ideal and acceptable floor area ranges (m²) |
| `walk` | Walk-time thresholds (minutes to station) |
| `roomType` | Score multipliers per layout type (1.0 = best) |
| `prefScores` | Base desirability score per prefecture |
| `buildingAge` | Age thresholds in years (ideal / ok / old) |
| `weights` | How much each factor contributes to the total score |

## Areas Covered

Currently searches 40 areas across 4 prefectures:

| Prefecture | Areas |
|---|---|
| **Saitama** (11) | Kawaguchi, Wako, Urawa, Omiya, Kawagoe, Toda, Warabi, Minami-ku, Chuo-ku, Asaka, Niiza |
| **Chiba** (4) | Ichikawa, Funabashi, Urayasu, Matsudo |
| **Kanagawa** (20) | Kawasaki (4 wards), Yokohama (11 wards), Kamakura, Fujisawa, Chigasaki, + 2 city-level REJ entries |
| **Tokyo** (5) | Kita-ku, Itabashi-ku, Nerima-ku, Adachi-ku, Edogawa-ku |

## Project Structure

```
├── ur_rental_search.py          # UR scraper
├── suumo_search.py              # SUUMO scraper
├── realestate_jp_search.py      # RealEstate.co.jp scraper
├── best_estate_search.py        # Best Estate scraper
├── gaijinpot_search.py          # GaijinPot scraper
├── wagaya_search.py             # Wagaya Japan scraper
├── villagehouse_search.py       # Village House scraper
├── run_all.py                   # Orchestrator (parallel execution)
├── server.py                    # Flask backend for viewer
├── build_pois.py                # POI builder (Overpass API)
├── geocode_properties.py        # Address geocoder (Nominatim)
├── viewer.html                  # Interactive browser-based viewer
├── viewer.js                    # Viewer application logic
├── viewer.css                   # Viewer styles
├── scoring_config.json          # Scoring overrides
├── shared/                      # Shared modules package
│   ├── config.py                #   Area definitions (single source of truth)
│   ├── scraper_template.py      #   BaseScraper class + StandardProperty/Room
│   ├── cli.py                   #   Common CLI argument parser
│   ├── http_client.py           #   HTTP client with retries and delays
│   ├── parsers.py               #   Shared parsing utilities (yen, age, size)
│   └── logging_setup.py         #   Logging configuration
├── tests/                       # Test suite
│   ├── test_*_parser.py        # One per scraper (7 files)
│   ├── test_build_pois.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_geocoder.py
│   ├── test_http_client.py
│   ├── test_parsers.py
│   ├── test_run_all.py
│   ├── test_scraper_template.py
│   ├── test_server.py
│   ├── test_scoring_prefs.js   # JS scoring tests (Node.js)
│   └── fixtures/               # HTML/JSON test fixtures
├── requirements.txt
├── .github/workflows/ci.yml     # CI pipeline
└── .githooks/pre-push           # Pre-push test hook
```

---

## UR Chintai API Reference

### Base URL

```
https://chintai.r6.ur-net.go.jp/chintai/api/
```

Found in the site's JS at `/chintai/common/js/api.js`. All requests are POST with form-encoded data. No authentication required.

> **Note:** The older hostname `chintai.sumai.ur-net.go.jp` (used in some third-party libraries) no longer resolves. The current hostname is `chintai.r6.ur-net.go.jp`.

The public-facing website is at `https://www.ur-net.go.jp/chintai/`.

### Key Concepts

| Term | Meaning | Example |
|---|---|---|
| `block` | Region | `kanto` |
| `tdfk` | Prefecture code (JIS) | `11`=Saitama, `12`=Chiba, `13`=Tokyo, `14`=Kanagawa |
| `skcs` | City/ward code (市区町村) | `203` = Kawaguchi in Saitama |
| `shisya` | Branch office code | `30`=Chiba, `40`=Kanagawa, `50`=Saitama |
| `danchi` | Property complex code | `336` |
| `shikibetu` | Property identifier | Usually `0` |

Property codes appear in URLs as: `{shisya}_{danchi}{shikibetu}` (e.g. `30_3360`).

### Endpoint: Search Properties by Area (what we use)

**`POST bukken/result/bukken_result/`**

Returns a list of all properties in an area with their currently vacant rooms. This is the most efficient endpoint — one call per area returns everything.

```
Form data:
  mode=area
  skcs=203          # city/ward code
  block=kanto       # region
  tdfk=11           # prefecture JIS code
  orderByField=0
  pageSize=100
  pageIndex=0
  shisya=           # empty = all
  danchi=           # empty = all
  shikibetu=        # empty = all
  pageIndexRoom=0
  sp=               # empty for PC, "sp" for mobile
```

**Response:** JSON array of property objects. Each contains:

```json
{
  "shisya": "30",
  "danchi": "336",
  "shikibetu": "0",
  "danchiNm": "ハイタウン塩浜",           // property name
  "place": "市川市塩浜4-2ほか",            // address
  "traffic": "<li>JR...駅 徒歩12分</li>",  // HTML list of station access
  "shikikin": "2か月",                     // deposit (months)
  "requirement": "ナシ",                   // key money
  "kouzou": "鉄筋コンクリート造",          // building type
  "floorAll": "14",                        // total floors
  "allCount": "2",                         // total properties in area
  "roomCount": "1",                        // vacant rooms at this property
  "room": [                                // array of vacant rooms
    {
      "id": "000091107",
      "roomNmMain": "9号棟",               // building number
      "roomNmSub": "1107号室",             // room number
      "type": "1LDK",                      // room layout type
      "floorspace": "50&#13217;",          // size (HTML entity for ㎡)
      "floor": "11階",                     // floor
      "rent": "95,500円",                  // monthly rent
      "rent_normal": "",                   // original rent (if discounted)
      "commonfee": "3,200円",              // monthly common fee
      "madori": "https://...gif",          // floor plan image URL
      "roomDetailLink": "/chintai/...",    // room detail page URL
      "system": [...],                     // discount programs
      "design": [...]                      // renovation status
    }
  ]
}
```

Properties with no vacancies have `"room": []`. Some rooms have empty `rent` — these are "rent on inquiry" (家賃はお問い合わせください) listings.

### Other Endpoints (not used in this script, but documented)

**`POST bukken/search/result_main/`** — Returns area-level metadata (rent ranges, available filters, property count). Same form data as above. Useful for understanding what's available before fetching listings.

**`POST bukken/detail/detail_bukken_room/`** — Get all vacant rooms for a single property.
```
Form data: shisya, danchi, shikibetu, orderByField=0, orderBySort=0, pageIndex=0
```
Returns JSON array of rooms or `null` if no vacancies. Used by the property detail pages.

**`POST bukken/detail/detail_bukken/`** — Get property images, gallery, and overview.
```
Form data: shisya, danchi, shikibetu
```

**`POST bukken/detail/detail_bukken_bukken/`** — Get property amenities (parking, facilities).
```
Form data: shisya, danchi, shikibetu
```

**`POST bukken/detail/detail_bukken_design/`** — Get property building info (structure, year, floor plans).
```
Form data: shisya, danchi, shikibetu
```

**`POST bukken/detail/detail_bukken_tenpo/`** — Get nearest UR office/shop info.
```
Form data: shisya, danchi, shikibetu
```

**`POST bukken/result/bukken_result_room/`** — Get more rooms for a property in search results (pagination).

### Area Code Discovery

Area pages on the website follow this pattern:
```
https://www.ur-net.go.jp/chintai/kanto/{prefecture}/area/{skcs}.html
```

Each page contains an inline `<script>` that calls:
```js
ur.api.bukken.result.initSearch('kanto', '{tdfk}', '{prefecture}', 'area', { skcs: '{skcs}'});
```

To find all available area codes for a prefecture, fetch the prefecture index page and extract area links:
```
https://www.ur-net.go.jp/chintai/kanto/saitama/   → all Saitama area codes
https://www.ur-net.go.jp/chintai/kanto/chiba/      → all Chiba area codes
https://www.ur-net.go.jp/chintai/kanto/kanagawa/   → all Kanagawa area codes
https://www.ur-net.go.jp/chintai/kanto/tokyo/       → all Tokyo area codes
```

### Headers

The API requires a `Referer` header from `www.ur-net.go.jp`. The `X-Requested-With: XMLHttpRequest` header mimics the website's AJAX calls. See the script for the full header set.

### Rate Limiting

No documented rate limits, but be respectful. The script uses a 2-second delay between area requests.

## Development

### Setup

```bash
pip install -r requirements.txt
git config core.hooksPath .githooks
```

The second command enables the pre-push hook, which runs the test suite before every `git push`. If any test fails, the push is blocked.

### Running Tests

```bash
python -m pytest tests/
```

### CI

GitHub Actions runs the test suite on every push to master and on all PRs targeting master. See `.github/workflows/ci.yml`.

## Dependencies

- `flask` — Web server for viewer backend
- `requests` — HTTP client
- `tabulate` — Console table formatting
- `beautifulsoup4` — HTML parsing (SUUMO, RealEstate.co.jp, Best Estate, GaijinPot, Wagaya, Village House)
- `pytest` — Test runner (dev)
- `responses` — HTTP mocking for tests (dev)

## Related Resources

- [UR Chintai website](https://www.ur-net.go.jp/chintai/)
- [urchintai-client](https://github.com/duongntbk/urchintai-client) — Third-party Python async client (uses older hostname)
- [UR API JS source](https://www.ur-net.go.jp/chintai/common/js/api.js) — API base URL config
- [UR Property Detail JS](https://www.ur-net.go.jp/chintai/common/js/api_bukken_detail.js) — Detail page API calls
- [UR Search Results JS](https://www.ur-net.go.jp/chintai/common/js/api_bukken_result.js) — Search/listing API calls
