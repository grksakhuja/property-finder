"""Tests for wagaya_search.parse_page and address matching."""

import os
from shared.config import Area, AREAS

from wagaya_search import WagayaScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AREA = Area("Saitama Test", "saitama", wagaya_prefecture="saitama")

scraper = WagayaScraper()


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "wagaya_page.html"), encoding="utf-8") as f:
        return f.read()


class TestWagayaParser:
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
                assert "wagaya-japan.com" in room.detail_url

    def test_rent_in_valid_range(self):
        """Wagaya listings should have reasonable rent values."""
        for prop in self.props:
            for room in prop.rooms:
                assert 10000 <= room.rent_value <= 500000, \
                    f"Rent {room.rent_value} outside valid range"


class TestWagayaAddressMatching:
    """Test English address matching to target areas."""

    def setup_method(self):
        self.entries = WagayaScraper._build_area_entries(AREAS)

    def test_kawaguchi_city_matches(self):
        match = WagayaScraper._match_area(
            "Nishikawaguchi 5-chome, Kawaguchi City, Saitama Prefecture",
            self.entries)
        assert match is not None
        assert "Kawaguchi" in match.name

    def test_niiza_city_matches(self):
        match = WagayaScraper._match_area(
            "Niiza City, Saitama Prefecture\rSome address",
            self.entries)
        assert match is not None
        assert "Niiza" in match.name

    def test_kita_ward_matches(self):
        match = WagayaScraper._match_area(
            "Kita Ward, Tokyo", self.entries)
        assert match is not None
        assert "Kita" in match.name

    def test_ichikawa_matches(self):
        match = WagayaScraper._match_area(
            "Ichikawa City, Chiba Prefecture",
            self.entries)
        assert match is not None
        assert "Ichikawa" in match.name

    def test_tokorozawa_no_match(self):
        """Tokorozawa is not in our target areas."""
        match = WagayaScraper._match_area(
            "Tokorozawa City, Saitama Prefecture",
            self.entries)
        assert match is None

    def test_empty_address_no_match(self):
        match = WagayaScraper._match_area("", self.entries)
        assert match is None


class TestWagayaPriceParser:
    def test_yen_with_symbol(self):
        assert scraper._parse_wagaya_price("￥50,000") == 50000

    def test_plain_number(self):
        assert scraper._parse_wagaya_price("50000") == 50000

    def test_dash_returns_zero(self):
        assert scraper._parse_wagaya_price("-") == 0

    def test_empty_returns_zero(self):
        assert scraper._parse_wagaya_price("") == 0

    def test_zero_returns_zero(self):
        assert scraper._parse_wagaya_price("0") == 0
