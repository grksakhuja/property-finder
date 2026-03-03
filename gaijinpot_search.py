#!/usr/bin/env python3
"""
GaijinPot Apartments Rental Search Tool

Scrapes apartments.gaijinpot.com for rental property listings.
GaijinPot is 100% foreigner-friendly, English-first, with ~25K listings.
Uses server-rendered HTML — no JS execution needed.

Key discovery: The `prefecture_id` URL parameter does NOT filter results
server-side — all listings are returned regardless. So we do a nationwide
paginated search and match properties to target areas by English address
(similar to Best Estate pattern).

HTML structure:
- Each listing: div.property-listing > div.listing-body + div.listing-info
- Title: div.listing-title > a > span.text-semi-strong (layout) + span (location)
- Rent: div.listing-body > div.listing-right-col > div.listing-item with "Monthly Costs"
- Details: div.listing-info > div.listing-right-col > div.listing-item with span.text-strong labels
"""

import datetime
import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from shared.config import AREAS, Area
from shared.cli import build_arg_parser, filter_areas
from shared.http_client import create_session, fetch_page
from shared.scraper_template import BaseScraper, StandardProperty, StandardRoom

BASE_URL = "https://apartments.gaijinpot.com"
ALLOWED_HOSTS = {"apartments.gaijinpot.com"}


