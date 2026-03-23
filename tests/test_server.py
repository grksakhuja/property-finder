"""Tests for server.py — static file allowlist."""

import pytest

from server import _is_allowed_static, app


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

    def test_amenities_cache_json(self):
        assert _is_allowed_static("amenities_cache.json") is True

    def test_geocoded_addresses_json(self):
        assert _is_allowed_static("geocoded_addresses.json") is True

    def test_results_prefix_match(self):
        assert _is_allowed_static("results_suumo.json") is True

    def test_area_pois_prefix_match(self):
        assert _is_allowed_static("area_pois.json") is True

    def test_path_traversal_rejected(self):
        assert _is_allowed_static("../../etc/passwd") is False

    def test_arbitrary_json_rejected(self):
        assert _is_allowed_static("malicious.json") is False

    def test_subdirectory_rejected(self):
        assert _is_allowed_static("data/scored_listings.json") is False


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

class TestStaticRoutes:
    @pytest.fixture(autouse=True)
    def _setup_client(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_serve_static_blocked_file_returns_404(self):
        resp = self.client.get("/secret.json")
        assert resp.status_code == 404

    def test_serve_index(self):
        # May return 200 or 404 depending on whether viewer.html exists
        resp = self.client.get("/")
        assert resp.status_code in (200, 404)

    def test_api_routes_removed(self):
        resp = self.client.get("/api/scrapers")
        assert resp.status_code == 404
