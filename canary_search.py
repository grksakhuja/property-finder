#!/usr/bin/env python3
"""
Canary Rental Search Tool

Searches web.canary-app.jp for rental property listings via their REST API.
Uses Firebase anonymous auth for a bearer token, then queries the
/v1/chintaiRooms:search endpoint with prefecture-level filtering and
offset-based pagination.

Canary searches by prefecture, so we search each prefecture with pagination
and match to specific areas by Japanese address.
"""

import json
import time
from datetime import datetime
from typing import List, Optional

import requests

from shared.config import AREAS, Area, get_target_room_types
from shared.cli import build_arg_parser, filter_areas
from shared.http_client import create_session
from shared.scraper_template import BaseScraper, StandardProperty, StandardRoom

BASE_URL = "https://web.canary-app.jp"
API_URL = "https://api.user.canary-app.com"
FIREBASE_API_KEY = "AIzaSyAj7f1dOCFbeplBxRhaxUrwSdxxmjVOTuo"

# Japanese prefecture names for address matching
PREFECTURE_JP = {
    "saitama": "埼玉県",
    "chiba": "千葉県",
    "kanagawa": "神奈川県",
    "tokyo": "東京都",
}

# Canary uses UUIDs for prefecture identifiers
PREFECTURE_UUID = {
    "saitama": "d1298901-dfc5-4812-a303-534de562679e",
    "chiba": "d5758809-3ada-4c5e-a2b8-e8260a052eee",
    "kanagawa": "2bbacfaa-febf-491b-99cb-18c95c9684ef",
    "tokyo": "5eeb60d1-3e54-4ce1-82f9-df6848481fdf",
}

PAGE_SIZE = 20  # API returns 20 estates per request


def _get_firebase_token() -> str:
    """Get an anonymous Firebase auth token for API access."""
    url = (f"https://identitytoolkit.googleapis.com/v1/"
           f"accounts:signUp?key={FIREBASE_API_KEY}")
    resp = requests.post(url, json={"returnSecureToken": True}, timeout=15)
    resp.raise_for_status()
    return resp.json()["idToken"]


