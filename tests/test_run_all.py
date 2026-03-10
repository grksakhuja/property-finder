"""Tests for run_all — build_scraper_args and run_scraper."""

import argparse
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from run_all import build_scraper_args, run_scraper


# ---------------------------------------------------------------------------
# build_scraper_args
# ---------------------------------------------------------------------------

class TestBuildScraperArgs:
    def _args(self, **kwargs):
        defaults = dict(verbose=False, dry_run=False, areas=None)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_pois_always_empty(self):
        args = self._args(verbose=True, dry_run=True, areas=["Kawaguchi"])
        assert build_scraper_args("POIs", args) == []

    def test_verbose_flag(self):
        args = self._args(verbose=True)
        result = build_scraper_args("UR", args)
        assert "--verbose" in result

    def test_dry_run_and_areas(self):
        args = self._args(dry_run=True, areas=["Kawaguchi"])
        result = build_scraper_args("SUUMO", args)
        assert "--dry-run" in result
        assert "--areas" in result
        assert "Kawaguchi" in result

    def test_all_flags_combined(self):
        args = self._args(verbose=True, dry_run=True, areas=["A", "B"])
        result = build_scraper_args("UR", args)
        assert result == ["--verbose", "--dry-run", "--areas", "A", "B"]


# ---------------------------------------------------------------------------
# run_scraper
# ---------------------------------------------------------------------------

class TestRunScraper:
    @patch("run_all.subprocess.run")
    def test_successful_run(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OK", stderr="",
        )
        scraper = {"name": "UR", "cmd": ["python", "ur.py"]}
        result = run_scraper(scraper, [])

        assert result["returncode"] == 0
        assert isinstance(result["elapsed"], float)

    @patch("run_all.subprocess.run")
    def test_failed_run(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error",
        )
        scraper = {"name": "UR", "cmd": ["python", "ur.py"]}
        result = run_scraper(scraper, [])

        assert result["returncode"] == 1

    @patch("run_all.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=600)
        scraper = {"name": "UR", "cmd": ["python", "ur.py"]}
        result = run_scraper(scraper, [])

        assert result["returncode"] == -1
        assert "TIMEOUT" in result["stderr"]
