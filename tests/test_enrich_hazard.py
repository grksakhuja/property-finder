"""Tests for pipeline/enrich_hazard.py — hazard data enrichment."""

import json
import shutil
import os

from pipeline.enrich_hazard import (
    build_stub_hazard,
    classify_risk,
    enrich_hazard,
    has_hazard_data,
    load_hazard_shapes,
)


class TestBuildStubHazard:
    """Test the stub hazard output structure."""

    def test_output_has_required_keys(self):
        result = build_stub_hazard()
        assert "flood_risk" in result
        assert "liquefaction_risk" in result
        assert "data_available" in result

    def test_data_available_is_false(self):
        result = build_stub_hazard()
        assert result["data_available"] is False

    def test_flood_risk_is_null(self):
        result = build_stub_hazard()
        assert result["flood_risk"] is None

    def test_liquefaction_risk_is_null(self):
        result = build_stub_hazard()
        assert result["liquefaction_risk"] is None


class TestEnrichHazard:
    """Test the enrich_hazard function applies stub to all listings."""

    def setup_method(self):
        self.listings = [
            {
                "id": "ur__wako__building_a__2ldk__48.0",
                "source": "ur",
                "area_name": "Wako (和光市)",
                "rent_value": 93800,
                "hazard": None,
            },
            {
                "id": "suumo__kawaguchi__building_b__3ldk__66.15",
                "source": "suumo",
                "area_name": "Kawaguchi (川口市)",
                "rent_value": 118000,
                "hazard": None,
            },
        ]

    def test_all_listings_get_hazard_field(self, tmp_path):
        enrich_hazard(self.listings, str(tmp_path))
        for listing in self.listings:
            assert listing["hazard"] is not None
            assert isinstance(listing["hazard"], dict)

    def test_all_listings_data_available_false(self, tmp_path):
        enrich_hazard(self.listings, str(tmp_path))
        for listing in self.listings:
            assert listing["hazard"]["data_available"] is False

    def test_all_listings_flood_risk_null(self, tmp_path):
        enrich_hazard(self.listings, str(tmp_path))
        for listing in self.listings:
            assert listing["hazard"]["flood_risk"] is None

    def test_all_listings_liquefaction_risk_null(self, tmp_path):
        enrich_hazard(self.listings, str(tmp_path))
        for listing in self.listings:
            assert listing["hazard"]["liquefaction_risk"] is None

    def test_empty_listings_list(self, tmp_path):
        empty = []
        enriched, total = enrich_hazard(empty, str(tmp_path))
        assert enriched == 0
        assert total == 0
        assert empty == []

    def test_preserves_other_fields(self, tmp_path):
        enrich_hazard(self.listings, str(tmp_path))
        assert self.listings[0]["id"] == "ur__wako__building_a__2ldk__48.0"
        assert self.listings[0]["source"] == "ur"
        assert self.listings[0]["area_name"] == "Wako (和光市)"
        assert self.listings[0]["rent_value"] == 93800
        assert self.listings[1]["id"] == "suumo__kawaguchi__building_b__3ldk__66.15"
        assert self.listings[1]["rent_value"] == 118000

    def test_returns_correct_counts(self, tmp_path):
        enriched, total = enrich_hazard(self.listings, str(tmp_path))
        assert enriched == 2
        assert total == 2


class TestHasHazardData:
    """Test GIS data detection."""

    def test_no_directory(self, tmp_path):
        assert has_hazard_data(str(tmp_path)) is False

    def test_empty_directory(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        assert has_hazard_data(str(tmp_path)) is False

    def test_directory_with_non_gis_files(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        (hazard_dir / "readme.txt").write_text("not gis data")
        assert has_hazard_data(str(tmp_path)) is False

    def test_directory_with_shapefile(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        (hazard_dir / "flood_risk.shp").write_text("")
        assert has_hazard_data(str(tmp_path)) is True

    def test_directory_with_geojson(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        (hazard_dir / "liquefaction.geojson").write_text("{}")
        assert has_hazard_data(str(tmp_path)) is True


# ---------------------------------------------------------------------------
# GeoJSON loading and point-in-polygon classification
# ---------------------------------------------------------------------------

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "test_hazard_flood.geojson"
)


class TestLoadHazardShapes:
    def test_loads_flood_features(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_PATH, hazard_dir / "flood_risk.geojson")
        shapes = load_hazard_shapes(str(hazard_dir))
        assert len(shapes["flood"]) == 2
        assert len(shapes["liquefaction"]) == 0

    def test_skips_unrecognised_files(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        (hazard_dir / "unknown.geojson").write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": {
                "type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
            }}]
        }))
        shapes = load_hazard_shapes(str(hazard_dir))
        assert len(shapes["flood"]) == 0
        assert len(shapes["liquefaction"]) == 0


class TestClassifyRisk:
    def setup_method(self):
        """Load the test fixture shapes."""
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        from shapely.geometry import shape
        self.features = []
        for feat in data["features"]:
            self.features.append({
                "geometry": shape(feat["geometry"]),
                "risk_level": feat["properties"]["risk_level"],
            })

    def test_point_inside_high_risk_polygon(self):
        # Centre of first polygon (high risk): ~139.725, 35.805
        result = classify_risk(35.805, 139.725, self.features)
        assert result == "high"

    def test_point_inside_moderate_risk_polygon(self):
        # Centre of second polygon (moderate risk): ~139.735, 35.805
        result = classify_risk(35.805, 139.735, self.features)
        assert result == "moderate"

    def test_point_outside_all_polygons(self):
        # Well outside both polygons
        result = classify_risk(36.0, 140.0, self.features)
        assert result is None

    def test_no_features_returns_none(self):
        result = classify_risk(35.805, 139.725, [])
        assert result is None


class TestEnrichHazardWithGIS:
    """Test enrich_hazard when real GIS data is present."""

    def test_gis_classifies_geocoded_listing(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_PATH, hazard_dir / "flood_risk.geojson")

        listings = [{
            "id": "test__1",
            "geocode": {"lat": 35.805, "lng": 139.725, "confidence": "precise"},
            "hazard": None,
        }]
        enrich_hazard(listings, str(tmp_path))
        assert listings[0]["hazard"]["data_available"] is True
        assert listings[0]["hazard"]["flood_risk"] == "high"

    def test_gis_no_geocode_gets_data_available_true(self, tmp_path):
        hazard_dir = tmp_path / "data" / "hazard_data"
        hazard_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_PATH, hazard_dir / "flood_risk.geojson")

        listings = [{
            "id": "test__2",
            "geocode": None,
            "hazard": None,
        }]
        enrich_hazard(listings, str(tmp_path))
        assert listings[0]["hazard"]["data_available"] is True
        assert listings[0]["hazard"]["flood_risk"] is None
