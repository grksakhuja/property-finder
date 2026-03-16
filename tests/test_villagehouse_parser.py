"""Tests for villagehouse_search.parse_page."""

import os
from shared.config import Area, AREAS
from shared.parsers import parse_digits_as_yen

from villagehouse_search import VillageHouseScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AREA = Area("Kanagawa Test", "kanagawa",
            villagehouse_region="kanto", villagehouse_prefecture="kanagawa")

def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "villagehouse_page.html"), encoding="utf-8") as f:
        return f.read()


class TestVillageHouseParser:
    def setup_method(self):
        self.scraper = VillageHouseScraper()
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

    def test_building_name_present(self):
        for prop in self.props:
            assert prop.name, "Property name should not be empty"
            assert "Village House" in prop.name

    def test_address_present(self):
        for prop in self.props:
            assert prop.address, "Address should not be empty"

    def test_station_access_present(self):
        with_station = sum(1 for p in self.props if p.access)
        assert with_station / len(self.props) >= 0.5, \
            f"At least 50% of properties should have station access, got {with_station}/{len(self.props)}"

    def test_layout_parsed(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.layout, f"Layout should not be empty for {prop.name}"

    def test_size_parsed(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.size, f"Size should not be empty for {prop.name}"
                assert "m²" in room.size, f"Size should contain m², got: {room.size}"

    def test_zero_deposit_and_key_money(self):
        """Village House always has zero deposit and key money."""
        for prop in self.props:
            for room in prop.rooms:
                assert room.deposit_value == 0, "Deposit should be 0"
                assert room.key_money_value == 0, "Key money should be 0"

    def test_detail_url_present(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.detail_url, "Detail URL should not be empty"
                assert "villagehouse.jp" in room.detail_url

    def test_rent_in_budget_range(self):
        """Village House rents are typically ¥30,000–¥150,000."""
        for prop in self.props:
            for room in prop.rooms:
                assert 25000 <= room.rent_value <= 150000, \
                    f"Rent {room.rent_value} outside Village House range (¥25K-¥150K)"

    def test_floor_info_parsed(self):
        has_floor = any(room.floor for p in self.props for room in p.rooms)
        assert has_floor, "At least one room should have floor info"


class TestVillageHousePriceParser:
    def test_yen_with_symbol(self):
        assert parse_digits_as_yen("¥79,000") == 79000

    def test_plain_number(self):
        assert parse_digits_as_yen("41000") == 41000

    def test_empty_returns_zero(self):
        assert parse_digits_as_yen("") == 0


class TestVillageHouseAreaMatching:
    def test_kawasaki_address_matches(self):
        areas = [a for a in AREAS if a.villagehouse_city]
        result = VillageHouseScraper._match_area_name(
            "Kanagawa-ken, Kawasaki-shi, Takatsu-ku", areas)
        assert result is not None
        assert "Kawasaki" in result or "Takatsu" in result

    def test_yokohama_address_matches(self):
        areas = [a for a in AREAS if a.villagehouse_city]
        result = VillageHouseScraper._match_area_name(
            "Kanagawa-ken, Yokohama-shi, Kohoku-ku", areas)
        assert result is not None

    def test_empty_address_returns_none(self):
        areas = [a for a in AREAS if a.villagehouse_city]
        result = VillageHouseScraper._match_area_name("", areas)
        assert result is None


class TestVillageHouseBuildUrl:
    def setup_method(self):
        self.scraper = VillageHouseScraper()

    def test_first_page_no_page_param(self):
        url = self.scraper.build_url(AREA, page=1)
        assert "page=" not in url
        assert "/kanto/kanagawa/" in url

    def test_second_page_has_page_param(self):
        url = self.scraper.build_url(AREA, page=2)
        assert "page=2" in url
