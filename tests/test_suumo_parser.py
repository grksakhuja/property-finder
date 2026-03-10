"""Tests for suumo_search.parse_page using fixture HTML."""

import os
from shared.config import Area

from bs4 import BeautifulSoup

from suumo_search import parse_page, get_total_count, build_url

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# A dummy area for parse_page
AREA = Area("Kawaguchi (川口市)", "saitama", suumo_code="sc_kawaguchi")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "suumo_page.html"), encoding="utf-8") as f:
        return f.read()


class TestSuumoParser:
    def setup_method(self):
        html = _load_fixture()
        self.props = parse_page(html, AREA)

    def test_returns_properties(self):
        assert len(self.props) == 2

    def test_property_names(self):
        names = [p.name for p in self.props]
        assert "グランドメゾン川口" in names
        assert "サンライズ戸田" in names

    def test_room_count(self):
        total_rooms = sum(len(p.rooms) for p in self.props)
        assert total_rooms == 3

    def test_rent_values_positive(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.rent_value > 0

    def test_layout_types(self):
        layouts = [room.layout for prop in self.props for room in prop.rooms]
        assert "2LDK" in layouts
        assert "3LDK" in layouts

    def test_building_age(self):
        ages = {p.name: p.building_age_years for p in self.props}
        assert ages["グランドメゾン川口"] == 20
        assert ages["サンライズ戸田"] == 0  # 新築

    def test_detail_urls(self):
        for prop in self.props:
            for room in prop.rooms:
                assert room.detail_url.startswith("https://suumo.jp/")


class TestGetTotalCount:
    def test_with_hit_element(self):
        html = '<div class="paginate_set-hit">7,492件</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert get_total_count(soup) == 7492

    def test_without_hit_element(self):
        html = '<div class="other">nothing</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert get_total_count(soup) == 0

    def test_empty_hit_element(self):
        html = '<div class="paginate_set-hit"></div>'
        soup = BeautifulSoup(html, "html.parser")
        assert get_total_count(soup) == 0


class TestSuumoBuildUrl:
    def test_first_page(self):
        url = build_url(AREA, page=1)
        assert "page=" not in url
        assert "sc_kawaguchi" in url
        assert "saitama" in url

    def test_second_page(self):
        url = build_url(AREA, page=2)
        assert "page=2" in url
