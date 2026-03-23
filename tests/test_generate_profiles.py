"""Tests for pipeline.generate_profiles — schema, validation, and I/O helpers."""

import json
import os
import pytest

from pipeline.generate_profiles import (
    PROFILE_DIMENSIONS,
    VALID_CONFIDENCE_LEVELS,
    VALID_RATING_RANGE,
    get_all_area_names,
    get_missing_areas,
    get_profile_schema,
    load_profiles,
    save_profiles,
    validate_profile,
)
from shared.config import AREAS


def _make_valid_profile(**overrides) -> dict:
    """Build a minimal valid profile, with optional overrides."""
    profile = {
        "area_en": "Kawaguchi",
        "area_jp": "\u5ddd\u53e3\u5e02",
        "prefecture": "saitama",
        "generated_date": "2026-03-16",
        "confidence": "high",
        "summary": "A large residential city north of Tokyo.",
        "dimensions": {
            dim: {"rating": 3, "narrative": f"Narrative for {dim}."}
            for dim in PROFILE_DIMENSIONS
        },
        "sources_consulted": 8,
        "notable_points": ["Close to Tokyo", "Affordable rents"],
    }
    profile.update(overrides)
    return profile


class TestGetProfileSchema:
    def test_returns_dict(self):
        schema = get_profile_schema()
        assert isinstance(schema, dict)

    def test_contains_all_top_level_fields(self):
        schema = get_profile_schema()
        expected_fields = {
            "area_en", "area_jp", "prefecture", "generated_date",
            "confidence", "summary", "dimensions", "sources_consulted",
            "notable_points",
        }
        assert set(schema.keys()) == expected_fields

    def test_dimensions_contains_all_six(self):
        schema = get_profile_schema()
        assert set(schema["dimensions"].keys()) == set(PROFILE_DIMENSIONS)

    def test_dimension_sub_schema(self):
        schema = get_profile_schema()
        for dim_name, dim_schema in schema["dimensions"].items():
            assert "rating" in dim_schema
            assert "narrative" in dim_schema
            assert dim_schema["rating"] is int
            assert dim_schema["narrative"] is str


class TestGetAllAreaNames:
    def test_returns_list(self):
        names = get_all_area_names()
        assert isinstance(names, list)

    def test_count_matches_areas(self):
        names = get_all_area_names()
        assert len(names) == len(AREAS)

    def test_all_names_are_strings(self):
        names = get_all_area_names()
        assert all(isinstance(n, str) for n in names)

    def test_first_area_is_kawaguchi(self):
        names = get_all_area_names()
        assert names[0] == "Kawaguchi (\u5ddd\u53e3\u5e02)"

    def test_no_duplicates(self):
        names = get_all_area_names()
        assert len(names) == len(set(names))


class TestValidateProfile:
    def test_valid_profile_passes(self):
        profile = _make_valid_profile()
        errors = validate_profile(profile, "Kawaguchi (\u5ddd\u53e3\u5e02)")
        assert errors == []

    def test_missing_required_field(self):
        profile = _make_valid_profile()
        del profile["summary"]
        errors = validate_profile(profile, "Kawaguchi (\u5ddd\u53e3\u5e02)")
        assert any("Missing required field: summary" in e for e in errors)

    def test_wrong_type_field(self):
        profile = _make_valid_profile(sources_consulted="not_an_int")
        errors = validate_profile(profile, "Kawaguchi (\u5ddd\u53e3\u5e02)")
        assert any("sources_consulted" in e and "int" in e for e in errors)

    def test_invalid_confidence(self):
        profile = _make_valid_profile(confidence="unknown")
        errors = validate_profile(profile, "Kawaguchi (\u5ddd\u53e3\u5e02)")
        assert any("Invalid confidence" in e for e in errors)

    def test_valid_confidence_levels(self):
        for level in VALID_CONFIDENCE_LEVELS:
            profile = _make_valid_profile(confidence=level)
            errors = validate_profile(profile, "test")
            assert not any("confidence" in e.lower() for e in errors)

    def test_missing_dimension(self):
        profile = _make_valid_profile()
        del profile["dimensions"]["safety"]
        errors = validate_profile(profile, "test")
        assert any("Missing dimension: safety" in e for e in errors)

    def test_missing_dimension_rating(self):
        profile = _make_valid_profile()
        del profile["dimensions"]["safety"]["rating"]
        errors = validate_profile(profile, "test")
        assert any("safety" in e and "rating" in e for e in errors)

    def test_missing_dimension_narrative(self):
        profile = _make_valid_profile()
        del profile["dimensions"]["safety"]["narrative"]
        errors = validate_profile(profile, "test")
        assert any("safety" in e and "narrative" in e for e in errors)

    def test_rating_below_range(self):
        profile = _make_valid_profile()
        profile["dimensions"]["safety"]["rating"] = 0
        errors = validate_profile(profile, "test")
        assert any("out of range" in e for e in errors)

    def test_rating_above_range(self):
        profile = _make_valid_profile()
        profile["dimensions"]["safety"]["rating"] = 6
        errors = validate_profile(profile, "test")
        assert any("out of range" in e for e in errors)

    def test_rating_boundary_values(self):
        for rating in (1, 5):
            profile = _make_valid_profile()
            profile["dimensions"]["safety"]["rating"] = rating
            errors = validate_profile(profile, "test")
            assert not any("out of range" in e for e in errors)

    def test_unexpected_dimension_flagged(self):
        profile = _make_valid_profile()
        profile["dimensions"]["nightlife"] = {"rating": 3, "narrative": "Fun."}
        errors = validate_profile(profile, "test")
        assert any("Unexpected dimension: nightlife" in e for e in errors)

    def test_missing_dimensions_entirely(self):
        profile = _make_valid_profile()
        del profile["dimensions"]
        errors = validate_profile(profile, "test")
        assert any("Missing required field: dimensions" in e for e in errors)

    def test_dimensions_wrong_type(self):
        profile = _make_valid_profile(dimensions="not_a_dict")
        errors = validate_profile(profile, "test")
        assert any("dimensions" in e and "dict" in e for e in errors)

    def test_rating_wrong_type(self):
        profile = _make_valid_profile()
        profile["dimensions"]["safety"]["rating"] = 3.5
        errors = validate_profile(profile, "test")
        assert any("safety" in e and "int" in e for e in errors)

    def test_narrative_wrong_type(self):
        profile = _make_valid_profile()
        profile["dimensions"]["safety"]["narrative"] = 123
        errors = validate_profile(profile, "test")
        assert any("safety" in e and "str" in e for e in errors)


