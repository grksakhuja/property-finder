"""Tests for shared.http_client — session creation and fetch_page."""

import responses
import pytest

from shared.http_client import create_session, fetch_page


class TestCreateSession:
    def test_default_user_agent(self):
        session = create_session()
        assert "Mozilla" in session.headers["User-Agent"]

    def test_extra_headers_applied(self):
        session = create_session(extra_headers={"X-Custom": "test"})
        assert session.headers["X-Custom"] == "test"
        assert "Mozilla" in session.headers["User-Agent"]


class TestFetchPage:
    @responses.activate
    def test_simple_get(self):
        responses.add(responses.GET, "https://example.com/test", body="OK", status=200)
        session = create_session()
        resp = fetch_page(session, "https://example.com/test")
        assert resp.status_code == 200
        assert resp.text == "OK"

    @responses.activate
    def test_retry_on_500(self):
        responses.add(responses.GET, "https://example.com/fail", status=500)
        responses.add(responses.GET, "https://example.com/fail", status=500)
        responses.add(responses.GET, "https://example.com/fail", body="recovered", status=200)
        session = create_session(max_retries=3, backoff_factor=0)
        resp = fetch_page(session, "https://example.com/fail")
        assert resp.status_code == 200
        assert len(responses.calls) == 3

    @responses.activate
    def test_raises_on_persistent_failure(self):
        for _ in range(4):
            responses.add(responses.GET, "https://example.com/down", status=500)
        session = create_session(max_retries=3, backoff_factor=0)
        with pytest.raises(Exception):
            fetch_page(session, "https://example.com/down")

    @responses.activate
    def test_post_method(self):
        responses.add(responses.POST, "https://example.com/api", json={"ok": True}, status=200)
        session = create_session()
        resp = fetch_page(session, "https://example.com/api", method="POST", data={"key": "val"})
        assert resp.json() == {"ok": True}
