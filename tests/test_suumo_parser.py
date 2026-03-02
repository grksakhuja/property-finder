"""Tests for suumo_search.parse_page using fixture HTML."""

import os
from shared.config import Area

from suumo_search import parse_page

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# A dummy area for parse_page
AREA = Area("Kawaguchi (川口市)", "saitama", suumo_code="sc_kawaguchi")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "suumo_page.html"), encoding="utf-8") as f:
        return f.read()


class TestSuumoParser:
    def test_returns_properties(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        assert len(props) == 2

    def test_property_names(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        names = [p.name for p in props]
        assert "グランドメゾン川口" in names
        assert "サンライズ戸田" in names

    def test_room_count(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        total_rooms = sum(len(p.rooms) for p in props)
        assert total_rooms == 3

    def test_rent_values_positive(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.rent_value > 0

    def test_layout_types(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        layouts = [room.layout for prop in props for room in prop.rooms]
        assert "2LDK" in layouts
        assert "3LDK" in layouts

    def test_building_age(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        ages = {p.name: p.building_age_years for p in props}
        assert ages["グランドメゾン川口"] == 20
        assert ages["サンライズ戸田"] == 0  # 新築

    def test_detail_urls(self):
        html = _load_fixture()
        props = parse_page(html, AREA)
        for prop in props:
            for room in prop.rooms:
                assert room.detail_url.startswith("https://suumo.jp/")
