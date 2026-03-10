"""Tests for shared.config — Area properties and area source filtering."""

import pytest

from shared.config import Area, get_areas_for_source


class TestAreaProperties:
    def test_en_name(self):
        a = Area("Kawaguchi (川口市)", "saitama")
        assert a.en_name == "Kawaguchi"

    def test_jp_name(self):
        a = Area("Kawaguchi (川口市)", "saitama")
        assert a.jp_name == "川口市"

    def test_en_name_no_parens(self):
        a = Area("Nationwide", "all")
        assert a.en_name == "Nationwide"

    def test_jp_name_no_parens(self):
        a = Area("Nationwide", "all")
        assert a.jp_name == ""

    def test_en_name_strips_whitespace(self):
        a = Area("Kita-ku (北区)", "tokyo")
        assert a.en_name == "Kita-ku"


class TestGetAreasForSource:
    def test_ur_returns_areas(self):
        areas = get_areas_for_source("ur")
        assert len(areas) >= 1
        assert all(a.ur_skcs is not None for a in areas)

    def test_gaijinpot_returns_areas(self):
        areas = get_areas_for_source("gaijinpot")
        assert len(areas) >= 1
        assert all(a.gaijinpot_prefecture_id is not None for a in areas)

    def test_wagaya_returns_areas(self):
        areas = get_areas_for_source("wagaya")
        assert len(areas) >= 1
        assert all(a.wagaya_prefecture is not None for a in areas)

    def test_villagehouse_returns_areas(self):
        areas = get_areas_for_source("villagehouse")
        assert len(areas) >= 1
        assert all(a.villagehouse_city is not None for a in areas)

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            get_areas_for_source("nonexistent")
