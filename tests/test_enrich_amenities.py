"""Tests for pipeline/enrich_amenities.py — amenity enrichment via Overpass API."""

import json
import math

import responses

from pipeline.enrich_amenities import (
    OVERPASS_URL,
    RADIUS_500M,
    RADIUS_1KM,
    build_overpass_query,
    compute_convenience_score,
    count_amenities,
    enrich_listings,
    extract_unique_locations,
    haversine_distance,
    load_cache,
    query_overpass,
    round_location,
    save_cache,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

KAWAGUCHI_LAT = 35.808
KAWAGUCHI_LNG = 139.724


def _make_listing(lat=None, lng=None, confidence="precise"):
    """Create a minimal listing dict for testing."""
    geocode = None
    if lat is not None and lng is not None:
        geocode = {"lat": lat, "lng": lng, "confidence": confidence}
    return {
        "id": f"test__{lat}_{lng}",
        "source": "test",
        "geocode": geocode,
        "amenities": None,
    }


def _make_overpass_element(lat, lng, tags):
    """Create a minimal Overpass element dict."""
    return {"type": "node", "id": 1, "lat": lat, "lon": lng, "tags": tags}


def _offset_point(lat, lng, distance_m, bearing_deg=0):
    """Offset a lat/lng point by distance_m in given bearing (degrees).

    Uses a simple spherical approximation sufficient for test purposes.
    """
    R = 6_371_000
    d = distance_m / R
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d)
        + math.cos(lat1) * math.sin(d) * math.cos(bearing)
    )
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lng2)


# ---------------------------------------------------------------------------
# Overpass query construction
# ---------------------------------------------------------------------------


