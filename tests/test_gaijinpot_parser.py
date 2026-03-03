"""Tests for gaijinpot_search.parse_page and address matching."""

import os
from shared.config import Area, AREAS

from gaijinpot_search import GaijinPotScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
AREA = Area("Nationwide", "all")

scraper = GaijinPotScraper()


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "gaijinpot_page.html"), encoding="utf-8") as f:
        return f.read()


class TestGaijinPotParser:
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
                assert "m²" in room.size or "m2" in room.size.lower(), \
                    f"Size should contain m², got: {room.size}"

    def test_detail_url_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.detail_url, "Detail URL should not be empty"
                assert room.detail_url.startswith("https://"), \
                    f"URL should start with https://, got: {room.detail_url}"

    def test_station_access_parsed(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        with_station = sum(1 for p in props if p.access)
        assert with_station / len(props) >= 0.3, \
            f"At least 30% of properties should have station access, got {with_station}/{len(props)}"

    def test_address_present(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        for prop in props:
            assert prop.address, "Address should not be empty"

    def test_building_age_parsed(self):
        html = _load_fixture()
        props = scraper.parse_page(html, AREA)
        with_age = sum(1 for p in props if p.building_age_years >= 0)
        assert with_age / len(props) >= 0.3, \
            f"At least 30% of properties should have building age, got {with_age}/{len(props)}"


class TestGaijinPotAddressMatching:
    """Test English address matching to target areas."""

    def setup_method(self):
        self.entries = GaijinPotScraper._build_area_match_entries(AREAS)

    def test_kawaguchi_matches(self):
        match = GaijinPotScraper._match_area(
            "in Kawaguchi Kawaguchi-shi, Saitama", self.entries)
        assert match is not None
        assert "Kawaguchi" in match.name

    def test_kita_ku_matches(self):
        match = GaijinPotScraper._match_area(
            "in Kita-ku, Tokyo", self.entries)
        assert match is not None
        assert "Kita-ku" in match.name

    def test_nakahara_ku_matches(self):
        match = GaijinPotScraper._match_area(
            "in Nakahara-ku Kawasaki-shi, Kanagawa", self.entries)
        assert match is not None
        assert "Nakahara" in match.name

    def test_ichikawa_matches(self):
        match = GaijinPotScraper._match_area(
            "in Ichikawa-shi, Chiba", self.entries)
        assert match is not None
        assert "Ichikawa" in match.name

    def test_osaka_no_match(self):
        match = GaijinPotScraper._match_area(
            "in Shoji Osaka-shi Ikuno-ku, Osaka", self.entries)
        assert match is None

    def test_empty_address_no_match(self):
        match = GaijinPotScraper._match_area("", self.entries)
        assert match is None

    def test_none_address_no_match(self):
        match = GaijinPotScraper._match_area(None, self.entries)
        assert match is None
