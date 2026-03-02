"""Tests for realestate_jp_search.parse_page using fixture HTML."""

import os
from shared.config import Area

from realestate_jp_search import parse_page

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

AREA = Area("Kawaguchi (川口市)", "saitama", rej_prefecture="JP-11", rej_city="11203")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "realestate_jp_page.html"), encoding="utf-8") as f:
        return f.read()


class TestRealEstateJPParser:
    def test_returns_rooms(self):
        html = _load_fixture()
        rooms = parse_page(html)
        assert len(rooms) == 2

    def test_monthly_cost_values(self):
        html = _load_fixture()
        rooms = parse_page(html)
        costs = [r.monthly_cost_value for r in rooms]
        assert 115000 in costs
        assert 145000 in costs

    def test_layouts(self):
        html = _load_fixture()
        rooms = parse_page(html)
        layouts = [r.layout for r in rooms]
        assert "2LDK" in layouts
        assert "3LDK" in layouts

    def test_station_info(self):
        html = _load_fixture()
        rooms = parse_page(html)
        for room in rooms:
            assert "Kawaguchi" in room.station or "Nishi-Kawaguchi" in room.station

    def test_year_built(self):
        html = _load_fixture()
        rooms = parse_page(html)
        years = [r.year_built_int for r in rooms]
        assert 2008 in years
        assert 2015 in years

    def test_detail_urls(self):
        html = _load_fixture()
        rooms = parse_page(html)
        for room in rooms:
            assert room.detail_url.startswith("https://realestate.co.jp/en/rent/view/")