class TestBuildOverpassQuery:
    def test_contains_all_poi_types(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert '"shop"="supermarket"' in query
        assert '"shop"="convenience"' in query
        assert '"amenity"~"clinic|hospital"' in query
        assert '"leisure"="park"' in query

    def test_contains_coordinates(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert str(KAWAGUCHI_LAT) in query
        assert str(KAWAGUCHI_LNG) in query

    def test_contains_radii(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert f"around:{RADIUS_1KM}" in query
        assert f"around:{RADIUS_500M}" in query

    def test_output_format(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert query.startswith("[out:json]")
        assert "out body;" in query

    def test_supermarket_uses_1km_radius(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        # supermarket line should use 1000m
        for line in query.splitlines():
            if "supermarket" in line:
                assert f"around:{RADIUS_1KM}" in line

    def test_convenience_uses_500m_radius(self):
        query = build_overpass_query(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        for line in query.splitlines():
            if "convenience" in line:
                assert f"around:{RADIUS_500M}" in line


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


class TestHaversineDistance:
    def test_same_point_is_zero(self):
        assert haversine_distance(35.0, 139.0, 35.0, 139.0) == 0.0

    def test_known_distance(self):
        # Approx 1 degree latitude ~ 111km
        dist = haversine_distance(35.0, 139.0, 36.0, 139.0)
        assert 110_000 < dist < 112_000

    def test_symmetry(self):
        d1 = haversine_distance(35.0, 139.0, 35.01, 139.01)
        d2 = haversine_distance(35.01, 139.01, 35.0, 139.0)
        assert abs(d1 - d2) < 0.01


# ---------------------------------------------------------------------------
# Cache hit — no API call
# ---------------------------------------------------------------------------


class TestCacheHit:
    def setup_method(self):
        self.cached_amenities = {
            "supermarkets_500m": 2,
            "supermarkets_1km": 5,
            "konbini_500m": 3,
            "clinics_1km": 1,
            "parks_500m": 1,
            "convenience_score": 8.5,  # 2*1.5 + 3*1.0 + 1*0.5 + 1*0.75 + 5*0.25
        }
        self.cache = {
            round_location(KAWAGUCHI_LAT, KAWAGUCHI_LNG): self.cached_amenities,
        }

    @responses.activate
    def test_cache_hit_skips_api(self):
        """When a location is already cached, no Overpass request is made."""
        # No responses registered — any HTTP call would raise ConnectionError
        listings = [_make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG)]
        result = enrich_listings(listings, self.cache)
        assert result[0]["amenities"] == self.cached_amenities

    def test_cache_hit_returns_copy(self):
        """Amenities dict should be a copy, not a reference to cache entry."""
        listings = [_make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG)]
        result = enrich_listings(listings, self.cache)
        result[0]["amenities"]["supermarkets_500m"] = 999
        assert self.cache[round_location(KAWAGUCHI_LAT, KAWAGUCHI_LNG)]["supermarkets_500m"] == 2


# ---------------------------------------------------------------------------
# Cache miss — API called, result cached
# ---------------------------------------------------------------------------


class TestCacheMiss:
    def setup_method(self):
        self.overpass_response = {
            "elements": [
                _make_overpass_element(
                    KAWAGUCHI_LAT + 0.001,
                    KAWAGUCHI_LNG,
                    {"shop": "supermarket"},
                ),
                _make_overpass_element(
                    KAWAGUCHI_LAT,
                    KAWAGUCHI_LNG + 0.001,
                    {"shop": "convenience"},
                ),
            ],
        }

    @responses.activate
    def test_cache_miss_calls_api(self):
        """When location is not cached, Overpass API is queried."""
        responses.add(
            responses.POST,
            OVERPASS_URL,
            json=self.overpass_response,
            status=200,
        )
        elements = query_overpass(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert len(elements) == 2
        assert len(responses.calls) == 1

    @responses.activate
    def test_query_sends_post_with_data(self):
        """Overpass query is sent as POST with 'data' form field."""
        responses.add(
            responses.POST,
            OVERPASS_URL,
            json=self.overpass_response,
            status=200,
        )
        query_overpass(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert "data" in responses.calls[0].request.body


# ---------------------------------------------------------------------------
# Skip logic — city confidence or null geocode
# ---------------------------------------------------------------------------


class TestSkipLogic:
    def setup_method(self):
        self.cache = {}

    def test_null_geocode_gets_none(self):
        listing = _make_listing()  # no lat/lng => geocode is None
        result = enrich_listings([listing], self.cache)
        assert result[0]["amenities"] is None

    def test_city_confidence_gets_none(self):
        listing = _make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG, confidence="city")
        result = enrich_listings([listing], self.cache)
        assert result[0]["amenities"] is None

    def test_precise_confidence_eligible(self):
        key = round_location(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        self.cache[key] = {"supermarkets_500m": 1, "supermarkets_1km": 2,
                           "konbini_500m": 0, "clinics_1km": 0,
                           "parks_500m": 0, "convenience_score": None}
        listing = _make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG, confidence="precise")
        result = enrich_listings([listing], self.cache)
        assert result[0]["amenities"] is not None

    def test_neighbourhood_confidence_eligible(self):
        key = round_location(KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        self.cache[key] = {"supermarkets_500m": 0, "supermarkets_1km": 0,
                           "konbini_500m": 0, "clinics_1km": 0,
                           "parks_500m": 0, "convenience_score": None}
        listing = _make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG, confidence="neighbourhood")
        result = enrich_listings([listing], self.cache)
        assert result[0]["amenities"] is not None

    def test_extract_skips_city_confidence(self):
        listings = [_make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG, confidence="city")]
        locations = extract_unique_locations(listings)
        assert len(locations) == 0

    def test_extract_skips_null_geocode(self):
        listings = [_make_listing()]
        locations = extract_unique_locations(listings)
        assert len(locations) == 0


# ---------------------------------------------------------------------------
# Count aggregation — correct counting of POI types
# ---------------------------------------------------------------------------


class TestCountAmenities:
    def test_empty_elements(self):
        result = count_amenities([], KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result == {
            "supermarkets_500m": 0,
            "supermarkets_1km": 0,
            "konbini_500m": 0,
            "clinics_1km": 0,
            "parks_500m": 0,
            "convenience_score": 0.0,
        }

    def test_mixed_poi_types(self):
        elements = [
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"shop": "supermarket"}),
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"shop": "convenience"}),
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"amenity": "clinic"}),
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"amenity": "hospital"}),
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"leisure": "park"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_500m"] == 1
        assert result["supermarkets_1km"] == 1
        assert result["konbini_500m"] == 1
        assert result["clinics_1km"] == 2  # clinic + hospital
        assert result["parks_500m"] == 1
        # 1*1.5 + 1*1.0 + 2*0.5 + 1*0.75 + 1*0.25 = 4.5
        assert result["convenience_score"] == 4.5

    def test_supermarket_counted_in_both_radii(self):
        """A supermarket within 500m should be counted in both 500m and 1km."""
        elements = [
            _make_overpass_element(KAWAGUCHI_LAT, KAWAGUCHI_LNG, {"shop": "supermarket"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_500m"] == 1
        assert result["supermarkets_1km"] == 1

    def test_element_without_lat_lng_skipped(self):
        elements = [{"type": "node", "id": 1, "tags": {"shop": "supermarket"}}]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_1km"] == 0

    def test_element_without_tags_skipped(self):
        elements = [{"type": "node", "id": 1, "lat": KAWAGUCHI_LAT, "lon": KAWAGUCHI_LNG}]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result == {
            "supermarkets_500m": 0,
            "supermarkets_1km": 0,
            "konbini_500m": 0,
            "clinics_1km": 0,
            "parks_500m": 0,
            "convenience_score": 0.0,
        }


# ---------------------------------------------------------------------------
# Distance filtering — supermarkets_500m only counts within 500m
# ---------------------------------------------------------------------------


class TestDistanceFiltering:
    def test_supermarket_within_500m(self):
        near_lat, near_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 300)
        elements = [
            _make_overpass_element(near_lat, near_lng, {"shop": "supermarket"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_500m"] == 1
        assert result["supermarkets_1km"] == 1

    def test_supermarket_beyond_500m_within_1km(self):
        far_lat, far_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 700)
        elements = [
            _make_overpass_element(far_lat, far_lng, {"shop": "supermarket"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_500m"] == 0
        assert result["supermarkets_1km"] == 1

    def test_supermarket_beyond_1km(self):
        far_lat, far_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 1100)
        elements = [
            _make_overpass_element(far_lat, far_lng, {"shop": "supermarket"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["supermarkets_500m"] == 0
        assert result["supermarkets_1km"] == 0

    def test_konbini_beyond_500m_not_counted(self):
        far_lat, far_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 600)
        elements = [
            _make_overpass_element(far_lat, far_lng, {"shop": "convenience"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["konbini_500m"] == 0

    def test_park_within_500m(self):
        near_lat, near_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 400)
        elements = [
            _make_overpass_element(near_lat, near_lng, {"leisure": "park"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["parks_500m"] == 1

    def test_park_beyond_500m_not_counted(self):
        far_lat, far_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 600)
        elements = [
            _make_overpass_element(far_lat, far_lng, {"leisure": "park"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["parks_500m"] == 0

    def test_clinic_beyond_1km_not_counted(self):
        far_lat, far_lng = _offset_point(KAWAGUCHI_LAT, KAWAGUCHI_LNG, 1100)
        elements = [
            _make_overpass_element(far_lat, far_lng, {"amenity": "clinic"}),
        ]
        result = count_amenities(elements, KAWAGUCHI_LAT, KAWAGUCHI_LNG)
        assert result["clinics_1km"] == 0


# ---------------------------------------------------------------------------
# Location deduplication
# ---------------------------------------------------------------------------


class TestExtractUniqueLocations:
    def test_deduplicates_nearby_points(self):
        """Points that round to the same 3-decimal key are deduplicated."""
        listings = [
            _make_listing(35.8081, 139.7241),
            _make_listing(35.8084, 139.7243),
        ]
        locations = extract_unique_locations(listings)
        assert len(locations) == 1

    def test_different_locations_kept(self):
        listings = [
            _make_listing(35.808, 139.724),
            _make_listing(35.900, 139.800),
        ]
        locations = extract_unique_locations(listings)
        assert len(locations) == 2


# ---------------------------------------------------------------------------
# Round-location key format
# ---------------------------------------------------------------------------


class TestRoundLocation:
    def test_format(self):
        assert round_location(35.8081, 139.7241) == "35.808,139.724"

    def test_rounding(self):
        assert round_location(35.8083, 139.7242) == "35.808,139.724"

    def test_negative_coords(self):
        key = round_location(-33.8688, 151.2093)
        assert key == "-33.869,151.209"


# ---------------------------------------------------------------------------
# Convenience score
# ---------------------------------------------------------------------------


class TestConvenienceScore:
    def test_convenience_score_zero_when_no_amenities(self):
        counts = {
            "supermarkets_500m": 0,
            "supermarkets_1km": 0,
            "konbini_500m": 0,
            "clinics_1km": 0,
            "parks_500m": 0,
        }
        assert compute_convenience_score(counts) == 0.0

    def test_convenience_score_capped_at_10(self):
        counts = {
            "supermarkets_500m": 10,
            "supermarkets_1km": 20,
            "konbini_500m": 10,
            "clinics_1km": 10,
            "parks_500m": 10,
        }
        assert compute_convenience_score(counts) == 10.0

    def test_convenience_score_weighted_sum(self):
        counts = {
            "supermarkets_500m": 2,
            "supermarkets_1km": 4,
            "konbini_500m": 3,
            "clinics_1km": 2,
            "parks_500m": 1,
        }
        # 2*1.5 + 3*1.0 + 2*0.5 + 1*0.75 + 4*0.25 = 3+3+1+0.75+1 = 8.75
        assert compute_convenience_score(counts) == 8.75

    def test_backfill_from_cache_with_null_score(self):
        """Cache entries with convenience_score=None get backfilled."""
        cache = {
            round_location(KAWAGUCHI_LAT, KAWAGUCHI_LNG): {
                "supermarkets_500m": 1,
                "supermarkets_1km": 2,
                "konbini_500m": 1,
                "clinics_1km": 0,
                "parks_500m": 0,
                "convenience_score": None,
            }
        }
        listings = [_make_listing(KAWAGUCHI_LAT, KAWAGUCHI_LNG)]
        result = enrich_listings(listings, cache)
        # 1*1.5 + 1*1.0 + 0*0.5 + 0*0.75 + 2*0.25 = 1.5+1+0.5 = 3.0
        assert result[0]["amenities"]["convenience_score"] == 3.0
