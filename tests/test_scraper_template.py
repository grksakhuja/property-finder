"""Tests for shared.scraper_template — safe_write_json, BaseScraper.search_area, save_results."""

import json
import os
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
import requests

from shared.config import Area
from shared.scraper_template import (
    BaseScraper,
    StandardProperty,
    StandardRoom,
    safe_write_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_room(**overrides):
    defaults = dict(
        floor="3F", rent="¥80,000", rent_value=80000,
        admin_fee="¥5,000", admin_fee_value=5000, total_value=85000,
        deposit="¥80,000", deposit_value=80000,
        key_money="¥0", key_money_value=0,
        layout="1K", size="25.0m²", detail_url="https://example.com/room/1",
    )
    defaults.update(overrides)
    return StandardRoom(**defaults)


def _make_property(area_name="TestArea", n_rooms=1, **overrides):
    defaults = dict(
        name="Test Building",
        address="1-2-3 Test",
        access="5 min walk",
        building_age="10 years",
        building_age_years=10,
        area_name=area_name,
        prefecture="saitama",
        rooms=[_make_room() for _ in range(n_rooms)],
    )
    defaults.update(overrides)
    return StandardProperty(**defaults)


class _StubScraper(BaseScraper):
    """Minimal concrete scraper for testing BaseScraper methods."""

    SOURCE_NAME = "stub"
    OUTPUT_FILE = "results_stub.json"
    ITEMS_PER_PAGE = 3

    def __init__(self):
        # skip parent __init__ to avoid logging setup side-effects
        pass

    def build_url(self, area, page=1):
        return f"https://stub.test/{area.name}?page={page}"

    def parse_page(self, html, area):
        return []


# ---------------------------------------------------------------------------
# safe_write_json
# ---------------------------------------------------------------------------

class TestSafeWriteJson:
    def test_creates_file_with_correct_json(self, tmp_path):
        fp = str(tmp_path / "out.json")
        data = {"key": "value", "num": 42}
        safe_write_json(data, fp)

        with open(fp, encoding="utf-8") as f:
            assert json.load(f) == data

    def test_creates_timestamped_backup_on_overwrite(self, tmp_path):
        fp = str(tmp_path / "out.json")
        safe_write_json({"v": 1}, fp)
        safe_write_json({"v": 2}, fp)

        files = os.listdir(tmp_path)
        backups = [f for f in files if f != "out.json"]
        assert len(backups) == 1
        assert backups[0].startswith("out.") and backups[0].endswith(".json")

    def test_prunes_old_backups(self, tmp_path):
        fp = str(tmp_path / "out.json")
        # Create 5 writes → 4 backups, but max_backups=2
        for i in range(5):
            safe_write_json({"v": i}, fp, max_backups=2)

        files = os.listdir(tmp_path)
        backups = [f for f in files if f != "out.json"]
        assert len(backups) <= 2

    def test_cleans_up_temp_file_on_write_error(self, tmp_path):
        fp = str(tmp_path / "out.json")
        with patch("shared.scraper_template.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                safe_write_json({"a": 1}, fp)

        # No files should remain (temp file cleaned up, target never created)
        assert len(os.listdir(tmp_path)) == 0

    def test_raises_on_nonexistent_directory(self):
        with pytest.raises(FileNotFoundError):
            safe_write_json({"a": 1}, "/nonexistent/dir/file.json")


# ---------------------------------------------------------------------------
# BaseScraper.search_area
# ---------------------------------------------------------------------------

class TestSearchArea:
    def setup_method(self):
        self.scraper = _StubScraper()
        self.scraper.logger = MagicMock()
        self.area = Area("TestArea (テスト)", "saitama")

    def test_uses_class_max_pages_when_zero(self):
        """max_pages <= 0 should fall back to MAX_PAGES_PER_AREA."""
        session = MagicMock()
        self.scraper.parse_page = MagicMock(return_value=[])

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.return_value = MagicMock(text="<html></html>")
            self.scraper.search_area(self.area, session, max_pages=0)

        # Should have been called (using class default MAX_PAGES_PER_AREA)
        mock_fetch.assert_called_once()

    def test_stops_on_empty_first_page(self):
        session = MagicMock()
        self.scraper.parse_page = MagicMock(return_value=[])

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.return_value = MagicMock(text="<html></html>")
            result = self.scraper.search_area(self.area, session, max_pages=3)

        assert result == []
        mock_fetch.assert_called_once()

    def test_stops_when_rooms_below_items_per_page(self):
        """Should stop paginating when room count < ITEMS_PER_PAGE."""
        session = MagicMock()
        # Return 2 rooms on page 1 (< ITEMS_PER_PAGE=3) → stop
        props = [_make_property(n_rooms=2)]
        self.scraper.parse_page = MagicMock(return_value=props)

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.return_value = MagicMock(text="<html></html>")
            result = self.scraper.search_area(self.area, session, max_pages=5)

        assert len(result) == 1
        mock_fetch.assert_called_once()  # only page 1

    def test_paginates_when_full_page(self):
        """Should request page 2 when page 1 has >= ITEMS_PER_PAGE rooms."""
        session = MagicMock()
        full_page = [_make_property(n_rooms=3)]  # 3 rooms = ITEMS_PER_PAGE
        partial_page = [_make_property(n_rooms=1)]

        self.scraper.parse_page = MagicMock(side_effect=[full_page, partial_page])

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.return_value = MagicMock(text="<html></html>")
            result = self.scraper.search_area(self.area, session, max_pages=5)

        assert len(result) == 2
        assert mock_fetch.call_count == 2

    def test_handles_request_exception(self):
        """Should return partial results on RequestException."""
        session = MagicMock()

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.side_effect = requests.RequestException("connection error")
            result = self.scraper.search_area(self.area, session, max_pages=3)

        assert result == []

    def test_handles_parse_exception(self):
        """Should stop and return partial results on parse error."""
        session = MagicMock()
        self.scraper.parse_page = MagicMock(side_effect=ValueError("bad html"))

        with patch("shared.scraper_template.fetch_page") as mock_fetch:
            mock_fetch.return_value = MagicMock(text="<html></html>")
            result = self.scraper.search_area(self.area, session, max_pages=3)

        assert result == []


# ---------------------------------------------------------------------------
# BaseScraper.save_results
# ---------------------------------------------------------------------------

class TestSaveResults:
    def setup_method(self):
        self.scraper = _StubScraper()
        self.scraper.logger = MagicMock()

    def test_json_has_correct_flat_structure(self, tmp_path):
        fp = str(tmp_path / "results.json")
        props = [_make_property(area_name="A", n_rooms=2)]
        self.scraper.save_results(props, filename=fp)

        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        assert data["source"] == "stub"
        assert data["total_rooms"] == 2
        assert isinstance(data["rooms"], list)
        assert len(data["rooms"]) == 2
        # Each room should have flat fields
        room = data["rooms"][0]
        assert room["source"] == "stub"
        assert room["area"] == "A"
        assert room["building"] == "Test Building"
        assert "rent" in room
        assert "total_monthly" in room
        assert "walk_minutes" in room

    def test_flat_rooms_from_multiple_areas(self, tmp_path):
        fp = str(tmp_path / "results.json")
        props = [
            _make_property(area_name="A"),
            _make_property(area_name="B"),
            _make_property(area_name="A"),
        ]
        self.scraper.save_results(props, filename=fp)

        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_rooms"] == 3
        areas = [r["area"] for r in data["rooms"]]
        assert areas.count("A") == 2
        assert areas.count("B") == 1

    def test_uses_output_file_when_filename_empty(self, tmp_path):
        self.scraper.OUTPUT_FILE = str(tmp_path / "results_stub.json")
        props = [_make_property()]
        self.scraper.save_results(props, filename="")

        assert os.path.exists(self.scraper.OUTPUT_FILE)


class TestToFlatRooms:
    def setup_method(self):
        self.scraper = _StubScraper()

    def test_flattens_properties_to_room_dicts(self):
        props = [_make_property(area_name="TestArea", n_rooms=2)]
        rooms = self.scraper.to_flat_rooms(props)

        assert len(rooms) == 2
        for room in rooms:
            assert room["source"] == "stub"
            assert room["area"] == "TestArea"
            assert room["building"] == "Test Building"
            assert isinstance(room["rent"], int)
            assert isinstance(room["total_monthly"], int)
            assert isinstance(room["size_sqm"], float)

    def test_includes_walk_minutes(self):
        prop = _make_property(access="JR京浜東北線 川口駅 徒歩8分")
        rooms = self.scraper.to_flat_rooms([prop])

        assert rooms[0]["walk_minutes"] == 8

    def test_walk_minutes_none_when_no_access(self):
        prop = _make_property(access="")
        rooms = self.scraper.to_flat_rooms([prop])

        assert rooms[0]["walk_minutes"] is None
