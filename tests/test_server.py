"""Tests for server.py — static file allowlist, API routes, scraper runner."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from server import _is_allowed_static, _run_single_scraper, app, scrape_lock, scrape_state


# ---------------------------------------------------------------------------
# _is_allowed_static
# ---------------------------------------------------------------------------

class TestIsAllowedStatic:
    def test_viewer_html(self):
        assert _is_allowed_static("viewer.html") is True

    def test_viewer_js(self):
        assert _is_allowed_static("viewer.js") is True

    def test_scoring_config_json(self):
        assert _is_allowed_static("scoring_config.json") is True

    def test_results_prefix_match(self):
        assert _is_allowed_static("results_suumo.json") is True

    def test_area_pois_prefix_match(self):
        assert _is_allowed_static("area_pois.json") is True

    def test_path_traversal_rejected(self):
        assert _is_allowed_static("../../etc/passwd") is False

    def test_arbitrary_json_rejected(self):
        assert _is_allowed_static("malicious.json") is False


# ---------------------------------------------------------------------------
# Flask API routes
# ---------------------------------------------------------------------------

class TestAPIRoutes:
    @pytest.fixture(autouse=True)
    def _setup_client(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        # Reset scrape state between tests
        with scrape_lock:
            scrape_state["running"] = False
            scrape_state["scrapers"] = {}

    def test_get_scrapers_returns_all_keys(self):
        resp = self.client.get("/api/scrapers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ur" in data
        assert "suumo" in data
        assert "pois" in data
        assert len(data) == 8

    def test_post_scrape_bad_origin_returns_403(self):
        resp = self.client.post(
            "/api/scrape",
            json={"scrapers": ["ur"]},
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_post_scrape_invalid_keys_returns_400(self):
        resp = self.client.post(
            "/api/scrape",
            json={"scrapers": ["nonexistent"]},
        )
        assert resp.status_code == 400

    def test_post_scrape_already_running_returns_409(self):
        with scrape_lock:
            scrape_state["running"] = True

        resp = self.client.post(
            "/api/scrape",
            json={"scrapers": ["ur"]},
        )
        assert resp.status_code == 409

    def test_get_scrape_status(self):
        resp = self.client.get("/api/scrape/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "running" in data
        assert "scrapers" in data

    def test_serve_static_blocked_file_returns_404(self):
        resp = self.client.get("/secret.json")
        assert resp.status_code == 404

    def test_serve_index(self):
        # May return 200 or 404 depending on whether viewer.html exists
        # in the test environment — we just verify the route is wired
        resp = self.client.get("/")
        assert resp.status_code in (200, 404)

    @patch("server._run_scrape_job")
    def test_post_scrape_success_starts_job(self, mock_job):
        resp = self.client.post(
            "/api/scrape",
            json={"scrapers": ["ur"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "started"
        assert "ur" in data["scrapers"]


# ---------------------------------------------------------------------------
# _run_single_scraper
# ---------------------------------------------------------------------------

class TestRunSingleScraper:
    @pytest.fixture(autouse=True)
    def _reset_state(self):
        with scrape_lock:
            scrape_state["running"] = True
            scrape_state["scrapers"] = {}

    @patch("server.subprocess.run")
    def test_successful_run_state_done(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        _run_single_scraper("ur")

        with scrape_lock:
            assert scrape_state["scrapers"]["ur"] == "done"

    @patch("server.subprocess.run")
    def test_timeout_state_failed(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=600)
        _run_single_scraper("ur")

        with scrape_lock:
            assert scrape_state["scrapers"]["ur"] == "failed"

    @patch("server.subprocess.run")
    def test_general_exception_state_failed(self, mock_run):
        mock_run.side_effect = OSError("permission denied")
        _run_single_scraper("ur")

        with scrape_lock:
            assert scrape_state["scrapers"]["ur"] == "failed"
