"""Tests for pipeline/normalise.py — normalisation of raw scraper results."""

import json
import os

from pipeline.normalise import (
    SOURCE_FIELDS,
    build_geocode_field,
    deduplicate_ids,
    generate_id,
    infer_geocode_confidence,
    normalise_source,
    parse_size_sqm,
    parse_walk_minutes,
)
from shared.config import Area

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Area used in tests
# ---------------------------------------------------------------------------
KAWAGUCHI = Area("Kawaguchi (川口市)", "saitama", 35.808, 139.724)
WAKO = Area("Wako (和光市)", "saitama", 35.787, 139.606)


class TestParseSizeSqm:
    def test_m2_format(self):
        assert parse_size_sqm("66.15m2") == 66.15

    def test_m2_unicode_format(self):
        assert parse_size_sqm("66.15m²") == 66.15

    def test_sqm_fullwidth_format(self):
        assert parse_size_sqm("75㎡") == 75.0

    def test_integer_size(self):
        assert parse_size_sqm("48㎡") == 48.0

    def test_none_input(self):
        assert parse_size_sqm(None) is None

    def test_empty_string(self):
        assert parse_size_sqm("") is None

    def test_no_number(self):
        assert parse_size_sqm("sqm") is None


class TestParseWalkMinutes:
    def test_jp_walk_pattern(self):
        assert parse_walk_minutes("埼玉高速鉄道「新井宿」駅 徒歩11分") == 11

    def test_jp_short_walk_pattern(self):
        assert parse_walk_minutes("東武東上線/成増駅 歩17分") == 17

    def test_en_walk_pattern(self):
        assert parse_walk_minutes("6 min. walk from Kawaguchi Station") == 6

    def test_en_walk_no_dot(self):
        assert parse_walk_minutes("10 min walk") == 10

    def test_multiple_jp_takes_minimum(self):
        access = "東武東上線「和光市」駅 徒歩17分 / 東京メトロ副都心線 徒歩5分"
        assert parse_walk_minutes(access) == 5

    def test_no_walk_time(self):
        assert parse_walk_minutes("バス10分") == -1

    def test_none_input(self):
        assert parse_walk_minutes(None) == -1

    def test_empty_string(self):
        assert parse_walk_minutes("") == -1

    def test_range_pattern(self):
        access = "東武東上線「和光市」駅 徒歩17～19分"
        assert parse_walk_minutes(access) == 17


class TestGenerateId:
    def test_basic_id(self):
        result = generate_id("suumo", "Kawaguchi (川口市)", "シンメイ", "3LDK", 66.15)
        assert result.startswith("suumo__kawaguchi__")
        assert "3ldk" in result
        assert "66.15" in result

    def test_different_sources_different_ids(self):
        id1 = generate_id("suumo", "Kawaguchi (川口市)", "Building", "2LDK", 50.0)
        id2 = generate_id("ur", "Kawaguchi (川口市)", "Building", "2LDK", 50.0)
        assert id1 != id2

    def test_none_size(self):
        result = generate_id("suumo", "Area (X)", "Building", "2LDK", None)
        assert "0" in result


class TestDeduplicateIds:
    def test_no_duplicates(self):
        listings = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        deduplicate_ids(listings)
        assert [l["id"] for l in listings] == ["a", "b", "c"]

    def test_with_duplicates(self):
        listings = [{"id": "a"}, {"id": "a"}, {"id": "a"}]
        deduplicate_ids(listings)
        ids = [l["id"] for l in listings]
        assert len(set(ids)) == 3
        assert ids[0] == "a"
        assert ids[1] == "a__1"
        assert ids[2] == "a__2"


class TestGeocodeConfidence:
    def test_csis_provider(self):
        entry = {"lat": 35.0, "lng": 139.0, "provider": "csis"}
        assert infer_geocode_confidence("suumo", entry) == "precise"

    def test_nominatim_gaijinpot(self):
        entry = {"lat": 35.0, "lng": 139.0, "provider": "nominatim"}
        assert infer_geocode_confidence("gaijinpot", entry) == "neighbourhood"

    def test_nominatim_wagaya(self):
        entry = {"lat": 35.0, "lng": 139.0, "provider": "nominatim"}
        assert infer_geocode_confidence("wagaya", entry) == "city"

    def test_no_provider_ur(self):
        entry = {"lat": 35.0, "lng": 139.0, "q": "addr"}
        assert infer_geocode_confidence("ur", entry) == "precise"

    def test_no_provider_gaijinpot(self):
        entry = {"lat": 35.0, "lng": 139.0, "q": "addr"}
        assert infer_geocode_confidence("gaijinpot", entry) == "neighbourhood"

    def test_none_entry(self):
        assert infer_geocode_confidence("suumo", None) is None


