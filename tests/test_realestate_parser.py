"""Tests for realestate_jp_search.parse_page using fixture HTML."""

import os
from shared.config import Area

from realestate_jp_search import parse_page, parse_year_built, build_url

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

AREA = Area("Kawaguchi (川口市)", "saitama", rej_prefecture="JP-11", rej_city="11203")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "realestate_jp_page.html"), encoding="utf-8") as f:
        return f.read()


class TestRealEstateJPParser:
    def setup_method(self):
        html = _load_fixture()
        self.rooms = parse_page(html)

    def test_returns_rooms(self):
        assert len(self.rooms) == 2

    def test_monthly_cost_values(self):
        costs = [r.monthly_cost_value for r in self.rooms]
        assert 115000 in costs
        assert 145000 in costs

    def test_layouts(self):
        layouts = [r.layout for r in self.rooms]
        assert "2LDK" in layouts
        assert "3LDK" in layouts

    def test_station_info(self):
        for room in self.rooms:
            assert "Kawaguchi" in room.station or "Nishi-Kawaguchi" in room.station

    def test_year_built(self):
        years = [r.year_built_int for r in self.rooms]
        assert 2008 in years
        assert 2015 in years

    def test_detail_urls(self):
        for room in self.rooms:
            assert room.detail_url.startswith("https://realestate.co.jp/en/rent/view/")


class TestParseYearBuilt:
    def test_valid_year(self):
        assert parse_year_built("2008") == 2008

    def test_empty_returns_negative(self):
        assert parse_year_built("") == -1

    def test_no_year_returns_negative(self):
        assert parse_year_built("unknown") == -1


class TestRealEstateBuildUrl:
    def test_first_page(self):
        url = build_url(AREA, page=1)
        assert "page=" not in url
        assert "JP-11" in url
        assert "11203" in url

    def test_second_page(self):
        url = build_url(AREA, page=2)
        assert "page=2" in url
