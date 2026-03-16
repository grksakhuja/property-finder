"""Tests for build_pois — haversine, _short_name, categorize_element, deduplicate, etc."""

import html as html_mod

import pytest

from build_pois import (
    _short_name,
    assign_pois_to_areas,
    build_bbox,
    categorize_element,
    deduplicate,
    haversine,
    AREA_CENTRES,
)


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_returns_zero(self):
        assert haversine(35.8, 139.7, 35.8, 139.7) == 0.0

    def test_known_distance(self):
        # Kawaguchi station → Akabane station ≈ 3200m
        dist = haversine(35.8069, 139.7210, 35.7778, 139.7207)
        assert 2800 < dist < 3600


# ---------------------------------------------------------------------------
# _short_name
# ---------------------------------------------------------------------------

class TestShortName:
    def test_strips_parenthetical(self):
        assert _short_name("Kawaguchi (川口市)") == "Kawaguchi"

    def test_no_parens_unchanged(self):
        assert _short_name("Nationwide") == "Nationwide"


# ---------------------------------------------------------------------------
# categorize_element
# ---------------------------------------------------------------------------

class TestCategorizeElement:
    def test_station(self):
        el = {
            "lat": 35.8, "lon": 139.7,
            "tags": {"railway": "station", "name": "Kawaguchi", "operator": "JR East"},
        }
        result = categorize_element(el)
        assert result is not None
        assert result["cat"] == "station"
        assert "JR East" in result["lines"]

    def test_supermarket(self):
        el = {
            "lat": 35.8, "lon": 139.7,
            "tags": {"shop": "supermarket", "name": "OK Store"},
        }
        result = categorize_element(el)
        assert result["cat"] == "supermarket"

    def test_hospital(self):
        el = {
            "lat": 35.8, "lon": 139.7,
            "tags": {"amenity": "hospital", "name": "Tokyo Hospital"},
        }
        result = categorize_element(el)
        assert result["cat"] == "hospital"

    def test_no_name_returns_none(self):
        el = {
            "lat": 35.8, "lon": 139.7,
            "tags": {"shop": "supermarket"},
        }
        assert categorize_element(el) is None

    def test_script_in_name_escaped(self):
        el = {
            "lat": 35.8, "lon": 139.7,
            "tags": {"shop": "supermarket", "name": "<script>alert(1)</script>"},
        }
        result = categorize_element(el)
        assert "<script>" not in result["name"]
        assert "&lt;script&gt;" in result["name"]


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def _poi(self, cat, name):
        return {"cat": cat, "name": name, "lat": 35.8, "lng": 139.7}

    def test_duplicates_removed(self):
        pois = [self._poi("station", "Kawaguchi"), self._poi("station", "Kawaguchi")]
        result = deduplicate(pois)
        assert len(result.get("station", [])) == 1

    def test_max_per_cat_enforced(self):
        pois = [self._poi("supermarket", f"Store {i}") for i in range(20)]
        result = deduplicate(pois, max_per_cat=5)
        assert len(result["supermarket"]) == 5

    def test_different_categories_retained(self):
        pois = [self._poi("station", "A"), self._poi("supermarket", "B")]
        result = deduplicate(pois)
        assert "station" in result
        assert "supermarket" in result


# ---------------------------------------------------------------------------
# build_bbox
# ---------------------------------------------------------------------------

class TestBuildBbox:
    def test_returns_four_floats(self):
        bbox = build_bbox()
        assert len(bbox) == 4
        s, w, n, e = bbox
        assert s < n
        assert w < e

    def test_bbox_covers_tokyo_area(self):
        s, w, n, e = build_bbox()
        # Tokyo station approx 35.68, 139.77 — should be inside bbox
        assert s < 35.68 < n
        assert w < 139.77 < e


# ---------------------------------------------------------------------------
# assign_pois_to_areas
# ---------------------------------------------------------------------------

class TestAssignPoisToAreas:
    def test_poi_near_area_centre_assigned(self):
        # Place a POI right at Kawaguchi's centre
        if "Kawaguchi" not in AREA_CENTRES:
            pytest.skip("Kawaguchi not in AREA_CENTRES")
        lat, lng = AREA_CENTRES["Kawaguchi"]
        pois = [{"cat": "station", "name": "Test", "lat": lat, "lng": lng}]
        result = assign_pois_to_areas(pois)
        assert len(result["Kawaguchi"]) == 1

    def test_poi_far_away_not_assigned(self):
        # POI in Hokkaido — outside all area radii
        pois = [{"cat": "station", "name": "Far", "lat": 43.0, "lng": 141.3}]
        result = assign_pois_to_areas(pois)
        total = sum(len(v) for v in result.values())
        assert total == 0
