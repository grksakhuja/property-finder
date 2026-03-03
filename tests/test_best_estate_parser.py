"""Tests for best_estate_search.parse_page using fixture HTML."""

import os
from shared.config import Area

from best_estate_search import BestEstateScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# A dummy area for parse_page
AREA = Area("Kita-ku (北区)", "tokyo", best_estate_prefecture="tokyo")

# Disable room type filter for fixture testing — the fixture contains
# whatever room types the site returned (1K, 1LDK, etc.) since the site
# ignores the room_type URL parameter.
scraper = BestEstateScraper()
scraper.ROOM_TYPE_FILTER = []


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "best_estate_page.html"), encoding="utf-8") as f:
        return f.read()


class TestBestEstateParser:
    def setup_method(self):
        html = _load_fixture()
        self.props = scraper.parse_page(html, AREA)

    def test_returns_properties(self):
        assert len(self.props) >= 1

    def test_properties_have_rooms(self):
        total_rooms = sum(len(p.rooms) for p in self.props)
        assert total_rooms >= 1

    def test_rent_values_positive(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.rent_value > 0, f"Rent should be positive, got {room.rent_value}"

    def test_building_names_present(self):
        for prop in self.props:
            assert prop.name, "Property name should not be empty"

    def test_address_present(self):
        # Streamed listings may lack address; check non-streamed ones
        named_props = [p for p in self.props if not p.name.startswith("(")]
        assert len(named_props) >= 1
        for prop in named_props:
            assert prop.address, "Address should not be empty"

    def test_building_age_parsed(self):
        for prop in self.props:
            # building_age_years should be a non-negative int or -1 (unknown)
            assert isinstance(prop.building_age_years, int)
            assert prop.building_age_years >= -1

    def test_detail_urls_absolute(self):
        for prop in self.props:
            for room in prop.rooms:
                if room.detail_url:
                    assert room.detail_url.startswith("https://www.best-estate.jp/"), \
                        f"URL should be absolute, got {room.detail_url}"

    def test_layout_present(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.layout, "Layout should not be empty"

    def test_size_present(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.size, "Size should not be empty"
