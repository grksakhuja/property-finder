"""Tests for canary_search parsing and address matching."""

import json
import os
from shared.config import Area, AREAS

from canary_search import CanaryScraper, PREFECTURE_UUID

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AREA = Area("Saitama Test", "saitama", canary_prefecture="saitama")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "canary_page.html"), encoding="utf-8") as f:
        return f.read()


class TestCanarySSRParser:
    """Test parsing of SSR __NEXT_DATA__ (fixture-based)."""

    def setup_method(self):
        self.scraper = CanaryScraper()
        html = _load_fixture()
        self.props = self.scraper.parse_page(html, AREA)

    def test_returns_properties(self):
        assert len(self.props) >= 1

    def test_properties_have_rooms(self):
        total_rooms = sum(len(p.rooms) for p in self.props)
        assert total_rooms >= 1

    def test_rent_values_positive(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.rent_value > 0, f"Rent should be positive, got {room.rent_value}"

    def test_name_present(self):
        for prop in self.props:
            assert prop.name, "Property name should not be empty"

    def test_address_present(self):
        for prop in self.props:
            assert prop.address, "Address should not be empty"

    def test_layout_parsed(self):
        all_rooms = [room for p in self.props for room in p.rooms]
        with_layout = sum(1 for r in all_rooms if r.layout)
        assert with_layout / len(all_rooms) >= 0.5, \
            f"At least 50% of rooms should have layout, got {with_layout}/{len(all_rooms)}"

    def test_detail_url_constructed(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.detail_url, "Detail URL should not be empty"
                assert "canary-app.jp/chintai/rooms/" in room.detail_url

    def test_rent_in_valid_range(self):
        for prop in self.props:
            for room in prop.rooms:
                assert 10000 <= room.rent_value <= 500000, \
                    f"Rent {room.rent_value} outside valid range"

    def test_size_parsed(self):
        all_rooms = [room for p in self.props for room in p.rooms]
        with_size = sum(1 for r in all_rooms if r.size and "m²" in r.size)
        assert with_size >= 1, "At least one room should have size in m²"

    def test_building_age_parsed(self):
        for prop in self.props:
            assert prop.building_age_years >= 0, \
                f"Building age should be >= 0, got {prop.building_age_years}"

    def test_deposit_and_key_money_parsed(self):
        all_rooms = [room for p in self.props for room in p.rooms]
        with_deposit = sum(1 for r in all_rooms if r.deposit_value >= 0)
        assert with_deposit == len(all_rooms), "All rooms should have deposit >= 0"

    def test_floor_format(self):
        all_rooms = [room for p in self.props for room in p.rooms]
        with_floor = [r for r in all_rooms if r.floor]
        assert len(with_floor) >= 1
        for room in with_floor:
            assert room.floor.endswith("F"), f"Floor should end with F, got {room.floor}"

    def test_access_string_present(self):
        for prop in self.props:
            assert prop.access, "Access string should not be empty"


class TestCanaryAPIParser:
    """Test parsing of API response format."""

    def setup_method(self):
        self.scraper = CanaryScraper()
        self.api_data = {
            "chintaiEstates": [
                {
                    "id": "estate-001",
                    "name": "テストマンション",
                    "builtAtYear": 2014,
                    "originalAccesses": [
                        {
                            "trainLine": {"id": "line-1", "name": "JR京浜東北線", "trainStations": []},
                            "trainStation": {"id": "st-1", "name": "川口駅", "prefectureId": "pref-1"},
                            "walkDuring": 8,
                            "busStation": {"name": "", "during": 0},
                        }
                    ],
                }
            ],
            "chintaiRooms": [
                {
                    "id": "room-001",
                    "chintaiEstateId": "estate-001",
                    "rent": 85000,
                    "adminFee": 5000,
                    "securityDeposit": 85000,
                    "keyMoney": 85000,
                    "layout": {"id": "layout-1", "name": "1LDK"},
                    "square": 42.5,
                    "floor": 3,
                    "addressStr": "埼玉県川口市西川口3丁目",
                    "accesses": [
                        {
                            "trainLine": {"id": "line-1", "name": "JR京浜東北線", "trainStations": []},
                            "trainStation": {"id": "st-1", "name": "川口駅", "prefectureId": "pref-1"},
                            "walkDuring": 8,
                            "busStation": {"name": "", "during": 0},
                        }
                    ],
                }
            ],
        }

    def test_parses_estates_and_rooms(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert len(props) == 1
        assert len(props[0].rooms) == 1

    def test_rent_parsed(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert props[0].rooms[0].rent_value == 85000

    def test_layout_parsed(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert props[0].rooms[0].layout == "1LDK"

    def test_size_parsed(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert props[0].rooms[0].size == "42.5m²"

    def test_address_from_room(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert "川口市" in props[0].address

    def test_access_string(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert "JR京浜東北線" in props[0].access
        assert "川口駅" in props[0].access
        assert "徒歩8分" in props[0].access

    def test_building_age_from_year(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        # Built in 2014, current year minus 2014
        assert props[0].building_age_years > 0

    def test_detail_url(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        assert "canary-app.jp/chintai/rooms/room-001/" in props[0].rooms[0].detail_url

    def test_deposit_and_key_money(self):
        props = self.scraper._parse_api_response(self.api_data, AREA)
        room = props[0].rooms[0]
        assert room.deposit_value == 85000
        assert room.key_money_value == 85000


class TestCanaryAddressMatching:
    """Test Japanese address matching to target areas."""

    def setup_method(self):
        self.entries = CanaryScraper._build_area_entries(AREAS)

    def test_kawaguchi_matches(self):
        match = CanaryScraper._match_area(
            "埼玉県川口市西川口3丁目5番12号", self.entries)
        assert match is not None
        assert "Kawaguchi" in match.name

    def test_yokohama_tsurumi_matches(self):
        match = CanaryScraper._match_area(
            "神奈川県横浜市鶴見区東寺尾2丁目4番23号", self.entries)
        assert match is not None
        assert "Tsurumi" in match.name

    def test_tokorozawa_no_match(self):
        """Tokorozawa is not in our target areas."""
        match = CanaryScraper._match_area(
            "埼玉県所沢市東町1丁目2番3号", self.entries)
        assert match is None

    def test_empty_address_no_match(self):
        match = CanaryScraper._match_area("", self.entries)
        assert match is None

    def test_kita_ku_tokyo_matches(self):
        """北区 with 東京都 should match Tokyo Kita-ku."""
        match = CanaryScraper._match_area(
            "東京都北区赤羽1丁目2番3号", self.entries)
        assert match is not None
        assert "Kita" in match.name
        assert match.prefecture == "tokyo"

    def test_minami_ku_kanagawa_matches(self):
        """南区 with 神奈川県 should match Yokohama Minami-ku, not Saitama."""
        match = CanaryScraper._match_area(
            "神奈川県横浜市南区中里1丁目", self.entries)
        assert match is not None
        assert match.prefecture == "kanagawa"


class TestCanaryBuildUrl:
    def setup_method(self):
        self.scraper = CanaryScraper()

    def test_url_has_prefecture(self):
        area = Area("Test", "kanagawa", canary_prefecture="kanagawa")
        url = self.scraper.build_url(area)
        assert "kanagawa" in url

    def test_url_has_api_endpoint(self):
        area = Area("Test", "saitama", canary_prefecture="saitama")
        url = self.scraper.build_url(area)
        assert "chintaiRooms:search" in url


class TestCanaryPrefectureUUIDs:
    def test_all_target_prefectures_have_uuids(self):
        for pref in ["saitama", "chiba", "kanagawa", "tokyo"]:
            assert pref in PREFECTURE_UUID
            assert len(PREFECTURE_UUID[pref]) == 36  # UUID format


class TestCanaryEmptyPage:
    def test_no_next_data_returns_empty(self):
        scraper = CanaryScraper()
        result = scraper.parse_page("<html><body></body></html>", AREA)
        assert result == []

    def test_empty_estates_returns_empty(self):
        scraper = CanaryScraper()
        html = '''<html><body>
        <script id="__NEXT_DATA__" type="application/json">
        {"props": {"pageProps": {"newEstatesResponse": {"estatesList": []}}}}
        </script></body></html>'''
        result = scraper.parse_page(html, AREA)
        assert result == []
