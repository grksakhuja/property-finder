"""Tests for best_estate_search.parse_page using fixture HTML."""

import re
import os
from bs4 import BeautifulSoup
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
        assert len(self.props) == 7, (
            f"Expected 7 properties (4 inline + 3 template-only), got {len(self.props)}")

    def test_properties_have_rooms(self):
        total_rooms = sum(len(p.rooms) for p in self.props)
        assert total_rooms == 20, (
            f"Expected 20 rooms total, got {total_rooms}")

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


class TestBestEstateTemplateResolution:
    """Tests for _build_rs_map() and _resolve_templates() methods."""

    def setup_method(self):
        self.scraper = BestEstateScraper()
        self.scraper.ROOM_TYPE_FILTER = []
        self.html = _load_fixture()
        self.soup = BeautifulSoup(self.html, "html.parser")

    def test_build_rs_map_finds_mappings(self):
        """RS map should contain P:→S: entries from $RS scripts."""
        rs_map = self.scraper._build_rs_map(self.soup)
        assert len(rs_map) > 0, "RS map should have at least one mapping"
        for p_id, s_id in rs_map.items():
            assert p_id.startswith("P:"), f"Key should be P:X, got {p_id}"
            assert s_id.startswith("S:"), f"Value should be S:X, got {s_id}"

    def test_resolve_templates_injects_room_data(self):
        """After resolution, template-only cards should contain room rows."""
        rs_map = self.scraper._build_rs_map(self.soup)
        # Count room rows before resolution
        cards_before = self.soup.find_all("div", class_=re.compile(r"lg:border-t-4"))
        cards_with_rooms_before = sum(
            1 for c in cards_before
            if c.find("div", class_=re.compile(r"border-y-\[1px\].*border-beu-border"))
        )
        # Resolve templates
        self.scraper._resolve_templates(self.soup, rs_map)
        # Count room rows after resolution
        cards_after = self.soup.find_all("div", class_=re.compile(r"lg:border-t-4"))
        cards_with_rooms_after = sum(
            1 for c in cards_after
            if c.find("div", class_=re.compile(r"border-y-\[1px\].*border-beu-border"))
        )
        assert cards_with_rooms_after > cards_with_rooms_before, (
            f"Template resolution should add rooms to cards: "
            f"{cards_with_rooms_before} before → {cards_with_rooms_after} after")

    def test_resolve_templates_all_cards_have_rooms(self):
        """After resolution, every property card should have at least 1 room row."""
        rs_map = self.scraper._build_rs_map(self.soup)
        self.scraper._resolve_templates(self.soup, rs_map)
        cards = self.soup.find_all("div", class_=re.compile(r"lg:border-t-4"))
        for i, card in enumerate(cards):
            room_rows = card.find_all(
                "div", class_=re.compile(r"border-y-\[1px\].*border-beu-border"))
            assert len(room_rows) >= 1, (
                f"Card {i} should have at least 1 room row after template resolution")

    def test_template_only_cards_produce_properties(self):
        """Cards that have no inline rooms should still produce properties after resolution."""
        # Parse with template resolution (normal path)
        props = self.scraper.parse_page(self.html, AREA)
        assert len(props) == 7, (
            f"All 7 cards (including 3 template-only) should produce properties, got {len(props)}")
        # Every property must have rooms
        for i, prop in enumerate(props):
            assert len(prop.rooms) >= 1, (
                f"Property {i} ({prop.name}) should have rooms")


class TestBestEstateRobustness:
    """Tests for graceful degradation and edge cases."""

    def setup_method(self):
        self.scraper = BestEstateScraper()
        self.scraper.ROOM_TYPE_FILTER = []

    def test_parse_page_without_rs_scripts_still_parses_inline(self):
        """If $RS scripts are stripped, inline cards should still parse."""
        html = _load_fixture()
        # Strip all <script> tags containing $RS
        html_no_rs = re.sub(
            r'<script>[^<]*\$RS[^<]*</script>', '', html)
        props = self.scraper.parse_page(html_no_rs, AREA)
        assert len(props) >= 4, (
            f"Without RS scripts, at least 4 inline-room cards should parse, got {len(props)}")

    def test_parse_page_with_empty_html(self):
        """Empty string should return empty list, no crash."""
        props = self.scraper.parse_page("", AREA)
        assert props == []

    def test_parse_page_with_no_cards(self):
        """Valid HTML with no property cards should return empty list."""
        props = self.scraper.parse_page("<html><body><p>No listings</p></body></html>", AREA)
        assert props == []
