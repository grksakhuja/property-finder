#!/usr/bin/env python3
"""
Wagaya Japan Rental Search Tool

Scrapes wagaya-japan.com for rental property listings.
Wagaya Japan is foreigner-friendly with no-guarantor options and online process.

Key discovery: All listing data is embedded as a JSON variable `estateDataFromPHP`
in the page source — no HTML parsing needed. We extract this JSON and filter
by address matching to target areas.

Wagaya lists by prefecture (e.g. /en/rent/tokyo/list/), so we search each
prefecture once and match to specific areas by address.
"""

import json
import re
from typing import List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from shared.config import AREAS, Area
from shared.cli import build_arg_parser, filter_areas
from shared.http_client import create_session, fetch_page
from shared.scraper_template import BaseScraper, StandardProperty, StandardRoom

BASE_URL = "https://wagaya-japan.com"

# Japanese prefecture names for address matching
PREFECTURE_JP = {
    "saitama": "埼玉県",
    "chiba": "千葉県",
    "kanagawa": "神奈川県",
    "tokyo": "東京都",
}


class WagayaScraper(BaseScraper):
    SOURCE_NAME = "wagaya"
    BASE_URL = BASE_URL
    OUTPUT_FILE = "results_wagaya.json"
    REQUEST_DELAY = 2.0
    MAX_PAGES_PER_AREA = 1  # All data on one page via JSON
    ITEMS_PER_PAGE = 9999  # No pagination needed
    DEFAULT_WORKERS = 1
    ROOM_TYPE_FILTER = []

    EXTRA_HEADERS = {
        "Accept-Language": "en-US,en;q=0.9",
    }

    def build_url(self, area: Area, page: int = 1) -> str:
        """Construct Wagaya search URL for a prefecture."""
        pref = area.wagaya_prefecture or "tokyo"
        return f"{BASE_URL}/en/rent/{pref}/list/"

    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Extract embedded JSON from Wagaya page source.

        The page contains a script variable `estateDataFromPHP` with all
        listing data as a JSON array. Each item has: id, name, type, lat, lng,
        image, address, price, kyoeki, heibei, heytype, rosen, madori.
        """
        # Extract the JSON data from the script tag.
        # First narrow scope to the relevant <script> block, then extract the array.
        soup = BeautifulSoup(html, "html.parser")
        script_text = ""
        for script in soup.find_all("script"):
            if script.string and "estateDataFromPHP" in script.string:
                script_text = script.string
                break
        if not script_text:
            return []

        # Extract the JSON array using bracket-depth counting for robustness
        start_match = re.search(r"estateDataFromPHP\s*=\s*\[", script_text)
        if not start_match:
            return []

        start_idx = start_match.end() - 1  # position of '['
        depth = 0
        end_idx = start_idx
        for i in range(start_idx, len(script_text)):
            if script_text[i] == '[':
                depth += 1
            elif script_text[i] == ']':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        else:
            return []

        try:
            listings = json.loads(script_text[start_idx:end_idx])
        except json.JSONDecodeError:
            return []

        properties = []
        for item in listings:
            prop = self._parse_listing(item, area)
            if prop and prop.rooms:
                properties.append(prop)

        return properties

    def _parse_listing(self, item: dict, area: Area) -> Optional[StandardProperty]:
        """Parse a single Wagaya JSON listing object."""
        name = item.get("name", "")
        address = item.get("address", "")
        station_info = item.get("rosen", "")
        price_text = item.get("price", "")
        admin_fee_text = item.get("kyoeki", "")
        size_text = item.get("heibei", "")
        layout = item.get("heytype", "") or item.get("madori", "")
        listing_id = item.get("icd", "") or item.get("id", "")

        # Parse rent: "￥50,000" or "50,000" → 50000
        rent_value = self._parse_wagaya_price(price_text)
        if rent_value <= 0:
            return None

        # Parse admin fee
        admin_fee_value = self._parse_wagaya_price(admin_fee_text)

        total_value = rent_value + admin_fee_value

        # Parse size: "(16m²)" or "16m²" or "16" → "16m²"
        clean_size = self._parse_size(size_text)

        # Build detail URL
        detail_url = ""
        if listing_id:
            detail_url = f"{BASE_URL}/en/rent/detail/?icd={quote(str(listing_id), safe='')}"

        room = StandardRoom(
            floor="",
            rent=f"¥{rent_value:,}",
            rent_value=rent_value,
            admin_fee=f"¥{admin_fee_value:,}" if admin_fee_value else "",
            admin_fee_value=admin_fee_value,
            total_value=total_value,
            deposit="",
            deposit_value=0,
            key_money="",
            key_money_value=0,
            layout=layout,
            size=clean_size,
            detail_url=detail_url,
        )

        return StandardProperty(
            name=name,
            address=address,
            access=station_info,
            building_age="",
            building_age_years=-1,
            area_name=area.name,
            prefecture=area.prefecture,
            rooms=[room],
        )

    def _parse_wagaya_price(self, text: str) -> int:
        """Parse Wagaya price formats: '￥50,000', '50,000円', etc."""
        if not text or text.strip() in ("-", "", "0"):
            return 0
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    def _parse_size(self, text: str) -> str:
        """Parse size text into clean format: '16m²'."""
        if not text:
            return ""
        m = re.search(r"([\d.]+)", text)
        if m:
            return f"{m.group(1)}m²"
        return text

    # ------------------------------------------------------------------
    # Address matching
    # ------------------------------------------------------------------

    @staticmethod
    def _build_area_entries(areas: List[Area]) -> List[tuple]:
        """Build (en_name, jp_name, Area) tuples for address matching.

        Wagaya addresses are in English format like:
          "Kawaguchi City, Saitama Prefecture"
          "Kita Ward, Tokyo"
          "Nakahara Ward, Kawasaki City, Kanagawa Prefecture"
        """
        entries = []
        for a in areas:
            en_name = a.name.split("(")[0].strip()
            jp_m = re.search(r"\((.+?)\)", a.name)
            jp_name = jp_m.group(1) if jp_m else ""
            entries.append((en_name, jp_name, a))
        return entries

    @staticmethod
    def _match_area(address: str,
                    area_entries: List[tuple]) -> Optional[Area]:
        """Match property address to a target area.

        Tries English name matching first (primary), then Japanese fallback.
        Handles patterns like:
          "Kawaguchi City" matches "Kawaguchi"
          "Kita Ward" matches "Kita-ku"
          "Niiza City" matches "Niiza"
        """
        if not address:
            return None
        addr_lower = address.lower()

        for en_name, jp_name, a in area_entries:
            en_lower = en_name.lower()
            # Strip -ku/-shi suffix for matching
            base_name = en_lower.replace("-ku", "").replace("-shi", "").strip()
            if base_name and base_name in addr_lower:
                return a
            # Also try the full English name
            if en_lower and en_lower in addr_lower:
                return a
            # Japanese fallback
            if jp_name and jp_name in address:
                return a

        return None

    # ------------------------------------------------------------------
    # Override run() for prefecture-level search with address matching
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Search by prefecture, then match to target areas by address."""
        parser = build_arg_parser(
            self.SOURCE_NAME, f"Search {self.SOURCE_NAME} rental listings")
        args = parser.parse_args()

        if args.verbose:
            self.logger.setLevel("DEBUG")
            for h in self.logger.handlers:
                h.setLevel("DEBUG")

        if args.delay is not None:
            self.REQUEST_DELAY = args.delay
        output_file = args.output or self.OUTPUT_FILE

        # Get all target areas for address matching
        target_areas = filter_areas(AREAS, args.areas)
        area_entries = self._build_area_entries(target_areas)

        # Determine which prefectures to search (deduplicate)
        prefs_to_search = {}
        for a in target_areas:
            if a.wagaya_prefecture and a.wagaya_prefecture not in prefs_to_search:
                prefs_to_search[a.wagaya_prefecture] = a

        self.logger.info("Wagaya Japan Rental Search")
        self.logger.info("Target areas: %d", len(target_areas))
        self.logger.info("Searching %d prefectures: %s",
                         len(prefs_to_search),
                         ", ".join(prefs_to_search.keys()))

        if args.dry_run:
            for pref, a in prefs_to_search.items():
                dummy = Area("dummy", pref, wagaya_prefecture=pref)
                self.logger.info("[DRY RUN] %s", self.build_url(dummy))
            return

        session = create_session(extra_headers=self.EXTRA_HEADERS)

        all_properties: List[StandardProperty] = []
        unmatched_count = 0

        for pref_name, sample_area in prefs_to_search.items():
            self.logger.info("Searching prefecture: %s", pref_name)

            dummy_area = Area(f"Wagaya-{pref_name}", pref_name,
                              wagaya_prefecture=pref_name)
            url = self.build_url(dummy_area)

            try:
                resp = fetch_page(session, url, delay=self.REQUEST_DELAY)
            except Exception as e:
                self.logger.error("Request failed for %s: %s", pref_name, e)
                continue

            try:
                properties = self.parse_page(resp.text, dummy_area)
            except Exception as e:
                self.logger.error("Parse failed for %s: %s", pref_name, e)
                continue

            if not properties:
                self.logger.info("  No listings found for %s", pref_name)
                continue

            self.logger.info("  Found %d total listings", len(properties))

            # Match each property to target areas by address
            matched_count = 0
            for prop in properties:
                matched = self._match_area(prop.address, area_entries)
                if matched:
                    prop.area_name = matched.name
                    prop.prefecture = matched.prefecture
                    all_properties.append(prop)
                    matched_count += 1
                else:
                    unmatched_count += 1

            self.logger.info("  %d matched to target areas, %d discarded",
                             matched_count, len(properties) - matched_count)

        total_rooms = sum(len(p.rooms) for p in all_properties)
        self.logger.info(
            "Done: %d properties with %d rooms in target areas "
            "(%d outside target areas discarded)",
            len(all_properties), total_rooms, unmatched_count)

        self.save_results(all_properties, output_file)


if __name__ == "__main__":
    WagayaScraper().run()
