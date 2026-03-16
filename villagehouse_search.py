#!/usr/bin/env python3
"""
Village House Rental Search Tool

Scrapes villagehouse.jp for rental property listings.
Village House is 100% foreigner-friendly, budget-focused (renovated older buildings).
Always zero deposit/key money.

Village House renders property listings server-side with these classes:
- Community cards: div.container-search-cards-community-wrap (building info)
- Unit cards: li.container-search-cards-unit-wrap (room details)

URL pattern: /en/rent/{region}/{prefecture}/
Village House doesn't reliably filter by city — we search at prefecture level.
"""

import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from shared.config import Area, get_areas_for_source
from shared.cli import build_arg_parser, filter_areas
from shared.http_client import create_session, fetch_page
from shared.parsers import parse_digits_as_yen
from shared.scraper_template import BaseScraper, StandardProperty, StandardRoom

BASE_URL = "https://www.villagehouse.jp"
ALLOWED_HOSTS = {"www.villagehouse.jp", "villagehouse.jp"}


class VillageHouseScraper(BaseScraper):
    SOURCE_NAME = "villagehouse"
    BASE_URL = BASE_URL
    OUTPUT_FILE = "results_villagehouse.json"
    REQUEST_DELAY = 1.5
    MAX_PAGES_PER_AREA = 5
    ITEMS_PER_PAGE = 10  # Community cards per page
    DEFAULT_WORKERS = 2
    ROOM_TYPE_FILTER = []

    EXTRA_HEADERS = {
        "Accept-Language": "en-US,en;q=0.9",
    }

    def build_url(self, area: Area, page: int = 1) -> str:
        """Construct Village House search URL at prefecture level."""
        region = area.villagehouse_region or "kanto"
        prefecture = area.villagehouse_prefecture or "kanagawa"
        url = f"{BASE_URL}/en/rent/{region}/{prefecture}/"
        if page > 1:
            url += f"?page={page}"
        return url

    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Parse Village House listing page.

        Structure:
        - Community cards (div.container-search-cards-community-wrap): building info
        - Unit cards (li.container-search-cards-unit-wrap): room details
        - Units follow their parent community card in DOM order
        """
        soup = BeautifulSoup(html, "html.parser")
        properties = []

        # Find all community (building) cards
        community_cards = soup.find_all(
            "div", class_="container-search-cards-community-wrap")

        if not community_cards:
            return []

        # Find all unit cards (they're in a list after each community card)
        # Build a mapping: community card → unit cards
        # Units are within the same parent container
        all_units = soup.find_all(
            "li", class_="container-search-cards-unit-wrap")

        # Group units by their preceding community card
        # We use position in the document to match
        all_elements = soup.find_all(
            class_=re.compile(
                r"container-search-cards-community-wrap|container-search-cards-unit-wrap"))

        current_community = None
        community_units = {}

        for el in all_elements:
            classes = el.get("class", [])
            if "container-search-cards-community-wrap" in classes:
                current_community = el
                community_units[id(el)] = []
            elif "container-search-cards-unit-wrap" in classes and current_community:
                community_units[id(current_community)].append(el)

        # Parse each community + its units
        for card in community_cards:
            units = community_units.get(id(card), [])
            prop = self._parse_community(card, units, area)
            if prop and prop.rooms:
                properties.append(prop)

        return properties

    def _parse_community(self, card, unit_elements,
                         area: Area) -> Optional[StandardProperty]:
        """Parse a community card + its unit cards into a StandardProperty."""
        # Building name
        title_el = card.find("h3", class_="container-search-cards-community-title")
        name = ""
        detail_url = ""
        if title_el:
            link = title_el.find("a")
            if link:
                name = link.get_text(strip=True)
                href = link.get("href", "")
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                elif href.startswith("http"):
                    parsed = urlparse(href)
                    if parsed.netloc in ALLOWED_HOSTS:
                        detail_url = href

        # Address
        address_el = card.find("p", class_="container-search-cards-community-area")
        address = address_el.get_text(strip=True) if address_el else ""

        # Station access
        station_el = card.find("p", class_="container-search-cards-community-line")
        station = station_el.get_text(strip=True) if station_el else ""

        # Parse rooms from unit cards
        rooms = []
        for unit_el in unit_elements:
            room = self._parse_unit(unit_el, detail_url)
            if room:
                rooms.append(room)

        if not name:
            return None

        return StandardProperty(
            name=name,
            address=address,
            access=station,
            building_age="",
            building_age_years=-1,
            area_name=area.name,
            prefecture=area.prefecture,
            rooms=rooms,
        )

    def _parse_unit(self, unit_el, base_url: str) -> Optional[StandardRoom]:
        """Parse a single unit card into a StandardRoom.

        Unit structure:
          dl.container-search-cards-unit-rent: dt "Rent:" dd "¥41,000"
          dl.container-search-cards-unit-size: dt "ROOM SIZE:" dd "33.54m² / 2K"
          dl.container-search-cards-unit-room: dt "Room:" dd "2-407 South (2 Building / 4 Floor)"
        """
        # Rent
        rent_dl = unit_el.find("dl", class_="container-search-cards-unit-rent")
        rent_value = 0
        if rent_dl:
            dd = rent_dl.find("dd")
            if dd:
                rent_text = dd.get_text(strip=True)
                rent_value = parse_digits_as_yen(rent_text)

        if rent_value <= 0:
            return None

        # Size and layout: "33.54m² / 2K"
        size_text = ""
        layout = ""
        size_dl = unit_el.find("dl", class_="container-search-cards-unit-size")
        if size_dl:
            dd = size_dl.find("dd")
            if dd:
                parts = dd.get_text(strip=True).split("/")
                size_text = parts[0].strip()
                if len(parts) > 1:
                    layout = parts[1].strip()

        # Room/floor: "2-407 South (2 Building / 4 Floor)"
        floor_text = ""
        room_dl = unit_el.find("dl", class_="container-search-cards-unit-room")
        if room_dl:
            dd = room_dl.find("dd")
            if dd:
                floor_text = dd.get_text(" ", strip=True)

        # Detail URL from unit link
        detail_url = base_url
        unit_link = unit_el.find(
            "a", class_="container-search-cards-unit-detail")
        if unit_link:
            href = unit_link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                parsed = urlparse(href)
                if parsed.netloc in ALLOWED_HOSTS:
                    detail_url = href

        return StandardRoom(
            floor=floor_text,
            rent=f"¥{rent_value:,}",
            rent_value=rent_value,
            admin_fee="¥0",
            admin_fee_value=0,
            total_value=rent_value,
            deposit="¥0",
            deposit_value=0,
            key_money="¥0",
            key_money_value=0,
            layout=layout,
            size=size_text,
            detail_url=detail_url,
        )

    # ------------------------------------------------------------------
    # Override to search at prefecture level (not city)
    # ------------------------------------------------------------------

    def search_area(self, area: Area, session, max_pages: int = 0):
        """Search at prefecture level. Deduplicates across areas sharing a prefecture."""
        return super().search_area(area, session, max_pages)

    def run(self) -> None:
        """Search unique prefectures, then assign properties to areas by address."""
        parser = build_arg_parser(
            self.SOURCE_NAME, f"Search {self.SOURCE_NAME} rental listings")
        args = parser.parse_args()

        if args.verbose:
            self.logger.setLevel("DEBUG")
            for h in self.logger.handlers:
                h.setLevel("DEBUG")

        max_pages = args.max_pages if args.max_pages is not None else self.MAX_PAGES_PER_AREA
        if args.delay is not None:
            self.REQUEST_DELAY = args.delay
        output_file = args.output or self.OUTPUT_FILE

        all_areas = filter_areas(get_areas_for_source(self.SOURCE_NAME), args.areas)

        # Deduplicate by prefecture (multiple areas share the same VH prefecture)
        seen_prefs = {}
        for area in all_areas:
            key = (area.villagehouse_region, area.villagehouse_prefecture)
            if key not in seen_prefs:
                seen_prefs[key] = area

        self.logger.info("Village House Rental Search")
        self.logger.info("Target areas: %d, unique prefectures: %d",
                         len(all_areas), len(seen_prefs))

        if args.dry_run:
            for area in seen_prefs.values():
                self.logger.info("[DRY RUN] %s", self.build_url(area))
            return

        session = create_session(extra_headers=self.EXTRA_HEADERS)
        all_properties: List[StandardProperty] = []

        for (region, pref), area in seen_prefs.items():
            self.logger.info("Searching %s/%s...", region, pref)
            props = self.search_area(area, session, max_pages)
            if props:
                # Assign properties to the most specific matching area
                for prop in props:
                    prop.area_name = self._match_area_name(prop.address, all_areas) or area.name
                    prop.prefecture = area.prefecture
                room_count = sum(len(p.rooms) for p in props)
                self.logger.info("[%s] %d buildings, %d rooms",
                                 pref, len(props), room_count)
                all_properties.extend(props)
            else:
                self.logger.info("[%s] No listings", pref)

        self.save_results(all_properties, output_file)

    @staticmethod
    def _match_area_name(address: str, areas: List[Area]) -> Optional[str]:
        """Try to match address to a specific area name.

        VH addresses like: "Kanagawa-ken, Hadano-shi, Tokawa 154-3"
        """
        if not address:
            return None
        addr_lower = address.lower()
        for a in areas:
            en_name = a.name.split("(")[0].strip().lower()
            base = en_name.replace("-ku", "").replace("-shi", "").strip()
            if base and base in addr_lower:
                return a.name
        return None


if __name__ == "__main__":
    VillageHouseScraper().run()
