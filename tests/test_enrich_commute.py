"""Tests for pipeline/enrich_commute.py — commute enrichment of normalised listings."""

from pipeline.enrich_commute import build_commute_field, enrich_commute


def _make_listing(area_en="Kawaguchi", prefecture="saitama", walk_minutes_claimed=12):
    """Create a minimal listing dict for testing."""
    return {
        "id": "test__kawaguchi__building__2ldk__50.0",
        "source": "suumo",
        "area_en": area_en,
        "prefecture": prefecture,
        "walk_minutes_claimed": walk_minutes_claimed,
        "commute": None,
    }


# Commute config subset matching real scoring_config.json structure
COMMUTE_CONFIG = {
    "known": {
        "Kawaguchi": {"min": 25, "transfers": 0, "line": "Namboku"},
        "Wako": {"min": 30, "transfers": 1, "line": "Tobu Tojo + Marunouchi"},
    },
    "prefectureDefault": {
        "saitama": {"min": 45, "transfers": 1},
        "chiba": {"min": 45, "transfers": 1},
        "kanagawa": {"min": 50, "transfers": 1},
        "tokyo": {"min": 25, "transfers": 1},
    },
}


class TestConfigLookupHit:
    """Listing with area_en in known gets commute data from known."""

    def setup_method(self):
        self.listing = _make_listing(area_en="Kawaguchi", walk_minutes_claimed=12)
        self.result = build_commute_field(
            self.listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )

    def test_total_minutes(self):
        assert self.result["total_minutes"] == 25

    def test_transfers(self):
        assert self.result["transfers"] == 0

    def test_line(self):
        assert self.result["line"] == "Namboku"

    def test_source_field(self):
        assert self.result["source"] == "config_lookup"

    def test_walk_to_station(self):
        assert self.result["walk_to_station_claimed"] == 12

    def test_door_to_door(self):
        assert self.result["estimated_door_to_door"] == 37  # 12 + 25


class TestPrefectureFallback:
    """Listing with unknown area_en falls back to prefectureDefault."""

    def setup_method(self):
        self.listing = _make_listing(
            area_en="UnknownCity", prefecture="chiba", walk_minutes_claimed=8
        )
        self.result = build_commute_field(
            self.listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )

    def test_total_minutes_from_prefecture(self):
        assert self.result["total_minutes"] == 45

    def test_transfers_from_prefecture(self):
        assert self.result["transfers"] == 1

    def test_line_is_none_for_prefecture_default(self):
        assert self.result["line"] is None

    def test_source_field(self):
        assert self.result["source"] == "config_lookup"

    def test_door_to_door(self):
        assert self.result["estimated_door_to_door"] == 53  # 8 + 45


class TestUnknownWalkTimeDefault:
    """walk_minutes_claimed=-1 uses 10 as default in door-to-door calc."""

    def setup_method(self):
        self.listing = _make_listing(area_en="Kawaguchi", walk_minutes_claimed=-1)
        self.result = build_commute_field(
            self.listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )

    def test_walk_defaults_to_10(self):
        assert self.result["walk_to_station_claimed"] == 10

    def test_door_to_door_uses_default(self):
        assert self.result["estimated_door_to_door"] == 35  # 10 + 25


class TestDoorToDoorCalculation:
    """Door-to-door = walk_to_station_claimed + total_minutes."""

    def test_wako_with_walk_15(self):
        listing = _make_listing(area_en="Wako", walk_minutes_claimed=15)
        result = build_commute_field(
            listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )
        assert result["estimated_door_to_door"] == 45  # 15 + 30

    def test_prefecture_default_with_walk_5(self):
        listing = _make_listing(
            area_en="Nowhere", prefecture="tokyo", walk_minutes_claimed=5
        )
        result = build_commute_field(
            listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )
        assert result["estimated_door_to_door"] == 30  # 5 + 25


class TestLineInfoFromConfig:
    """Line info comes from config known entries."""

    def test_known_area_has_line(self):
        listing = _make_listing(area_en="Wako", walk_minutes_claimed=10)
        result = build_commute_field(
            listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )
        assert result["line"] == "Tobu Tojo + Marunouchi"

    def test_prefecture_fallback_no_line(self):
        listing = _make_listing(area_en="Nowhere", prefecture="kanagawa")
        result = build_commute_field(
            listing, COMMUTE_CONFIG["known"], COMMUTE_CONFIG["prefectureDefault"]
        )
        assert result["line"] is None


class TestEnrichCommuteInPlace:
    """enrich_commute modifies listings in-place and returns counts."""

    def setup_method(self):
        self.listings = [
            _make_listing(area_en="Kawaguchi", walk_minutes_claimed=12),
            _make_listing(area_en="UnknownCity", prefecture="saitama", walk_minutes_claimed=7),
            _make_listing(area_en="Wako", walk_minutes_claimed=-1),
        ]
        self.enriched, self.skipped, self.total = enrich_commute(
            self.listings, COMMUTE_CONFIG
        )

    def test_all_enriched(self):
        assert self.enriched == 3
        assert self.skipped == 0
        assert self.total == 3

    def test_commute_populated(self):
        for listing in self.listings:
            assert listing["commute"] is not None
            assert listing["commute"]["source"] == "config_lookup"

    def test_no_match_skipped(self):
        listings = [
            _make_listing(area_en="Mars", prefecture="unknown_pref"),
        ]
        enriched, skipped, total = enrich_commute(listings, COMMUTE_CONFIG)
        assert enriched == 0
        assert skipped == 1
        assert listings[0]["commute"] is None
