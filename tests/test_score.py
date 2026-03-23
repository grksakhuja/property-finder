"""Tests for pipeline/score.py — percentile-based scoring engine."""

from pipeline.score import (
    DEFAULT_WEIGHTS,
    compute_hazard_penalty,
    compute_percentiles,
    get_grade,
    score_area_character,
    score_listings,
    score_room_type,
)


# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------
class TestGetGrade:
    def test_a_grade(self):
        assert get_grade(80) == "A"
        assert get_grade(95) == "A"
        assert get_grade(100) == "A"

    def test_b_grade(self):
        assert get_grade(65) == "B"
        assert get_grade(79.9) == "B"

    def test_c_grade(self):
        assert get_grade(50) == "C"
        assert get_grade(64.9) == "C"

    def test_d_grade(self):
        assert get_grade(0) == "D"
        assert get_grade(49.9) == "D"


# ---------------------------------------------------------------------------
# Percentile computation
# ---------------------------------------------------------------------------
class TestComputePercentiles:
    def test_empty_list(self):
        assert compute_percentiles([]) == {}

    def test_single_value(self):
        result = compute_percentiles([(0, 50)])
        assert result[0] == 50.0

    def test_ascending_values(self):
        values = [(0, 10), (1, 20), (2, 30), (3, 40), (4, 50)]
        result = compute_percentiles(values)
        assert result[0] == 0.0  # lowest
        assert result[4] == 100.0  # highest

    def test_inverted(self):
        values = [(0, 10), (1, 20), (2, 30), (3, 40), (4, 50)]
        result = compute_percentiles(values, invert=True)
        assert result[0] == 100.0  # lowest value → highest percentile
        assert result[4] == 0.0  # highest value → lowest percentile

    def test_two_values(self):
        values = [(0, 100), (1, 200)]
        result = compute_percentiles(values)
        assert result[0] == 0.0
        assert result[1] == 100.0


# ---------------------------------------------------------------------------
# Room type scoring
# ---------------------------------------------------------------------------
class TestScoreRoomType:
    def test_preferred_type(self):
        config = {"roomType": {"2LDK": 1.0, "3LDK": 0.7}}
        assert score_room_type("2LDK", config) == 100.0

    def test_partial_match(self):
        config = {"roomType": {"2LDK": 1.0, "3LDK": 0.7}}
        assert score_room_type("3LDK", config) == 70.0

    def test_unknown_type(self):
        config = {"roomType": {"2LDK": 1.0}}
        assert score_room_type("4LDK", config) == 30.0

    def test_none_type(self):
        config = {"roomType": {"2LDK": 1.0}}
        assert score_room_type(None, config) is None


# ---------------------------------------------------------------------------
# Area character scoring
# ---------------------------------------------------------------------------
class TestScoreAreaCharacter:
    def test_all_fives(self):
        profiles = {
            "Area A": {
                "dimensions": {
                    "safety": {"rating": 5},
                    "foreigner_friendliness": {"rating": 5},
                    "daily_convenience": {"rating": 5},
                    "noise_atmosphere": {"rating": 5},
                    "local_character": {"rating": 5},
                    "transport_connectivity": {"rating": 5},
                }
            }
        }
        assert score_area_character("Area A", profiles) == 100.0

    def test_all_ones(self):
        profiles = {
            "Area A": {
                "dimensions": {
                    "safety": {"rating": 1},
                    "foreigner_friendliness": {"rating": 1},
                    "daily_convenience": {"rating": 1},
                    "noise_atmosphere": {"rating": 1},
                    "local_character": {"rating": 1},
                    "transport_connectivity": {"rating": 1},
                }
            }
        }
        assert score_area_character("Area A", profiles) == 0.0

    def test_all_threes(self):
        profiles = {
            "Area A": {
                "dimensions": {
                    "safety": {"rating": 3},
                    "foreigner_friendliness": {"rating": 3},
                    "daily_convenience": {"rating": 3},
                    "noise_atmosphere": {"rating": 3},
                    "local_character": {"rating": 3},
                    "transport_connectivity": {"rating": 3},
                }
            }
        }
        assert score_area_character("Area A", profiles) == 50.0

    def test_missing_area(self):
        assert score_area_character("NonExistent", {}) is None

    def test_no_dimensions(self):
        profiles = {"Area A": {"dimensions": {}}}
        assert score_area_character("Area A", profiles) is None


