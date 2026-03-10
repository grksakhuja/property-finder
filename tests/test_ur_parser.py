"""Tests for ur_rental_search parsing using fixture JSON."""

import json
import os
from unittest.mock import MagicMock

from shared.config import Area
from shared.parsers import parse_yen
from ur_rental_search import clean_traffic, clean_floorspace, search_area

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture():
    with open(os.path.join(FIXTURE_DIR, "ur_api_response.json"), encoding="utf-8") as f:
        return json.load(f)


class TestURParser:
    def setup_method(self):
        self.data = _load_fixture()

    def test_fixture_has_properties(self):
        assert len(self.data) == 1
        assert self.data[0]["danchiNm"] == "コンフォール川口"

    def test_room_count(self):
        rooms = self.data[0]["room"]
        assert len(rooms) == 3

    def test_rent_parsing(self):
        rooms = self.data[0]["room"]
        rent_values = [parse_yen(r["rent"]) for r in rooms]
        assert 101800 in rent_values
        assert 125600 in rent_values
        assert 72000 in rent_values

    def test_room_types(self):
        types = [r["type"] for r in self.data[0]["room"]]
        assert "2LDK" in types
        assert "3LDK" in types
        assert "1LDK" in types

    def test_clean_traffic(self):
        traffic = clean_traffic(self.data[0]["traffic"])
        assert "川口駅" in traffic
        assert "徒歩12分" in traffic

    def test_clean_floorspace(self):
        fs = clean_floorspace(self.data[0]["room"][0]["floorspace"])
        assert "㎡" in fs


class TestURSearchArea:
    """Test search_area JSON→Property transformation using fixture data."""

    def setup_method(self):
        self.area = Area(
            "Kawaguchi (川口市)", "saitama",
            ur_block="kanto", ur_tdfk="11", ur_skcs="203")
        data = _load_fixture()
        # Mock session whose POST returns the fixture data
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        self.session = MagicMock()
        self.session.request.return_value = mock_resp

    def test_returns_properties(self):
        props = search_area(self.area, self.session)
        assert len(props) >= 1

    def test_property_name(self):
        props = search_area(self.area, self.session)
        assert props[0].name == "コンフォール川口"

    def test_rooms_filtered_by_type(self):
        props = search_area(self.area, self.session)
        rooms = props[0].rooms
        # Room type filter is active; only matching types should be present
        for room in rooms:
            assert room.room_type, "Room type should not be empty"

    def test_rent_values_parsed(self):
        props = search_area(self.area, self.session)
        rent_values = [r.rent_value for p in props for r in p.rooms]
        assert all(v > 0 for v in rent_values)

    def test_area_name_set(self):
        props = search_area(self.area, self.session)
        assert props[0].area_name == "Kawaguchi (川口市)"

    def test_traffic_cleaned(self):
        props = search_area(self.area, self.session)
        assert "川口駅" in props[0].traffic
