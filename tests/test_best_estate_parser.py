"""Tests for best_estate_search.parse_page using fixture HTML."""

import os
from shared.config import Area, AREAS

from best_estate_search import BestEstateScraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# A dummy area for parse_page
AREA = Area("Kita-ku (北区)", "tokyo", best_estate_prefecture="tokyo")

def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "best_estate_page.html"), encoding="utf-8") as f:
        return f.read()


class TestBestEstateParser:
    def setup_method(self):
        self.scraper = BestEstateScraper()
        self.scraper.ROOM_TYPE_FILTER = []
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


class TestBestEstateBuildUrl:
    def setup_method(self):
        self.scraper = BestEstateScraper()

    def test_first_page_no_current_page(self):
        url = self.scraper.build_url(page=1)
        assert "current_page" not in url

    def test_second_page_has_current_page(self):
        url = self.scraper.build_url(page=2)
        assert "current_page=2" in url

    def test_url_has_layouts(self):
        url = self.scraper.build_url(page=1)
        assert "layouts=" in url

    def test_url_has_price_range(self):
        url = self.scraper.build_url(page=1)
        assert "min_price=60000" in url
        assert "max_price=200000" in url


class TestBestEstateAreaMatching:
    def setup_method(self):
        self.scraper = BestEstateScraper()
        target_areas = [a for a in AREAS if a.best_estate_prefecture]
        self.entries = self.scraper._build_area_jp_map(target_areas)

    def test_kawaguchi_matches(self):
        match = self.scraper._match_area(
            "埼玉県川口市西川口5丁目", self.entries)
        assert match is not None
        assert "Kawaguchi" in match.name

    def test_kita_ku_tokyo_matches(self):
        match = self.scraper._match_area(
            "東京都北区赤羽1丁目", self.entries)
        assert match is not None
        assert "Kita-ku" in match.name

    def test_wrong_prefecture_no_match(self):
        """南区 exists in both Yokohama and Saitama; check prefecture."""
        match = self.scraper._match_area(
            "広島県広島市南区", self.entries)
        assert match is None

    def test_empty_address_no_match(self):
        match = self.scraper._match_area("", self.entries)
        assert match is None

    def test_no_match(self):
        match = self.scraper._match_area(
            "大阪府大阪市北区", self.entries)
        assert match is None

    def test_build_area_jp_map_extracts_jp_names(self):
        """Verify entries contain valid Japanese names."""
        assert len(self.entries) >= 1
        for jp_name, pref_jp, area in self.entries:
            assert jp_name, f"jp_name should not be empty for {area.name}"
            assert pref_jp, f"pref_jp should not be empty for {area.name}"
