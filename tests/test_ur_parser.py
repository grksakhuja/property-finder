"""Tests for ur_rental_search parsing using fixture JSON."""

import json
import os

from shared.parsers import parse_yen
from ur_rental_search import clean_traffic, clean_floorspace

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "ur_api_response.json"), encoding="utf-8") as f:
        return json.load(f)


class TestURParser:
    def test_fixture_has_properties(self):
        data = _load_fixture()
        assert len(data) == 1
        assert data[0]["danchiNm"] == "コンフォール川口"

    def test_room_count(self):
        data = _load_fixture()
        rooms = data[0]["room"]
        assert len(rooms) == 3

    def test_rent_parsing(self):
        data = _load_fixture()
        rooms = data[0]["room"]
        rent_values = [parse_yen(r["rent"]) for r in rooms]
        assert 101800 in rent_values
        assert 125600 in rent_values
        assert 72000 in rent_values

    def test_room_types(self):
        data = _load_fixture()
        types = [r["type"] for r in data[0]["room"]]
        assert "2LDK" in types
        assert "3LDK" in types
        assert "1LDK" in types

    def test_clean_traffic(self):
        data = _load_fixture()
        traffic = clean_traffic(data[0]["traffic"])
        assert "川口駅" in traffic
        assert "徒歩12分" in traffic

    def test_clean_floorspace(self):
        data = _load_fixture()
        fs = clean_floorspace(data[0]["room"][0]["floorspace"])
        assert "㎡" in fs
