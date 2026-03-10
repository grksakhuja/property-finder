"""Tests for geocode_properties — address validation, normalization, geocoding."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from geocode_properties import (
    _guess_prefecture,
    geocode_address,
    is_path_safe,
    load_cache,
    normalize_address_for_geocoding,
    save_cache,
    validate_address,
)


# ---------------------------------------------------------------------------
# validate_address
# ---------------------------------------------------------------------------

class TestValidateAddress:
    def test_valid_ascii_address(self):
        result = validate_address("1-2-3 Kawaguchi, Saitama")
        assert result == "1-2-3 Kawaguchi, Saitama"

    def test_valid_japanese_address(self):
        result = validate_address("埼玉県川口市1丁目")
        assert result == "埼玉県川口市1丁目"

    def test_none_returns_none(self):
        assert validate_address(None) is None

    def test_empty_returns_none(self):
        assert validate_address("") is None

    def test_too_long_returns_none(self):
        assert validate_address("a" * 201) is None

    def test_control_chars_stripped(self):
        # Control chars stripped, then remaining valid text returned
        result = validate_address("Kawaguchi\x00 City")
        assert result == "Kawaguchi City"

    def test_script_tag_returns_none(self):
        assert validate_address("<script>alert(1)</script>") is None


# ---------------------------------------------------------------------------
# is_path_safe
# ---------------------------------------------------------------------------

class TestIsPathSafe:
    def test_path_inside_project_root(self):
        # Use a path that's definitely inside the project
        from geocode_properties import PROJECT_ROOT
        safe = os.path.join(PROJECT_ROOT, "results_test.json")
        assert is_path_safe(safe) is True

    def test_path_traversal_rejected(self):
        from geocode_properties import PROJECT_ROOT
        # Construct a path that escapes PROJECT_ROOT
        dangerous = os.path.join(PROJECT_ROOT, "..", "..", "etc", "passwd")
        assert is_path_safe(dangerous) is False


# ---------------------------------------------------------------------------
# normalize_address_for_geocoding
# ---------------------------------------------------------------------------

class TestNormalizeAddress:
    def test_ur_saitama_prepends_kanji(self):
        result = normalize_address_for_geocoding("川口市1丁目", "ur", "saitama")
        assert result.startswith("埼玉県")

    def test_ur_no_double_prepend(self):
        result = normalize_address_for_geocoding("埼玉県川口市1丁目", "ur", "saitama")
        assert not result.startswith("埼玉県埼玉県")

    def test_english_source_strips_in_prefix(self):
        result = normalize_address_for_geocoding("in Kawaguchi, Saitama", "gaijinpot")
        assert not result.startswith("in ")
        assert result.endswith(", Japan")

    def test_english_source_no_double_japan(self):
        result = normalize_address_for_geocoding("Kawaguchi, Japan", "wagaya")
        assert not result.endswith("Japan, Japan")

    def test_suumo_returns_unchanged(self):
        addr = "埼玉県川口市1丁目"
        result = normalize_address_for_geocoding(addr, "suumo")
        assert result == addr

    def test_invalid_address_returns_none(self):
        result = normalize_address_for_geocoding("", "gaijinpot")
        assert result is None


# ---------------------------------------------------------------------------
# _guess_prefecture
# ---------------------------------------------------------------------------

class TestGuessPrefecture:
    def test_kawaguchi_is_saitama(self):
        assert _guess_prefecture("Kawaguchi") == "saitama"

    def test_yokohama_is_kanagawa(self):
        assert _guess_prefecture("Yokohama Naka-ku") == "kanagawa"

    def test_kita_ku_is_tokyo(self):
        assert _guess_prefecture("Kita-ku") == "tokyo"

    def test_unknown_returns_empty(self):
        assert _guess_prefecture("Sapporo") == ""


# ---------------------------------------------------------------------------
# geocode_address
# ---------------------------------------------------------------------------

class TestGeocodeAddress:
    def _mock_session(self, json_data, status_code=200):
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        resp.status_code = status_code
        session.get.return_value = resp
        return session

    def test_valid_response_returns_coords(self):
        session = self._mock_session([{"lat": "35.8069", "lon": "139.7210"}])
        last_time = [0.0]

        with patch("geocode_properties.time.sleep"):
            result = geocode_address(session, "Kawaguchi, Saitama", last_time)

        assert result is not None
        lat, lng = result
        assert 35.0 < lat < 36.0
        assert 139.0 < lng < 140.0

    def test_empty_response_returns_none(self):
        session = self._mock_session([])
        last_time = [0.0]

        with patch("geocode_properties.time.sleep"):
            result = geocode_address(session, "Nonexistent Place", last_time)

        assert result is None

    def test_outside_japan_returns_none(self):
        # Coordinates in Europe (outside Japan bbox)
        session = self._mock_session([{"lat": "48.8566", "lon": "2.3522"}])
        last_time = [0.0]

        with patch("geocode_properties.time.sleep"):
            result = geocode_address(session, "Paris France", last_time)

        assert result is None


# ---------------------------------------------------------------------------
# load_cache
# ---------------------------------------------------------------------------

class TestLoadCache:
    def test_missing_file_returns_empty(self, tmp_path):
        with patch("geocode_properties.CACHE_FILE", str(tmp_path / "nope.json")):
            assert load_cache() == {}

    def test_malformed_json_returns_empty(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        with patch("geocode_properties.CACHE_FILE", str(bad_file)):
            assert load_cache() == {}


# ---------------------------------------------------------------------------
# save_cache
# ---------------------------------------------------------------------------

class TestSaveCache:
    def test_writes_and_reads_back(self, tmp_path):
        cache_file = str(tmp_path / "geocoded_addresses.json")
        data = {"addr1": {"lat": 35.8, "lng": 139.7, "q": "test"}}
        with patch("geocode_properties.CACHE_FILE", cache_file):
            save_cache(data)
            loaded = load_cache()
        assert loaded == data

    def test_atomic_write_cleans_up_on_error(self, tmp_path):
        cache_file = str(tmp_path / "geocoded_addresses.json")
        with patch("geocode_properties.CACHE_FILE", cache_file):
            with patch("geocode_properties.json.dump", side_effect=OSError("disk full")):
                with pytest.raises(OSError):
                    save_cache({"a": 1})
        # No files should remain
        assert len(list(tmp_path.iterdir())) == 0