class CanaryScraper(BaseScraper):
    SOURCE_NAME = "canary"
    BASE_URL = BASE_URL
    OUTPUT_FILE = "results_canary.json"
    REQUEST_DELAY = 1.0
    MAX_PAGES_PER_AREA = 100  # 100 pages × 20 estates = 2000 estates max
    ITEMS_PER_PAGE = PAGE_SIZE
    DEFAULT_WORKERS = 1
    ROOM_TYPE_FILTER = []

    def __init__(self):
        super().__init__()
        self._target_room_types = get_target_room_types()

    def build_url(self, area: Area, page: int = 1) -> str:
        """Construct Canary search URL (for dry-run display only)."""
        pref = area.canary_prefecture or "tokyo"
        return f"{API_URL}/v1/chintaiRooms:search [prefecture={pref}]"

    def parse_page(self, html: str, area: Area) -> List[StandardProperty]:
        """Parse SSR __NEXT_DATA__ (kept for test compatibility)."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            return []
        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError:
            return []

        page_props = data.get("props", {}).get("pageProps", {})
        estates_response = page_props.get("newEstatesResponse", {})
        estates_list = estates_response.get("estatesList", [])
        if not estates_list:
            return []

        properties = []
        for estate in estates_list:
            prop = self._parse_ssr_estate(estate, area)
            if prop and prop.rooms:
                properties.append(prop)
        return properties

    # ------------------------------------------------------------------
    # API response parsing
    # ------------------------------------------------------------------

    def _parse_api_response(self, data: dict,
                            area: Area) -> List[StandardProperty]:
        """Parse API response into StandardProperty objects.

        API response has separate chintaiEstates and chintaiRooms arrays
        linked by chintaiEstateId.
        """
        estates = {e["id"]: e for e in data.get("chintaiEstates", [])}
        rooms_by_estate: dict = {}
        for room in data.get("chintaiRooms", []):
            eid = room.get("chintaiEstateId", "")
            rooms_by_estate.setdefault(eid, []).append(room)

        properties = []
        for estate_id, estate in estates.items():
            api_rooms = rooms_by_estate.get(estate_id, [])
            if not api_rooms:
                continue

            prop = self._parse_api_estate(estate, api_rooms, area)
            if prop and prop.rooms:
                properties.append(prop)

        return properties

    def _parse_api_estate(self, estate: dict, api_rooms: list,
                          area: Area) -> Optional[StandardProperty]:
        """Parse a single estate from the API response."""
        building_name = estate.get("name", "")

        # Building age from construction year
        built_year = estate.get("builtAtYear")
        if built_year and built_year > 0:
            building_age_years = datetime.now().year - built_year
            building_age = f"築{building_age_years}年"
        else:
            building_age_years = -1
            building_age = ""

        # Build access from estate's originalAccesses
        access = self._build_access_from_api(
            estate.get("originalAccesses", []))

        rooms = []
        address = ""
        for room_data in api_rooms:
            # Get address from room (addressStr field)
            if not address:
                address = room_data.get("addressStr", "")

            room = self._parse_api_room(room_data)
            if room:
                rooms.append(room)

            # Also use room-level access if estate has none
            if not access:
                access = self._build_access_from_api(
                    room_data.get("accesses", []))

        if not rooms:
            return None

        return StandardProperty(
            name=building_name,
            address=address,
            access=access,
            building_age=building_age,
            building_age_years=building_age_years,
            area_name=area.name,
            prefecture=area.prefecture,
            rooms=rooms,
        )

    def _parse_api_room(self, room: dict) -> Optional[StandardRoom]:
        """Parse a single room from the API response."""
        # Layout is an object {id, name} in API response
        layout_obj = room.get("layout", {})
        layout = layout_obj.get("name", "") if isinstance(layout_obj, dict) else str(layout_obj)

        # Filter by target room types
        if self._target_room_types and layout not in self._target_room_types:
            return None

        rent_value = room.get("rent", 0) or 0
        if rent_value <= 0:
            return None

        admin_fee_value = room.get("adminFee", 0) or 0
        total_value = rent_value + admin_fee_value
        deposit_value = room.get("securityDeposit", 0) or 0
        key_money_value = room.get("keyMoney", 0) or 0

        # Size
        square = room.get("square", 0) or 0
        size = f"{square}m²" if square else ""

        # Floor
        floor_num = room.get("floor", 0) or 0
        floor = f"{floor_num}F" if floor_num else ""

        # Access from room-level data
        access = self._build_access_from_api(room.get("accesses", []))

        # Detail URL
        room_id = room.get("id", "")
        detail_url = f"{BASE_URL}/chintai/room/{room_id}" if room_id else ""

        return StandardRoom(
            floor=floor,
            rent=f"¥{rent_value:,}",
            rent_value=rent_value,
            admin_fee=f"¥{admin_fee_value:,}" if admin_fee_value else "",
            admin_fee_value=admin_fee_value,
            total_value=total_value,
            deposit=f"¥{deposit_value:,}" if deposit_value else "",
            deposit_value=deposit_value,
            key_money=f"¥{key_money_value:,}" if key_money_value else "",
            key_money_value=key_money_value,
            layout=layout,
            size=size,
            size_display=size,
            detail_url=detail_url,
        )

    @staticmethod
    def _build_access_from_api(accesses: list) -> str:
        """Build access string from API-format accesses.

        API format: [{trainLine: {name}, trainStation: {name}, walkDuring: N}]
        """
        if not accesses:
            return ""
        parts = []
        for acc in accesses:
            line = acc.get("trainLine", {})
            station = acc.get("trainStation", {})
            line_name = line.get("name", "") if isinstance(line, dict) else ""
            station_name = station.get("name", "") if isinstance(station, dict) else ""
            walk = acc.get("walkDuring", 0)

            if line_name and station_name and walk:
                parts.append(f"{line_name} {station_name} 徒歩{walk}分")
            elif station_name and walk:
                parts.append(f"{station_name} 徒歩{walk}分")
            elif station_name:
                parts.append(station_name)
        return " / ".join(parts)

    # ------------------------------------------------------------------
    # SSR parsing (kept for test fixture compatibility)
    # ------------------------------------------------------------------

    def _parse_ssr_estate(self, estate: dict,
                         area: Area) -> Optional[StandardProperty]:
        """Parse a single estate from SSR __NEXT_DATA__."""
        building_name = estate.get("name", "")
        building_age_years = estate.get("old", -1)
        if building_age_years is None:
            building_age_years = -1
        building_age = f"築{building_age_years}年" if building_age_years >= 0 else ""

        access = self._build_access_string(estate.get("accessesList", []))
        rooms_list = estate.get("roomsList", [])
        if not rooms_list:
            return None

        rooms = []
        for room_data in rooms_list:
            room = self._parse_ssr_room(room_data)
            if room:
                rooms.append(room)
        if not rooms:
            return None

        address = rooms_list[0].get("address", "") if rooms_list else ""

        return StandardProperty(
            name=building_name, address=address, access=access,
            building_age=building_age, building_age_years=building_age_years,
            area_name=area.name, prefecture=area.prefecture, rooms=rooms,
        )

    def _parse_ssr_room(self, room: dict) -> Optional[StandardRoom]:
        """Parse a single room from SSR data."""
        if not room.get("isListed", True):
            return None
        layout = room.get("layout", "")
        if self._target_room_types and layout not in self._target_room_types:
            return None

        rent_value = room.get("rent", 0) or 0
        if rent_value <= 0:
            return None

        admin_fee_value = room.get("adminFee", 0) or 0
        deposit_value = room.get("securityDeposit", 0) or 0
        key_money_value = room.get("keyMoney", 0) or 0
        square = room.get("square", 0) or 0
        floor_num = room.get("floor", 0) or 0
        room_id = room.get("id", "")

        return StandardRoom(
            floor=f"{floor_num}F" if floor_num else "",
            rent=f"¥{rent_value:,}", rent_value=rent_value,
            admin_fee=f"¥{admin_fee_value:,}" if admin_fee_value else "",
            admin_fee_value=admin_fee_value,
            total_value=rent_value + admin_fee_value,
            deposit=f"¥{deposit_value:,}" if deposit_value else "",
            deposit_value=deposit_value,
            key_money=f"¥{key_money_value:,}" if key_money_value else "",
            key_money_value=key_money_value,
            layout=layout,
            size=f"{square}m²" if square else "",
            size_display=f"{square}m²" if square else "",
            detail_url=f"{BASE_URL}/chintai/room/{room_id}" if room_id else "",
        )

    @staticmethod
    def _build_access_string(accesses: list) -> str:
        """Build access string from SSR accessesList."""
        if not accesses:
            return ""
        parts = []
        for acc in accesses:
            station = acc.get("station", "")
            during = acc.get("during", "")
            if station and during:
                parts.append(f"{station} 徒歩{during}分")
            elif station:
                parts.append(station)
        return " / ".join(parts)

    # ------------------------------------------------------------------
    # Address matching
    # ------------------------------------------------------------------

    @staticmethod
    def _build_area_entries(areas: List[Area]) -> List[tuple]:
        """Build (jp_name, prefecture_jp, Area) tuples for address matching."""
        entries = []
        for a in areas:
            pref_jp = PREFECTURE_JP.get(a.prefecture, "")
            entries.append((a.jp_name, pref_jp, a))
        return entries

    @staticmethod
    def _match_area(address: str,
                    area_entries: List[tuple]) -> Optional[Area]:
        """Match Japanese property address to a target area."""
        if not address:
            return None
        for jp_name, pref_jp, a in area_entries:
            if not jp_name:
                continue
            if jp_name in address:
                if pref_jp and pref_jp in address:
                    return a
                if not pref_jp or "区" not in jp_name:
                    return a
        return None

    # ------------------------------------------------------------------
    # API search request
    # ------------------------------------------------------------------

    def _build_search_body(self, prefecture_uuid: str,
                           offset: str = "") -> dict:
        """Build the search API request body."""
        return {
            "prefectureIds": [prefecture_uuid],
            "cityIds": [],
            "chomeiIds": [],
            "stationIds": [],
            "rentMin": {"value": 0, "hasValue": False},
            "rentMax": {"value": 0, "hasValue": False},
            "includeAdminFee": False,
            "squareMin": {"value": 0, "hasValue": False},
            "squareMax": {"value": 0, "hasValue": False},
            "oldMax": {"value": 0, "hasValue": False},
            "duringMax": {"value": 0, "hasValue": False},
            "searchOptionIds": [],
            "keywords": [],
            "layoutNames": list(self._target_room_types),
            "isNewArrival": False,
            "commutes": [],
            "sortType": 0,
            "listType": 2,
            "limit": PAGE_SIZE,
            "offset": {"value": offset, "hasValue": bool(offset)},
            "searchSessionId": "",
            "chintaiEstateIds": [],
            "shatakuCode": {"value": "", "hasValue": False},
        }

    # ------------------------------------------------------------------
    # Override run() for API-based search
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Search via Canary API by prefecture with pagination."""
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

        # Get all target areas for address matching
        target_areas = filter_areas(AREAS, args.areas)
        area_entries = self._build_area_entries(target_areas)

        # Determine which prefectures to search (deduplicate)
        prefs_to_search = {}
        for a in target_areas:
            if a.canary_prefecture and a.canary_prefecture not in prefs_to_search:
                prefs_to_search[a.canary_prefecture] = a

        self.logger.info("Canary Rental Search")
        self.logger.info("Target areas: %d", len(target_areas))
        self.logger.info("Searching %d prefectures (max %d pages each): %s",
                         len(prefs_to_search), max_pages,
                         ", ".join(prefs_to_search.keys()))

        if args.dry_run:
            for pref in prefs_to_search:
                uuid = PREFECTURE_UUID.get(pref, "?")
                self.logger.info("[DRY RUN] POST %s/v1/chintaiRooms:search "
                                 "[%s=%s]", API_URL, pref, uuid)
            return

        # Authenticate via Firebase anonymous sign-in
        self.logger.info("Authenticating...")
        try:
            token = _get_firebase_token()
        except Exception as e:
            self.logger.error("Firebase auth failed: %s", e)
            return

        session = create_session()
        session.headers["Authorization"] = f"Bearer {token}"
        session.headers["Content-Type"] = "application/json"

        all_properties: List[StandardProperty] = []
        unmatched_count = 0

        for pref_name in prefs_to_search:
            pref_uuid = PREFECTURE_UUID.get(pref_name)
            if not pref_uuid:
                self.logger.warning("No UUID for prefecture %s", pref_name)
                continue

            self.logger.info("Searching prefecture: %s", pref_name)
            dummy_area = Area(f"Canary-{pref_name}", pref_name,
                              canary_prefecture=pref_name)

            pref_properties: List[StandardProperty] = []
            offset = ""
            total_count = None

            for page_num in range(1, max_pages + 1):
                body = self._build_search_body(pref_uuid, offset)

                try:
                    if page_num > 1:
                        time.sleep(self.REQUEST_DELAY)
                    resp = session.post(
                        f"{API_URL}/v1/chintaiRooms:search",
                        json=body, timeout=30)
                    resp.raise_for_status()
                except Exception as e:
                    self.logger.error("  API request failed page %d: %s",
                                      page_num, e)
                    break

                data = resp.json()

                # Get total count on first page
                if total_count is None:
                    tc = data.get("totalCount", {})
                    total_count = tc.get("value", 0) if isinstance(tc, dict) else 0
                    self.logger.info("  Total listings: %s", total_count)

                properties = self._parse_api_response(data, dummy_area)

                if not properties:
                    if page_num == 1:
                        self.logger.info("  No listings found")
                    break

                pref_properties.extend(properties)
                room_count = sum(len(p.rooms) for p in properties)
                self.logger.debug("  Page %d: %d buildings, %d rooms",
                                  page_num, len(properties), room_count)

                # Check pagination — API may not return nextOffset on
                # the first page, so fall back to manual offset calculation
                next_offset = data.get("nextOffset", {})
                if isinstance(next_offset, dict) and next_offset.get("hasValue"):
                    offset = next_offset["value"]
                else:
                    # Manual offset: page_num * PAGE_SIZE
                    offset = str(page_num * PAGE_SIZE)

                # Stop if we got fewer than a full page of estates
                if len(data.get("chintaiEstates", [])) < PAGE_SIZE:
                    break

            if not pref_properties:
                continue

            self.logger.info("  Found %d buildings across %d pages",
                             len(pref_properties), page_num)

            # Match each property to target areas by address
            matched_count = 0
            for prop in pref_properties:
                matched = self._match_area(prop.address, area_entries)
                if matched:
                    prop.area_name = matched.name
                    prop.prefecture = matched.prefecture
                    all_properties.append(prop)
                    matched_count += 1
                else:
                    unmatched_count += 1

            self.logger.info("  %d matched to target areas, %d discarded",
                             matched_count,
                             len(pref_properties) - matched_count)

        total_rooms = sum(len(p.rooms) for p in all_properties)
        self.logger.info(
            "Done: %d properties with %d rooms in target areas "
            "(%d outside target areas discarded)",
            len(all_properties), total_rooms, unmatched_count)

        self.save_results(all_properties, output_file)


if __name__ == "__main__":
    CanaryScraper().run()
