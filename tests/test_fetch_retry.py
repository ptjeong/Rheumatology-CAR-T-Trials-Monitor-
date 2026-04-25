"""Tests for the CT.gov fetch retry shim.

Run with:  python -m pytest tests/test_fetch_retry.py -v

Stubs out requests.get; never hits the live API. Covers:
  - Transient 503 → retried, eventually succeeds
  - Transient ConnectionError → retried, eventually succeeds
  - Persistent 500 → exhausts retries, raises HTTPError
  - 4xx → no retry, returns immediately
  - Backoff sleeps are short-circuited so the suite stays fast
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline  # noqa: E402


def _resp(status: int, body: str = "") -> MagicMock:
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.text = body
    r.json = MagicMock(return_value={"studies": []})
    return r


def test_transient_5xx_retried_then_succeeds(monkeypatch):
    calls = {"n": 0}
    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return _resp(503, "Service Unavailable")
        return _resp(200, "")

    with patch("pipeline.requests.get", side_effect=fake_get), \
         patch("pipeline.time.sleep") as fake_sleep:
        resp = pipeline._request_with_retry("https://example.test/x", {})

    assert resp.status_code == 200
    assert calls["n"] == 3
    # Slept twice (between attempts 1→2 and 2→3); not after the success.
    assert fake_sleep.call_count == 2


def test_connection_error_retried_then_succeeds():
    calls = {"n": 0}
    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("dns failed")
        return _resp(200, "")

    with patch("pipeline.requests.get", side_effect=fake_get), \
         patch("pipeline.time.sleep"):
        resp = pipeline._request_with_retry("https://example.test/x", {})

    assert resp.status_code == 200
    assert calls["n"] == 2


def test_persistent_5xx_exhausts_retries_and_raises():
    with patch("pipeline.requests.get",
               side_effect=lambda url, params=None, timeout=None: _resp(500, "boom")), \
         patch("pipeline.time.sleep"):
        with pytest.raises(requests.HTTPError, match="500"):
            pipeline._request_with_retry("https://example.test/x", {})


def test_4xx_returns_immediately_without_retry():
    """4xx is a client error — retries don't help. Returned, not raised; the
    fetch_raw_trials caller decides whether to surface it."""
    calls = {"n": 0}
    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return _resp(404, "Not Found")

    with patch("pipeline.requests.get", side_effect=fake_get), \
         patch("pipeline.time.sleep") as fake_sleep:
        resp = pipeline._request_with_retry("https://example.test/x", {})

    assert resp.status_code == 404
    assert calls["n"] == 1
    assert fake_sleep.call_count == 0


def test_fetch_raw_trials_surfaces_partial_context_on_total_failure():
    """If fetch fails after retries mid-pagination, the error message should
    include how many studies were collected so the operator knows the
    blast radius."""
    with patch("pipeline.requests.get",
               side_effect=lambda url, params=None, timeout=None: _resp(500, "boom")), \
         patch("pipeline.time.sleep"):
        with pytest.raises(requests.HTTPError, match="cumulative studies"):
            pipeline.fetch_raw_trials(max_records=10)
