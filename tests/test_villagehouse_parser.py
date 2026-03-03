"""Tests for villagehouse_search.parse_page."""

import os
from shared.config import Area, AREAS

from villagehouse_search import VillageHouseScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AREA = Area("Kanagawa Test", "kanagawa",
            villagehouse_region="kanto", villagehouse_prefecture="kanagawa")

scraper = VillageHouseScraper()


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "villagehouse_page.html"), encoding="utf-8") as f:
        return f.read()


class TestVillageHouseParser:
    def test_returns_properties(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        assert len(props) >= 1

    def test_properties_have_rooms(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        total_rooms = sum(len(p.rooms) for p in props)
        assert total_rooms >= 1

    def test_rent_values_positive(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.rent_value > 0, f"Rent should be positive, got {room.rent_value}"

    def test_building_name_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            assert prop.name, "Property name should not be empty"
            assert "Village House" in prop.name

    def test_address_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            assert prop.address, "Address should not be empty"

    def test_station_access_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        with_station = sum(1 for p in props if p.access)
        assert with_station / len(props) >= 0.5, \
            f"At least 50% of properties should have station access, got {with_station}/{len(props)}"

    def test_layout_parsed(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.layout, f"Layout should not be empty for {prop.name}"

    def test_size_parsed(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.size, f"Size should not be empty for {prop.name}"
                assert "m²" in room.size, f"Size should contain m², got: {room.size}"

    def test_zero_deposit_and_key_money(self):
        """Village House always has zero deposit and key money."""
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.deposit_value == 0, "Deposit should be 0"
                assert room.key_money_value == 0, "Key money should be 0"

    def test_detail_url_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.detail_url, "Detail URL should not be empty"
                assert "villagehouse.jp" in room.detail_url

    def test_rent_in_budget_range(self):
        """Village House rents are typically ¥30,000–¥150,000."""
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert 25000 <= room.rent_value <= 150000, \
                    f"Rent {room.rent_value} outside Village House range (¥25K-¥150K)"

    def test_floor_info_parsed(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        has_floor = any(room.floor for p in props for room in p.rooms)
        assert has_floor, "At least one room should have floor info"


class TestVillageHousePriceParser:
    def test_yen_with_symbol(self):
        assert VillageHouseScraper._parse_price("¥79,000") == 79000

    def test_plain_number(self):
        assert VillageHouseScraper._parse_price("41000") == 41000

    def test_empty_returns_zero(self):
        assert VillageHouseScraper._parse_price("") == 0


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
