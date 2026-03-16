"""Tests for shared.cli — area filtering and arg parser."""

from shared.config import Area
from shared.cli import build_arg_parser, filter_areas

AREAS = [
    Area("Kawaguchi (川口市)", "saitama"),
    Area("Kita-ku (北区)", "tokyo"),
    Area("Ichikawa (市川市)", "chiba"),
]


class TestFilterAreas:
    def test_no_filter_returns_all(self):
        result = filter_areas(AREAS, None)
        assert result == AREAS

    def test_empty_list_returns_all(self):
        result = filter_areas(AREAS, [])
        assert result == AREAS

    def test_partial_match(self):
        result = filter_areas(AREAS, ["Kita"])
        assert len(result) == 1
        assert result[0].name == "Kita-ku (北区)"

    def test_case_insensitive(self):
        result = filter_areas(AREAS, ["kita"])
        assert len(result) == 1

    def test_multiple_filters(self):
        result = filter_areas(AREAS, ["Kita", "Ichikawa"])
        assert len(result) == 2

    def test_no_match_returns_empty(self):
        result = filter_areas(AREAS, ["Osaka"])
        assert result == []

    def test_japanese_match(self):
        result = filter_areas(AREAS, ["川口"])
        assert len(result) == 1
        assert "Kawaguchi" in result[0].name


class TestBuildArgParser:
    def test_returns_parser(self):
        parser = build_arg_parser("test", "Test scraper")
        assert parser.prog == "test"

    def test_parses_areas(self):
        parser = build_arg_parser("test", "Test scraper")
        args = parser.parse_args(["--areas", "Kawaguchi", "Kita"])
        assert args.areas == ["Kawaguchi", "Kita"]

    def test_parses_max_pages(self):
        parser = build_arg_parser("test", "Test scraper")
        args = parser.parse_args(["--max-pages", "3"])
        assert args.max_pages == 3

    def test_parses_verbose_and_dry_run(self):
        parser = build_arg_parser("test", "Test scraper")
        args = parser.parse_args(["-v", "--dry-run"])
        assert args.verbose is True
        assert args.dry_run is True

    def test_defaults(self):
        parser = build_arg_parser("test", "Test scraper")
        args = parser.parse_args([])
        assert args.areas is None
        assert args.max_pages is None
        assert args.delay is None
        assert args.output is None
        assert args.verbose is False
        assert args.dry_run is False
        assert args.workers is None
