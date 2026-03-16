#!/usr/bin/env python3
"""
Best Estate Rental Search Tool

Scrapes best-estate.jp for rental property listings filtered by room type.
Best Estate is a foreigner-focused rental site with 182K+ listings.
Uses server-rendered HTML (Next.js SSR) — no JS execution needed.

Key discovery: The `layouts` URL parameter with double-URL-encoded JSON
genuinely filters server-side, reducing 182K listings to ~2,776 for target
room types. The `prefecture` parameter is ignored when `layouts` is present,
so we do ONE nationwide paginated search and match to target areas by address.

See BEST_ESTATE_FILTER_INVESTIGATION.md for full details.
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from shared.cli import build_arg_parser, filter_areas
from shared.config import AREAS, Area, get_target_room_types
from shared.http_client import create_session, fetch_page
from shared.logging_setup import setup_logging
from shared.parsers import parse_yen, parse_year_to_age
from shared.scraper_template import BaseScraper, StandardProperty, StandardRoom, safe_write_json

BASE_URL = "https://www.best-estate.jp"
ALLOWED_HOSTS = {"www.best-estate.jp", "best-estate.jp"}

# Layout type codes for the `layouts` URL parameter.
# Maps room type names (from scoring_config.json) to the {amount, type_code}
# format that best-estate.jp expects. Verified individually via testing.
LAYOUT_TYPE_CODES: Dict[str, Dict[str, int]] = {
    "1LDK":  {"amount": 1, "type_code": 7},
    "2LDK":  {"amount": 2, "type_code": 7},
    "2SLDK": {"amount": 2, "type_code": 8},
    "3LDK":  {"amount": 3, "type_code": 7},
    "3SLDK": {"amount": 3, "type_code": 8},
    "3DK":   {"amount": 3, "type_code": 3},
    "3K":    {"amount": 3, "type_code": 2},
}


CHECKPOINT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "results_best_estate_checkpoint.json")
PARALLEL_WORKERS = 2
STAGGER_DELAY = 0.75


class BestEstateScraper(BaseScraper):
    SOURCE_NAME = "best_estate"
    BASE_URL = BASE_URL
    OUTPUT_FILE = "results_best_estate.json"
    REQUEST_DELAY = 1.5  # site shows no rate limiting; retry adapter handles 429s
    MAX_PAGES = 140    # ~2,776 listings / 20 per page ≈ 139 pages
    MAX_PAGES_PER_AREA = 140  # kept for BaseScraper compatibility
    ITEMS_PER_PAGE = 20
    DEFAULT_WORKERS = 1  # single nationwide search, not per-area
    ROOM_TYPE_FILTER = []

    def __init__(self):
        super().__init__()
        self._target_layouts = self._get_target_layouts()
        self._encoded_layouts = self._encode_layouts(self._target_layouts)

    @staticmethod
    def _encode_layouts(layouts: List[Dict[str, int]]) -> str:
        """Double-URL-encode the layouts JSON the way best-estate.jp expects.

        Encoding steps:
        1. JSON-serialize with no spaces: [{"amount":2,"type_code":7}]
        2. URL-encode once, keeping [] only → [%7B%22amount%22%3A2%2C%22type_code%22%3A7%7D]
        3. Re-encode only the commas: %2C → %252C
        """
        json_str = json.dumps(layouts, separators=(",", ":"))
        single_encoded = quote(json_str, safe="[]")
        return single_encoded.replace("%2C", "%252C")

    def _get_target_layouts(self) -> List[Dict[str, int]]:
        """Get layout codes for room types from scoring_config.json."""
        room_types = get_target_room_types()
        return [LAYOUT_TYPE_CODES[rt] for rt in room_types if rt in LAYOUT_TYPE_CODES]

    def build_url(self, area: Area = None, page: int = 1) -> str:
        """Construct Best Estate search URL with layouts filter.

        Note: `prefecture` is intentionally omitted — it's ignored by the
        server when `layouts` is present. We do a nationwide search and
        match properties to areas by address instead.
        """
        url = (
            f"{BASE_URL}/ja/search/"
            f"?min_price=60000"
            f"&max_price=200000"
            f"&layouts={self._encoded_layouts}"
        )
        if page > 1:
            url += f"&current_page={page}"
        return url

    # Japanese prefecture names for address validation
    PREFECTURE_JP = {
        "saitama": "埼玉県",
        "chiba": "千葉県",
        "kanagawa": "神奈川県",
        "tokyo": "東京都",
    }

    def _build_area_jp_map(self, areas: List[Area]) -> List[tuple]:
        """Build list of (jp_name, prefecture_jp, Area) for address matching.

        Extracts the Japanese text in parentheses from area names:
        "Kawaguchi (川口市)" → "川口市"

        Returns a list (not dict) because ward names like 南区 and 中区
        exist in multiple cities; we need to check prefecture too.
        """
        entries = []
        for area in areas:
            jp_name = area.jp_name
            if jp_name:
                pref_jp = self.PREFECTURE_JP.get(area.prefecture, "")
                entries.append((jp_name, pref_jp, area))
        return entries

    def _match_area(self, address: str,
                    area_entries: List[tuple]) -> Optional[Area]:
        """Match a property address to a target area.

        Checks both the Japanese area name AND the prefecture to avoid
        false positives (e.g. 南区 in Hiroshima vs Yokohama).
        """
        for jp_name, pref_jp, area in area_entries:
            if jp_name in address and pref_jp in address:
                return area
        return None

    # ------------------------------------------------------------------
    # Checkpointing helpers
    # ------------------------------------------------------------------

    def _load_checkpoint(self) -> tuple:
        """Load checkpoint if it exists. Returns (properties, next_page)."""
        if not os.path.exists(CHECKPOINT_FILE):
            return [], 1
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                cp = json.load(f)
            properties = []
            for p in cp.get("properties", []):
                rooms = [StandardRoom(**r) for r in p.get("rooms", [])]
                prop_data = {k: v for k, v in p.items() if k != "rooms"}
                properties.append(StandardProperty(**prop_data, rooms=rooms))
            next_page = cp.get("next_page", 1)
            self.logger.info("Resuming from checkpoint: %d properties, page %d",
                             len(properties), next_page)
            return properties, next_page
        except Exception as e:
            self.logger.warning("Ignoring bad checkpoint: %s", e)
            return [], 1

    def _save_checkpoint(self, properties: List[StandardProperty],
                         next_page: int) -> None:
        """Save checkpoint after each page batch."""
        data = {
            "next_page": next_page,
            "properties": [],
        }
        for prop in properties:
            pd = {
                "name": prop.name,
                "address": prop.address,
                "access": prop.access,
                "building_age": prop.building_age,
                "building_age_years": prop.building_age_years,
                "area_name": prop.area_name,
                "prefecture": prop.prefecture,
                "rooms": [asdict(r) for r in prop.rooms],
            }
            data["properties"].append(pd)
        safe_write_json(data, CHECKPOINT_FILE)

    def _delete_checkpoint(self) -> None:
        """Remove checkpoint file after successful completion."""
        if os.path.exists(CHECKPOINT_FILE):
            os.unlink(CHECKPOINT_FILE)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Nationwide paginated search with layouts filter, then area matching.

        Features:
        - Parallel page fetching (2 workers with staggered delays)
        - Page-level checkpointing for crash recovery
        - Area matching by address
        """
        parser = build_arg_parser(
            self.SOURCE_NAME, f"Search {self.SOURCE_NAME} rental listings")
        args = parser.parse_args()

        if args.verbose:
            self.logger.setLevel("DEBUG")
            for h in self.logger.handlers:
                h.setLevel("DEBUG")

        max_pages = args.max_pages if args.max_pages is not None else self.MAX_PAGES
        if args.delay is not None:
            self.REQUEST_DELAY = args.delay
        output_file = args.output or self.OUTPUT_FILE

        # Get ALL areas for address matching — since we search nationwide,
        # we match against every area in AREAS (not just best_estate ones)
        target_areas = filter_areas(AREAS, args.areas)
        area_entries = self._build_area_jp_map(target_areas)

        self.logger.info("Best Estate Rental Search (layouts filter)")
        self.logger.info("Target room types: %s",
                         ", ".join(LAYOUT_TYPE_CODES.keys()))
        self.logger.info("Target areas: %d (%s)", len(target_areas),
                         ", ".join(a.name for a in target_areas))
        self.logger.info("Max pages: %d", max_pages)

        if args.dry_run:
            self.logger.info("[DRY RUN] %s", self.build_url())
            return

        session = create_session(extra_headers={
            "Accept-Language": "ja,en;q=0.9",
        })

        # Load checkpoint for crash recovery
        all_properties, start_page = self._load_checkpoint()
        unmatched_count = 0
        stop = False
        workers = PARALLEL_WORKERS

        # Note: self.REQUEST_DELAY is set above before the ThreadPoolExecutor
        # starts, so workers always see the final value.

        def _fetch_page(page_num: int, worker_idx: int):
            """Fetch and parse a single page. Returns (page_num, properties) or raises."""
            if worker_idx > 0:
                time.sleep(STAGGER_DELAY * worker_idx)
            url = self.build_url(page=page_num)
            resp = fetch_page(
                session, url,
                delay=self.REQUEST_DELAY if page_num > start_page else 0)
            dummy_area = Area("Nationwide", "all")
            return page_num, self.parse_page(resp.text, dummy_area)

        page_num = start_page
        while page_num <= max_pages and not stop:
            # Build batch of pages to fetch in parallel
            batch_pages = list(range(page_num, min(page_num + workers, max_pages + 1)))

            # Fetch batch
            results = {}
            try:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(_fetch_page, p, i): p
                        for i, p in enumerate(batch_pages)
                    }
                    for future in as_completed(futures):
                        p = futures[future]
                        try:
                            pn, props = future.result()
                            results[pn] = props
                        except requests.RequestException as e:
                            self.logger.error("Request failed (page %d): %s", p, e)
                            stop = True
                        except Exception as e:
                            self.logger.error("Parse failed (page %d): %s", p, e)
                            stop = True
            except Exception as e:
                self.logger.error("Batch fetch error: %s", e)
                break

            # Process results in page order
            for bp in batch_pages:
                if bp not in results:
                    stop = True
                    break

                properties = results[bp]
                if not properties:
                    if bp == 1:
                        self.logger.info("No listings found")
                    else:
                        self.logger.info("No more listings after page %d",
                                         bp - 1)
                    stop = True
                    break

                # Match each property to a target area by address
                page_matched = 0
                page_rooms = 0
                for prop in properties:
                    for room in prop.rooms:
                        page_rooms += 1
                    matched_area = self._match_area(prop.address, area_entries)
                    if matched_area:
                        prop.area_name = matched_area.name
                        prop.prefecture = matched_area.prefecture
                        all_properties.append(prop)
                        page_matched += 1
                    else:
                        unmatched_count += 1

                self.logger.info(
                    "Page %d: %d rooms, %d matched to target areas, "
                    "%d discarded",
                    bp, page_rooms, page_matched,
                    len(properties) - page_matched)

                # Stop if fewer results than a full page
                if page_rooms < self.ITEMS_PER_PAGE:
                    stop = True
                    break

            # Advance page counter only for pages actually processed
            pages_processed = sum(1 for bp in batch_pages if bp in results)
            page_num += pages_processed
            self._save_checkpoint(all_properties, page_num)

        total_rooms = sum(len(p.rooms) for p in all_properties)
        self.logger.info(
            "Done: %d properties with %d rooms in target areas "
            "(%d properties outside target areas discarded)",
            len(all_properties), total_rooms, unmatched_count)

        self.save_results(all_properties, output_file)
        self._delete_checkpoint()

    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Parse a Best Estate search results page into StandardProperty objects.

        Page structure (Next.js SSR with React Server Component streaming):
        - Property cards: div with class containing 'lg:border-t-4'
          - Building info: div.bg-beu-gray-light3 with <h4> name, <p> address/access/built
          - Room rows: div with class 'border-y-[1px] border-beu-border'
            - Rent: span.text-beu-primary (bold price)
            - Floor: span with 'X 階'
            - Fees grid: div.grid-rows-3 (管理費, 敷金, 礼金)
            - Layout/size summary: p.my-2 ("2LDK / 55.5㎡ / 3階")
        - Detail URLs: in hidden div[id^=S:] swapped into template[id^=P:] via $RS scripts
        - Room data for most cards is streamed via React SC and lives in hidden
          divs — templates inside cards act as placeholders. We resolve these
          before parsing to reconstruct the complete card content.
        """
        soup = BeautifulSoup(html, "html.parser")
        properties = []

        # Build $RS template→hidden-div mapping and detail URL mapping
        rs_map = self._build_rs_map(soup)
        detail_url_map = self._build_detail_url_map(soup)

        # Resolve streamed content: replace <template id="P:X"> with
        # the corresponding hidden <div id="S:X"> children
        self._resolve_templates(soup, rs_map)

        # Track which room rows we've already processed (via property cards)
        processed_rows = set()

        # 1. Find property cards (main SSR-rendered listings)
        property_cards = soup.find_all(
            "div", class_=re.compile(r"lg:border-t-4"))

        for card in property_cards:
            # Mark all room rows in this card as processed
            for row in card.find_all(
                    "div", class_=re.compile(r"border-y-\[1px\].*border-beu-border")):
                processed_rows.add(id(row))

            prop = self._parse_property_card(card, area, detail_url_map)
            if prop and prop.rooms:
                properties.append(prop)

        # 2. Find orphan room rows (React streaming additions without card wrapper)
        all_room_rows = soup.find_all(
            "div", class_=re.compile(r"border-y-\[1px\].*border-beu-border"))
        orphan_rooms = []
        for row in all_room_rows:
            if id(row) in processed_rows:
                continue
            room = self._parse_room_row(row, detail_url_map)
            if room is not None:
                orphan_rooms.append(room)

        if orphan_rooms:
            self.logger.debug(
                "%d orphan rooms from React streaming (no building info, "
                "will be discarded during area matching)", len(orphan_rooms))

        return properties

    def _build_rs_map(self, soup: BeautifulSoup) -> dict:
        """Build mapping from template P:X → hidden div S:X id via $RS scripts."""
        rs_map = {}
        for script in soup.find_all("script"):
            text = script.string or ""
            for match in re.finditer(r'\$RS\("(S:\w+)","(P:\w+)"\)', text):
                s_id, p_id = match.group(1), match.group(2)
                rs_map[p_id] = s_id
        return rs_map

    def _resolve_templates(self, soup: BeautifulSoup, rs_map: dict) -> None:
        """Replace <template id="P:X"> placeholders with hidden div content.

        React Server Components stream room data into hidden divs and use
        $RS scripts to swap them into template placeholders at runtime.
        We simulate this by moving the hidden div's children into the
        template's parent, replacing the template element.
        """
        for template in soup.find_all("template"):
            t_id = template.get("id", "")
            s_id = rs_map.get(t_id)
            if not s_id:
                continue
            hidden_div = soup.find("div", id=s_id)
            if not hidden_div:
                continue
            # Check if the hidden div has room-row data (not just a detail link)
            if not hidden_div.find("div", class_=re.compile(
                    r"border-y-\[1px\]")):
                continue
            # Insert hidden div children before the template, then remove it
            parent = template.parent
            if not parent:
                continue
            for child in list(hidden_div.children):
                template.insert_before(child.extract())
            template.decompose()

    def _build_detail_url_map(self, soup: BeautifulSoup) -> dict:
        """Build mapping from template P:X ID → property detail URL.

        React Server Components use $RS("S:X","P:X") scripts to swap
        hidden div content into template placeholders.
        """
        # Map S:X → property URL from hidden divs
        s_to_url = {}
        for div in soup.find_all("div", attrs={"hidden": True}):
            div_id = div.get("id", "")
            link = div.find("a", href=re.compile(r"/ja/property/\d+/"))
            if link:
                href = link["href"]
                # Ensure absolute URL
                if href.startswith("/"):
                    href = f"{BASE_URL}{href}"
                # Validate domain to prevent open redirects
                parsed = urlparse(href)
                if parsed.netloc not in ALLOWED_HOSTS:
                    continue
                s_to_url[div_id] = href

        # Map P:X → S:X from $RS scripts
        p_to_url = {}
        for script in soup.find_all("script"):
            text = script.string or ""
            for match in re.finditer(r'\$RS\("(S:\w+)","(P:\w+)"\)', text):
                s_id, p_id = match.group(1), match.group(2)
                if s_id in s_to_url:
                    p_to_url[p_id] = s_to_url[s_id]

        return p_to_url

    def _parse_property_card(self, card, area: Area,
                             detail_url_map: dict) -> StandardProperty:
        """Parse a single property card into a StandardProperty."""
        # --- Building-level info ---
        info_div = card.find("div", class_=re.compile(r"bg-beu-gray-light3"))
        name = ""
        address = ""
        access_lines = []
        building_age_text = ""

        if info_div:
            # Building name from <h4>
            h4 = info_div.find("h4")
            name = h4.get_text(strip=True) if h4 else ""

            # <p> tags: address, access lines, built date
            ps = info_div.find_all("p")
            for p in ps:
                text = p.get_text(strip=True)
                if not text:
                    continue
                if re.match(r"^\d{4}年", text):
                    # Built date like "2010年 9月"
                    building_age_text = text
                elif "徒歩" in text or "バス" in text:
                    access_lines.append(text)
                elif not address:
                    # First non-date, non-access <p> is the address
                    address = text

        access = " / ".join(access_lines)
        building_age_years = parse_year_to_age(building_age_text)

        # --- Room-level data ---
        rooms = []
        room_rows = card.find_all(
            "div", class_=re.compile(r"border-y-\[1px\].*border-beu-border"))

        for row in room_rows:
            room = self._parse_room_row(row, detail_url_map)
            if room is None:
                continue
            rooms.append(room)

        return StandardProperty(
            name=name,
            address=address,
            access=access,
            building_age=building_age_text,
            building_age_years=building_age_years,
            area_name=area.name,
            prefecture=area.prefecture,
            rooms=rooms,
        )

    def _parse_room_row(self, row, detail_url_map: dict) -> StandardRoom:
        """Parse a single room row from a property card."""
        # Rent (bold primary-colored span)
        rent_el = row.find("span", class_=re.compile(r"text-beu-primary"))
        rent_text = rent_el.get_text(strip=True) if rent_el else ""
        rent_value = parse_yen(rent_text + "円") if rent_text else 0
        rent_display = f"{rent_text}円" if rent_text else ""

        if rent_value <= 0:
            return None

        # Mobile summary: "2LDK / 55.5㎡ / 3階"
        summary = row.find("p", class_="my-2")
        layout = ""
        size_text = ""
        floor_text = ""
        if summary:
            parts = [s.get_text(strip=True)
                     for s in summary.find_all("span")]
            # Filter out separator "/"
            parts = [p for p in parts if p != "/"]
            if len(parts) >= 1:
                layout = parts[0]
            if len(parts) >= 2:
                size_text = parts[1]
            if len(parts) >= 3:
                floor_text = parts[2]

        # Fee grid (管理費, 敷金, 礼金)
        admin_fee_text = ""
        deposit_text = ""
        key_money_text = ""

        fee_grid = row.find("div", class_=re.compile(r"grid-rows-3"))
        if fee_grid:
            labels_and_values = self._parse_fee_grid(fee_grid)
            admin_fee_text = labels_and_values.get("管理費", "")
            deposit_text = labels_and_values.get("敷金", "")
            key_money_text = labels_and_values.get("礼金", "")

        admin_fee_value = parse_yen(admin_fee_text)
        deposit_value = parse_yen(deposit_text)
        key_money_value = parse_yen(key_money_text)
        total_value = rent_value + admin_fee_value

        # Detail URL from template mapping or direct link
        detail_url = ""
        templates = row.find_all("template")
        for t in templates:
            t_id = t.get("id", "")
            if t_id in detail_url_map:
                detail_url = detail_url_map[t_id]
                break

        # Fallback: check for direct links (orphan rows from React streaming)
        if not detail_url:
            direct_link = row.find("a", href=re.compile(r"/ja/property/\d+/"))
            if direct_link:
                href = direct_link["href"]
                if href.startswith("/"):
                    href = f"{BASE_URL}{href}"
                parsed = urlparse(href)
                if parsed.netloc in ALLOWED_HOSTS:
                    detail_url = href

        return StandardRoom(
            floor=floor_text,
            rent=rent_display,
            rent_value=rent_value,
            admin_fee=admin_fee_text,
            admin_fee_value=admin_fee_value,
            total_value=total_value,
            deposit=deposit_text,
            deposit_value=deposit_value,
            key_money=key_money_text,
            key_money_value=key_money_value,
            layout=layout,
            size=size_text,
            detail_url=detail_url,
        )

    def _parse_fee_grid(self, grid) -> dict:
        """Parse the 2-column fee grid (label → value pairs)."""
        result = {}
        children = list(grid.children)
        # Grid has pairs: <div class="border...">Label</div><span>Value</span>
        label = None
        for child in children:
            if not hasattr(child, "name") or not child.name:
                continue
            text = child.get_text(strip=True)
            if child.name == "div" and "border" in " ".join(child.get("class", [])):
                label = text
            elif child.name == "span" and label:
                result[label] = text
                label = None
        return result

if __name__ == "__main__":
    BestEstateScraper().run()