class GaijinPotScraper(BaseScraper):
    SOURCE_NAME = "gaijinpot"
    BASE_URL = BASE_URL
    OUTPUT_FILE = "results_gaijinpot.json"
    REQUEST_DELAY = 1.5
    MAX_PAGES = 100  # ~25K listings / 15 per page, but we stop early via matching
    MAX_PAGES_PER_AREA = 100
    ITEMS_PER_PAGE = 15
    DEFAULT_WORKERS = 1
    ROOM_TYPE_FILTER = []

    EXTRA_HEADERS = {
        "Accept-Language": "en-US,en;q=0.9",
    }

    def build_url(self, area: Area = None, page: int = 1) -> str:
        """Construct GaijinPot search URL (nationwide)."""
        url = (
            f"{BASE_URL}/en/rent/listing"
            f"?min_price=50000"
            f"&max_price=200000"
        )
        if page > 1:
            url += f"&page={page}"
        return url

    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Parse GaijinPot search results page.

        Each listing represents a single room/unit, so each becomes one
        StandardProperty with one StandardRoom.
        """
        soup = BeautifulSoup(html, "html.parser")
        properties = []

        listings = soup.find_all("div", class_="property-listing")
        for listing in listings:
            prop = self._parse_listing(listing, area)
            if prop and prop.rooms:
                properties.append(prop)

        return properties

    def _parse_listing(self, listing, area: Area) -> Optional[StandardProperty]:
        """Parse a single GaijinPot listing div.

        Structure:
        div.property-listing
          div.listing-body
            div.listing-left-col (image)
            div.listing-right-col
              div.listing-item.listing-title (layout, location, link)
              div.listing-item (Monthly Costs ¥xxx)
              div.listing-item (Available Now / date)
          div.listing-info
            div.listing-left-col (agency logo)
            div.listing-right-col
              div.listing-item (Size)
              div.listing-item (Deposit)
              div.listing-item (Key Money)
              div.listing-item (Floor)
              div.listing-item (Year Built)
              div.listing-item (Nearest Station)
        """
        # --- Title section ---
        title_div = listing.find("div", class_="listing-title")
        layout = ""
        location = ""
        detail_url = ""

        if title_div:
            strong = title_div.find("span", class_="text-semi-strong")
            if strong:
                layout = strong.get_text(strip=True)

            # Location: spans that aren't the layout
            for span in title_div.find_all("span"):
                if span == strong:
                    continue
                text = span.get_text(" ", strip=True)
                if text:
                    location = text
                    break

            link = title_div.find("a")
            if link:
                href = link.get("href", "")
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                elif href.startswith("http"):
                    parsed = urlparse(href)
                    if parsed.netloc in ALLOWED_HOSTS:
                        detail_url = href

        # --- Monthly costs from listing-body ---
        rent_text = ""
        body = listing.find("div", class_="listing-body")
        if body:
            right_col = body.find("div", class_="listing-right-col")
            if right_col:
                for item in right_col.find_all("div", class_="listing-item"):
                    text = item.get_text(" ", strip=True)
                    if "Monthly" in text:
                        rent_text = text

        # --- Details from listing-info ---
        size_text = ""
        deposit_text = ""
        key_money_text = ""
        floor_text = ""
        year_built_text = ""
        station_text = ""

        info_div = listing.find("div", class_="listing-info")
        if info_div:
            right_col = info_div.find("div", class_="listing-right-col")
            if right_col:
                for item in right_col.find_all("div", class_="listing-item"):
                    label_el = item.find("span", class_="text-strong")
                    if not label_el:
                        continue
                    label = label_el.get_text(strip=True)
                    # Value is the full text minus the label
                    full_text = item.get_text(" ", strip=True)
                    value = full_text.replace(label, "", 1).strip()

                    label_lower = label.lower()
                    if "size" in label_lower:
                        size_text = value
                    elif "deposit" in label_lower:
                        deposit_text = value
                    elif "key money" in label_lower:
                        key_money_text = value
                    elif "floor" in label_lower:
                        floor_text = value
                    elif "year" in label_lower or "built" in label_lower:
                        year_built_text = value
                    elif "station" in label_lower or "nearest" in label_lower:
                        station_text = value

        # --- Parse values ---
        rent_value = self._parse_yen(rent_text)
        if rent_value <= 0:
            return None

        deposit_value = self._parse_yen(deposit_text)
        key_money_value = self._parse_yen(key_money_text)
        total_value = rent_value  # GaijinPot "Monthly Costs" often includes admin fee

        building_age_years = self._parse_year_built(year_built_text)

        # Clean layout: "1K Apartment" → "1K"
        clean_layout = layout
        for suffix in [" Apartment", " Mansion", " House", " Condo",
                       " Guesthouse", " Share House"]:
            clean_layout = clean_layout.replace(suffix, "")

        room = StandardRoom(
            floor=floor_text,
            rent=f"¥{rent_value:,}",
            rent_value=rent_value,
            admin_fee="",
            admin_fee_value=0,
            total_value=total_value,
            deposit=deposit_text,
            deposit_value=deposit_value,
            key_money=key_money_text,
            key_money_value=key_money_value,
            layout=clean_layout,
            size=size_text,
            detail_url=detail_url,
        )

        return StandardProperty(
            name=location or layout,
            address=location,
            access=station_text,
            building_age=year_built_text,
            building_age_years=building_age_years,
            area_name=area.name,
            prefecture=area.prefecture,
            rooms=[room],
        )

    @staticmethod
    def _parse_yen(text: str) -> int:
        """Parse yen: '¥80,000', 'Monthly Costs ¥150,490', '¥0', 'None', etc."""
        if not text or text.strip().lower() in ("none", "n/a", "-", "free"):
            return 0
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    @staticmethod
    def _parse_year_built(text: str) -> int:
        """Parse year built: '2010', 'Built in 2010'. Returns age in years."""
        if not text:
            return -1
        m = re.search(r"(\d{4})", text)
        if m:
            built_year = int(m.group(1))
            current_year = datetime.datetime.now().year
            return max(0, current_year - built_year)
        return -1

    # ------------------------------------------------------------------
    # English address matching
    # ------------------------------------------------------------------

    @staticmethod
    def _build_area_match_entries(areas: List[Area]) -> List[tuple]:
        """Build (en_name, jp_name, prefecture, Area) tuples for matching.

        GaijinPot addresses are English like:
          "in Kawaguchi Kawaguchi-shi, Saitama"
          "in Kita-ku, Tokyo"
        We match by both English and Japanese names.
        """
        entries = []
        for a in areas:
            # English name: "Kawaguchi (川口市)" → "Kawaguchi"
            en_name = a.name.split("(")[0].strip()
            # Japanese name from parentheses
            jp_m = re.search(r"\((.+?)\)", a.name)
            jp_name = jp_m.group(1) if jp_m else ""
            entries.append((en_name, jp_name, a.prefecture, a))
        return entries

    @staticmethod
    def _match_area(address: str,
                    entries: List[tuple]) -> Optional[Area]:
        """Match GaijinPot English address to target area.

        Addresses look like:
          "in Kawaguchi Kawaguchi-shi, Saitama"
          "in Kita-ku, Tokyo"
          "in Nakahara-ku Kawasaki-shi, Kanagawa"
        """
        if not address:
            return None
        addr_lower = address.lower()

        # Map English prefecture names to our keys
        pref_map = {
            "saitama": "saitama",
            "chiba": "chiba",
            "kanagawa": "kanagawa",
            "tokyo": "tokyo",
        }

        # Detect prefecture from address
        addr_pref = None
        for pref_en, pref_key in pref_map.items():
            if pref_en in addr_lower:
                addr_pref = pref_key
                break

        for en_name, jp_name, area_pref, area in entries:
            # Skip if prefecture doesn't match (avoids "Minami-ku" in wrong city)
            if addr_pref and addr_pref != area_pref:
                continue

            # Try English name match (case-insensitive, hyphenated variants)
            en_lower = en_name.lower()
            if en_lower and en_lower in addr_lower:
                return area

            # Try Japanese name match
            if jp_name and jp_name in address:
                return area

        return None

    # ------------------------------------------------------------------
    # Override run() for nationwide search with address matching
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Nationwide paginated search, then match to target areas by address."""
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

        target_areas = filter_areas(AREAS, args.areas)
        match_entries = self._build_area_match_entries(target_areas)

        self.logger.info("GaijinPot Rental Search (nationwide + area matching)")
        self.logger.info("Target areas: %d (%s)", len(target_areas),
                         ", ".join(a.name for a in target_areas[:5]))
        self.logger.info("Max pages: %d", max_pages)

        if args.dry_run:
            self.logger.info("[DRY RUN] %s", self.build_url())
            return

        session = create_session(extra_headers=self.EXTRA_HEADERS)

        all_properties: List[StandardProperty] = []
        unmatched_count = 0

        for page_num in range(1, max_pages + 1):
            url = self.build_url(page=page_num)

            try:
                resp = fetch_page(
                    session, url,
                    delay=self.REQUEST_DELAY if page_num > 1 else 0)
            except Exception as e:
                self.logger.error("Request failed (page %d): %s", page_num, e)
                break

            dummy_area = Area("Nationwide", "all")
            try:
                properties = self.parse_page(resp.text, dummy_area)
            except Exception as e:
                self.logger.error("Parse failed (page %d): %s", page_num, e)
                break

            if not properties:
                if page_num == 1:
                    self.logger.info("No listings found")
                break

            # Match each property to target areas
            page_matched = 0
            for prop in properties:
                matched = self._match_area(prop.address, match_entries)
                if matched:
                    prop.area_name = matched.name
                    prop.prefecture = matched.prefecture
                    all_properties.append(prop)
                    page_matched += 1
                else:
                    unmatched_count += 1

            room_count = sum(len(p.rooms) for p in properties)
            self.logger.info(
                "Page %d: %d listings, %d matched, %d discarded",
                page_num, len(properties), page_matched,
                len(properties) - page_matched)

            if room_count < self.ITEMS_PER_PAGE:
                break

        total_rooms = sum(len(p.rooms) for p in all_properties)
        self.logger.info(
            "Done: %d properties with %d rooms in target areas "
            "(%d outside target areas discarded)",
            len(all_properties), total_rooms, unmatched_count)

        self.save_results(all_properties, output_file)


if __name__ == "__main__":
    GaijinPotScraper().run()