# ---------------------------------------------------------------------------
# Hazard penalty
# ---------------------------------------------------------------------------
class TestHazardPenalty:
    def test_no_hazard_data(self):
        listing = {"hazard": None}
        assert compute_hazard_penalty(listing) == 0

    def test_data_not_available(self):
        listing = {"hazard": {"data_available": False, "flood_risk": None, "liquefaction_risk": None}}
        assert compute_hazard_penalty(listing) == 0

    def test_low_risk(self):
        listing = {"hazard": {"data_available": True, "flood_risk": "low", "liquefaction_risk": "low"}}
        assert compute_hazard_penalty(listing) == 0

    def test_moderate_risk(self):
        listing = {"hazard": {"data_available": True, "flood_risk": "moderate", "liquefaction_risk": "low"}}
        assert compute_hazard_penalty(listing) == -5

    def test_high_risk(self):
        listing = {"hazard": {"data_available": True, "flood_risk": "high", "liquefaction_risk": "low"}}
        assert compute_hazard_penalty(listing) == -15

    def test_both_high(self):
        listing = {"hazard": {"data_available": True, "flood_risk": "high", "liquefaction_risk": "high"}}
        assert compute_hazard_penalty(listing) == -15


# ---------------------------------------------------------------------------
# Integration: score_listings
# ---------------------------------------------------------------------------
class TestScoreListings:
    def setup_method(self):
        self.config = {
            "roomType": {"2LDK": 1.0, "3LDK": 0.7, "1LDK": 0.7},
        }
        self.listings = [
            {
                "area_name": "Kawaguchi (川口市)",
                "room_type": "2LDK",
                "size_sqm": 55.0,
                "total_monthly": 120000,
                "walk_minutes_claimed": 10,
                "move_in_cost": 240000,
                "building_age_years": 15,
                "commute": {"estimated_door_to_door": 35, "total_minutes": 25},
                "amenities": {"konbini_500m": 3, "supermarkets_500m": 2, "clinics_1km": 1, "parks_500m": 1},
                "hazard": {"data_available": False, "flood_risk": None, "liquefaction_risk": None},
            },
            {
                "area_name": "Wako (和光市)",
                "room_type": "3LDK",
                "size_sqm": 70.0,
                "total_monthly": 150000,
                "walk_minutes_claimed": 15,
                "move_in_cost": 350000,
                "building_age_years": 25,
                "commute": {"estimated_door_to_door": 45, "total_minutes": 30},
                "amenities": {"konbini_500m": 1, "supermarkets_500m": 1, "clinics_1km": 0, "parks_500m": 0},
                "hazard": {"data_available": False, "flood_risk": None, "liquefaction_risk": None},
            },
            {
                "area_name": "Omiya (大宮区)",
                "room_type": "1LDK",
                "size_sqm": 40.0,
                "total_monthly": 80000,
                "walk_minutes_claimed": 5,
                "move_in_cost": 160000,
                "building_age_years": 5,
                "commute": {"estimated_door_to_door": 55, "total_minutes": 45},
                "amenities": None,
                "hazard": None,
            },
        ]

    def test_all_listings_get_scores(self):
        score_listings(self.listings, self.config)
        for l in self.listings:
            assert "scores" in l
            assert "grade" in l
            assert l["scores"]["composite"] >= 0

    def test_all_listings_get_grade(self):
        score_listings(self.listings, self.config)
        for l in self.listings:
            assert l["grade"] in ("A", "B", "C", "D")

    def test_scored_dimensions_count(self):
        score_listings(self.listings, self.config)
        # First listing has all dimensions except area_character
        scores = self.listings[0]["scores"]
        assert scores["scored_dimensions"] >= 7
        assert scores["total_dimensions"] == 9

    def test_missing_data_exclusion(self):
        """Listing 2 has no amenities — daily_convenience should be None."""
        score_listings(self.listings, self.config)
        assert self.listings[2]["scores"]["daily_convenience"] is None

    def test_weight_normalisation(self):
        """Composite score should be between 0 and 100."""
        score_listings(self.listings, self.config)
        for l in self.listings:
            assert 0 <= l["scores"]["composite"] <= 100

    def test_hazard_penalty_applied(self):
        """Add high hazard to a listing and verify lower score."""
        self.listings[0]["hazard"] = {
            "data_available": True,
            "flood_risk": "high",
            "liquefaction_risk": "low",
        }
        score_listings(self.listings, self.config)
        assert self.listings[0]["scores"]["hazard_penalty"] == -15

    def test_completeness_count(self):
        score_listings(self.listings, self.config)
        for l in self.listings:
            scored = l["scores"]["scored_dimensions"]
            total = l["scores"]["total_dimensions"]
            assert 0 <= scored <= total

    def test_room_type_score_present(self):
        score_listings(self.listings, self.config)
        assert self.listings[0]["scores"]["room_type"] == 100.0  # 2LDK = 1.0
        assert self.listings[1]["scores"]["room_type"] == 70.0   # 3LDK = 0.7