class TestProfileDimensions:
    def test_exactly_six_dimensions(self):
        assert len(PROFILE_DIMENSIONS) == 6

    def test_dimension_names(self):
        expected = {
            "safety", "foreigner_friendliness", "daily_convenience",
            "noise_atmosphere", "local_character", "transport_connectivity",
        }
        assert set(PROFILE_DIMENSIONS) == expected

    def test_schema_dimensions_match_constant(self):
        schema = get_profile_schema()
        assert set(schema["dimensions"].keys()) == set(PROFILE_DIMENSIONS)


class TestRatingRange:
    def test_range_is_1_to_5(self):
        assert list(VALID_RATING_RANGE) == [1, 2, 3, 4, 5]


class TestConfidenceLevels:
    def test_levels(self):
        assert set(VALID_CONFIDENCE_LEVELS) == {"high", "medium", "low"}


class TestGetMissingAreas:
    def test_all_missing_when_empty(self):
        missing = get_missing_areas({})
        assert len(missing) == len(AREAS)

    def test_none_missing_when_all_profiled(self):
        profiles = {area.name: {} for area in AREAS}
        missing = get_missing_areas(profiles)
        assert missing == []

    def test_partial_profiles(self):
        profiles = {AREAS[0].name: {}}
        missing = get_missing_areas(profiles)
        assert len(missing) == len(AREAS) - 1
        assert AREAS[0].name not in missing

    def test_extra_keys_ignored(self):
        profiles = {"Nonexistent Area": {}}
        missing = get_missing_areas(profiles)
        assert len(missing) == len(AREAS)


class TestLoadSaveProfiles:
    def setup_method(self):
        self.tmp_root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_tmp_profiles_test"
        )
        self.data_dir = os.path.join(self.tmp_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)

    def teardown_method(self):
        path = os.path.join(self.data_dir, "neighbourhood_profiles.json")
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(self.data_dir):
            os.rmdir(self.data_dir)
        if os.path.exists(self.tmp_root):
            os.rmdir(self.tmp_root)

    def test_load_returns_empty_when_no_file(self):
        result = load_profiles(self.tmp_root)
        assert result == {}

    def test_save_then_load_roundtrip(self):
        profiles = {"Kawaguchi (\u5ddd\u53e3\u5e02)": _make_valid_profile()}
        save_profiles(profiles, self.tmp_root)
        loaded = load_profiles(self.tmp_root)
        assert loaded == profiles

    def test_save_creates_data_directory(self):
        new_root = os.path.join(self.tmp_root, "nested")
        new_data = os.path.join(new_root, "data")
        profiles = {"test": _make_valid_profile()}
        save_profiles(profiles, new_root)
        assert os.path.exists(new_data)
        # cleanup
        os.remove(os.path.join(new_data, "neighbourhood_profiles.json"))
        os.rmdir(new_data)
        os.rmdir(new_root)

    def test_save_overwrites_existing(self):
        profiles_v1 = {"area1": _make_valid_profile()}
        profiles_v2 = {"area2": _make_valid_profile()}
        save_profiles(profiles_v1, self.tmp_root)
        save_profiles(profiles_v2, self.tmp_root)
        loaded = load_profiles(self.tmp_root)
        assert "area2" in loaded
        assert "area1" not in loaded

    def test_save_preserves_unicode(self):
        profiles = {"Kawaguchi (\u5ddd\u53e3\u5e02)": _make_valid_profile()}
        save_profiles(profiles, self.tmp_root)
        loaded = load_profiles(self.tmp_root)
        assert "\u5ddd\u53e3\u5e02" in loaded["Kawaguchi (\u5ddd\u53e3\u5e02)"]["area_jp"]