class TestBuildGeocodeField:
    def setup_method(self):
        self.cache = {
            "川口市本町2丁目5-8": {
                "lat": 35.808, "lng": 139.724, "q": "test"
            },
            "埼玉県和光市白子３": {
                "lat": 35.787, "lng": 139.606, "q": "test", "provider": "csis"
            },
        }

    def test_ur_address_lookup(self):
        result = build_geocode_field("ur", "川口市本町2丁目5-8", KAWAGUCHI, self.cache)
        assert result is not None
        assert result["lat"] == 35.808
        assert result["confidence"] == "precise"

    def test_suumo_address_lookup(self):
        result = build_geocode_field("suumo", "埼玉県和光市白子３", WAKO, self.cache)
        assert result is not None
        assert result["lat"] == 35.787
        assert result["confidence"] == "precise"

    def test_missing_address(self):
        result = build_geocode_field("suumo", "Not in cache", WAKO, self.cache)
        assert result is None


class TestNormaliseURSource:
    def setup_method(self):
        self.data = _load_fixture("normalise_ur_sample.json")

    def test_room_count(self):
        listings = normalise_source(self.data, "ur", {})
        assert len(listings) == 2

    def test_ur_fields(self):
        listings = normalise_source(self.data, "ur", {})
        room = listings[0]
        assert room["source"] == "ur"
        assert room["area_name"] == "Kawaguchi (川口市)"
        assert room["prefecture"] == "saitama"
        assert room["room_type"] == "2LDK"
        assert room["size_sqm"] == 48.0
        assert room["rent_value"] == 93800
        assert room["admin_fee_value"] == 7100
        assert room["total_monthly"] == 100900
        assert room["room_name"] == "1号棟 507号室"

    def test_ur_move_in_cost_zero(self):
        """UR has no key money — move_in_cost should be 0."""
        listings = normalise_source(self.data, "ur", {})
        for room in listings:
            assert room["move_in_cost"] == 0
            assert room["deposit_value"] == 0
            assert room["key_money_value"] == 0

    def test_ur_walk_time(self):
        listings = normalise_source(self.data, "ur", {})
        assert listings[0]["walk_minutes_claimed"] == 11

    def test_ur_building_age_none(self):
        """UR doesn't have building age."""
        listings = normalise_source(self.data, "ur", {})
        assert listings[0]["building_age_years"] is None

    def test_enrichment_fields_null(self):
        listings = normalise_source(self.data, "ur", {})
        for room in listings:
            assert room["commute"] is None
            assert room["amenities"] is None
            assert room["hazard"] is None
            assert room["scores"] is None
            assert room["grade"] is None


class TestNormaliseStandardSource:
    def setup_method(self):
        self.data = _load_fixture("normalise_standard_sample.json")

    def test_room_count(self):
        listings = normalise_source(self.data, "suumo", {})
        assert len(listings) == 2

    def test_suumo_fields(self):
        listings = normalise_source(self.data, "suumo", {})
        room = listings[0]
        assert room["source"] == "suumo"
        assert room["area_name"] == "Wako (和光市)"
        assert room["area_en"] == "Wako"
        assert room["prefecture"] == "saitama"
        assert room["room_type"] == "3LDK"
        assert room["size_sqm"] == 66.15
        assert room["rent_value"] == 118000
        assert room["admin_fee_value"] == 10000
        assert room["total_monthly"] == 128000
        assert room["deposit_value"] == 118000
        assert room["key_money_value"] == 0

    def test_suumo_move_in_cost(self):
        listings = normalise_source(self.data, "suumo", {})
        # First room: rent (118000) + deposit (118000) + key_money (0) = 236000
        assert listings[0]["move_in_cost"] == 236000
        # Second room: rent (105000) + deposit (105000) + key_money (105000) = 315000
        assert listings[1]["move_in_cost"] == 315000

    def test_suumo_building_age(self):
        listings = normalise_source(self.data, "suumo", {})
        assert listings[0]["building_age_years"] == 30

    def test_suumo_walk_time(self):
        listings = normalise_source(self.data, "suumo", {})
        # access has 歩17分 and 歩18分, min is 17
        assert listings[0]["walk_minutes_claimed"] == 17

    def test_suumo_url(self):
        listings = normalise_source(self.data, "suumo", {})
        assert "suumo.jp" in listings[0]["url"]

    def test_id_stability(self):
        """Same input should produce same IDs."""
        listings1 = normalise_source(self.data, "suumo", {})
        listings2 = normalise_source(self.data, "suumo", {})
        for l1, l2 in zip(listings1, listings2):
            assert l1["id"] == l2["id"]

    def test_id_uniqueness_after_dedup(self):
        listings = normalise_source(self.data, "suumo", {})
        deduplicate_ids(listings)
        ids = [l["id"] for l in listings]
        assert len(ids) == len(set(ids))
