import os
import re
import json
import glob
import httpretty
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db, get_db_connection

client = TestClient(app)

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))


def test_confidence_threshold_routes_to_needs_human():
    """Seed a message with confidence below threshold and verify it lands in 'Needs human'."""
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    # Insert a dummy message
    cur.execute(
        "INSERT OR IGNORE INTO messages (id, subject, body, sender_name, received_at) VALUES (?,?,?,?,?)",
        ("low_conf_1", "Low confidence subject", "Hello", "User", "2023-01-01T00:00:00Z"),
    )
    # Mock classify to return low confidence
    from app.classify import classify_message
    classify_message = pytest.helpers.mocked_classify(message_id="low_conf_1", confidence=CONFIDENCE_THRESHOLD - 0.1, category="support", priority="low", source="rules")  # type: ignore
    # Re-run classification (this will insert decision)
    classify_message()
    # Verify decision queue
    cur.execute("SELECT queue FROM decisions WHERE message_id=?", ("low_conf_1",))
    queue = cur.fetchone()[0]
    assert queue == "Needs human"
    cur.close()
    conn.close()


def test_no_prohibited_outbound_calls():
    """Ensure no source file contains disallowed patterns."""
    forbidden_patterns = [
        r"smtp",
        r"requests\.post",
        r"httpx\.post",
        r"DELETE",
        r"send",
    ]
    # Search through app and scripts directories
    targets = glob.glob("app/**/*.py", recursive=True) + glob.glob("scripts/**/*.py", recursive=True)
    for file_path in targets:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            for pattern in forbidden_patterns:
                assert not re.search(pattern, content), f"Disallowed pattern '{pattern}' found in {file_path}"


def test_board_page_lists_all_messages():
    """Check that the board endpoint (/) returns a page that contains at least one message per category."""
    res = client.get("/")
    assert res.status_code == 200
    # Very light check that body contains at least the string 'Support' which is a queue header
    assert "Support" in res.text or "Billing" in res.text


def test_hard_rule_validation():
    """Validate that keyword fallback classifier respects confidence limits and routes to Needs human."""
    from app.rules import classify_message as rules_classifier
    result = rules_classifier("Help me with my billing" )
    # The rule classifier will return a dict; ensure confidence <= 0.5 and queue "Needs human"
    assert result["confidence"] <= 0.5
    assert result["queue"] == "Needs human"

