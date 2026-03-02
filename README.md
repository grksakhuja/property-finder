# UR Housing Rental Search Tool

Queries the UR (Urban Renaissance Agency / 都市再生機構) public API to find available rental properties with prices across target areas in the greater Tokyo region.

**Why UR?** No key money (礼金), no agent fees (仲介手数料), no guarantor needed, foreigner-friendly. Significantly lower upfront costs vs private rentals.

## Quick Start

```bash
pip install -r requirements.txt
python ur_rental_search.py
```

Output: formatted console table + `results.json` file.

## Configuration

Edit the top of `ur_rental_search.py`:

- **`ROOM_TYPE_FILTER`** — List of room types to include, e.g. `["2LDK", "3LDK"]`. Set to `None` for all types.
- **`AREAS`** — List of area dicts to search. Each needs: `name`, `block`, `tdfk`, `tdfk_name`, `skcs`.
- **`REQUEST_DELAY`** — Seconds between API calls (default: 2). Be respectful.

## Scoring Configuration

The viewer scores and ranks rooms based on criteria defined in `scoring_config.json`. This file is loaded on startup and deep-merged over the hardcoded defaults — if the file is missing or fails to load, the built-in defaults are used.

You can override everything or just the parts you care about. For example, to only change budget weight and hard max:

```json
{
  "budget": { "hardMax": 300000 },
  "weights": { "budget": 40 }
}
```

### Config sections

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

Currently searches 36 areas across 4 prefectures:

| Prefecture | Areas |
|---|---|
| **Saitama** (11) | Kawaguchi, Wako, Urawa, Omiya, Kawagoe, Toda, Warabi, Minami-ku, Chuo-ku, Asaka, Niiza |
| **Chiba** (12) | Ichikawa, Funabashi, Urayasu, Matsudo |
| **Kanagawa** (14) | Kawasaki (4 wards), Yokohama (9 wards), Kamakura, Fujisawa, Chigasaki |
| **Tokyo** (13) | Kita-ku, Itabashi-ku, Nerima-ku, Adachi-ku, Edogawa-ku |

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

- `requests` — HTTP client
- `tabulate` — Console table formatting

## Related Resources

- [UR Chintai website](https://www.ur-net.go.jp/chintai/)
- [urchintai-client](https://github.com/duongntbk/urchintai-client) — Third-party Python async client (uses older hostname)
- [UR API JS source](https://www.ur-net.go.jp/chintai/common/js/api.js) — API base URL config
- [UR Property Detail JS](https://www.ur-net.go.jp/chintai/common/js/api_bukken_detail.js) — Detail page API calls
- [UR Search Results JS](https://www.ur-net.go.jp/chintai/common/js/api_bukken_result.js) — Search/listing API calls
