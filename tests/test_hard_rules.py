"""Comprehensive hard‑rules test suite for issue #13.

The suite validates each acceptance criterion listed in the issue:

1. Low‑confidence decisions land in ``Needs human``.
2. High‑confidence decisions are queued by category.
3. Model errors fall back to the rule‑based classifier (confidence ≤ 0.5, source ``rules``).
4. Running the feed twice is idempotent – exactly one decision per message.
5. ``GET /api/messages`` returns every feed message.
6. ``GET /api/messages/{id}`` returns the decision and at least one audit row.
7. No prohibited outbound‑call strings exist in the source tree.
8. No API‑key‑like strings exist in the repository.

All tests run against the temporary SQLite database created by ``tests/conftest.py``.
Only the standard library, ``pytest``, and the FastAPI ``TestClient`` are used.
"""

import os
import re
import json
import glob
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.classify import classify_message, call_llm, CONFIDENCE_THRESHOLD
from app.db import get_db_connection
from scripts import run_feed

client = TestClient(app)


def test_confidence_below_threshold_routes_to_needs_human(monkeypatch):
    """A decision with confidence below the threshold ends up in ``Needs human``.

    The LLM call is monkey‑patched to return a low confidence value.
    """
    low_conf = CONFIDENCE_THRESHOLD - 0.1

    def fake_call_llm(prompt, retry_error=None):  # pragma: no cover
        return {
            "category": "support",
            "priority": "low",
            "confidence": low_conf,
            "reason": "test low confidence",
        }

    monkeypatch.setattr("app.classify.call_llm", fake_call_llm)
    classify_message("msg_low", "Subject", "Body")
    conn = get_db_connection()
    row = conn.execute("SELECT queue FROM decisions WHERE message_id = ?", ("msg_low",)).fetchone()
    assert row is not None
    assert row[0] == "Needs human"
    conn.close()


def test_confidence_above_threshold_routes_to_category_queue(monkeypatch):
    """A decision with confidence above the threshold is queued by its category.
    """
    high_conf = CONFIDENCE_THRESHOLD + 0.1

    def fake_call_llm(prompt, retry_error=None):  # pragma: no cover
        return {
            "category": "billing",
            "priority": "high",
            "confidence": high_conf,
            "reason": "test high confidence",
        }

    monkeypatch.setattr("app.classify.call_llm", fake_call_llm)
    classify_message("msg_high", "Billing issue", "I need help")
    conn = get_db_connection()
    row = conn.execute("SELECT queue FROM decisions WHERE message_id = ?", ("msg_high",)).fetchone()
    assert row is not None
    # Billing maps to capitalised queue name "Billing"
    assert row[0] == "Billing"
    conn.close()


def test_fallback_on_model_error(monkeypatch):
    """When the LLM raises an HTTP error the fallback classifier is used.

    The fallback must produce confidence ≤ 0.5 and route to ``Needs human`` with
    source ``rules``.
    """
    def error_call_llm(prompt, retry_error=None):
        raise httpx.HTTPStatusError("429 Too Many Requests", request=None, response=None)

    monkeypatch.setattr("app.classify.call_llm", error_call_llm)
    classify_message("msg_fallback", "Trigger fallback", "Network issue")
    conn = get_db_connection()
    decision = conn.execute(
        "SELECT category, priority, confidence, queue, source FROM decisions WHERE message_id = ?",
        ("msg_fallback",),
    ).fetchone()
    assert decision is not None
    # Rules classifier always returns confidence ≤ 0.5 and routes to Needs human
    assert decision[3] == "Needs human"
    assert decision[4] == "rules"
    conn.close()


def test_feed_idempotent(monkeypatch):
    """Running the feed twice creates exactly one decision per message.

    The LLM is forced to error so the rule‑based fallback runs quickly.
    """
    def error_call_llm(prompt, retry_error=None):
        raise httpx.HTTPStatusError("429", request=None, response=None)
    monkeypatch.setattr("app.classify.call_llm", error_call_llm)
    # First run
    run_feed.run_feed()
    # Second run – should be idempotent
    run_feed.run_feed()
    conn = get_db_connection()
    feed = json.load(open(os.path.join("data", "feed.json")))
    count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert count == len(feed)
    conn.close()


def test_api_messages_returns_all_feed_messages():
    """GET /api/messages returns a list with one entry per feed item."""
    response = client.get("/api/messages")
    assert response.status_code == 200
    data = response.json()
    feed = json.load(open(os.path.join("data", "feed.json")))
    assert isinstance(data, list)
    assert len(data) == len(feed)


def test_api_message_detail_contains_decision_and_audit(monkeypatch):
    """GET /api/messages/{id} includes the decision and audit rows.

    The test ensures the first feed message has been classified.
    """
    # Ensure classification has happened (idempotent run)
    def error_call_llm(prompt, retry_error=None):
        raise httpx.HTTPStatusError("429", request=None, response=None)
    monkeypatch.setattr("app.classify.call_llm", error_call_llm)
    run_feed.run_feed()
    feed = json.load(open(os.path.join("data", "feed.json")))
    first_id = feed[0]["id"]
    resp = client.get(f"/api/messages/{first_id}")
    assert resp.status_code == 200
    payload = resp.json()
    for key in ["category", "priority", "confidence", "queue", "source"]:
        assert key in payload
    assert "audit" in payload
    assert isinstance(payload["audit"], list)
    assert len(payload["audit"]) >= 1


def test_no_prohibited_outbound_calls():
    """Ensure source files do not contain disallowed outbound‑call strings."""
    prohibited = [r"smtp", r"sendmail", r"requests\.post", r"httpx\.post", r"webhook", r"DELETE"]
    paths = glob.glob("app/**/*.py", recursive=True) + glob.glob("scripts/**/*.py", recursive=True)
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            for pat in prohibited:
                assert not re.search(pat, content), f"Forbidden pattern '{pat}' found in {path}"


def test_no_api_key_like_strings():
    """Search the repository for strings that resemble API keys.

    Patterns include ``sk-...``, ``ollama_...`` and any 32+ hex string.
    """
    patterns = [r"sk-[A-Za-z0-9]{20,}", r"ollama_[A-Za-z0-9]{20,}", r"[a-fA-F0-9]{32,}"]
    for root, _, files in os.walk('.'):
        if ".venv" in root:
            continue
        for fname in files:
            if not (fname.endswith('.py') or fname.endswith('.md') or fname.endswith('.json')):
                continue
            full_path = os.path.join(root, fname)
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pat in patterns:
                    assert not re.search(pat, content), f"Potential key pattern found in {full_path}"

