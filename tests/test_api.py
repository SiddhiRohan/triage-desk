import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db
from unittest.mock import patch, MagicMock
import httpx

# Create a test client that will be used in tests that don't need to mock
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_api_config():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "confidence_threshold" in data
    assert "model_name" in data

def test_api_messages_list():
    # Note: depends on data/triage.db having data.
    # In a real CI, we would seed a test DB.
    res = client.get("/api/messages")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_api_message_detail():
    res = client.get("/api/messages/nonexistent")
    assert res.status_code == 404
    try:
        res.json()
    except Exception:
        pass

def test_root_serves_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]

def test_intake_valid_request():
    # Patch the classify_message function in the main module where it is used
    with patch('app.main.classify_message') as mock_classify:
        mock_classify.return_value = {
            "category": "support",
            "priority": "normal",
            "confidence": 0.9,
            "reason": "test reason",
            "queue": "Support",
            "source": "llm",
            "model": "gpt-oss:20b",
            "decided_at": "2023-01-01T00:00:00Z"
        }
        # Create a test client inside the patch to ensure the mock is used
        from fastapi.testclient import TestClient
        from app.main import app
        test_client = TestClient(app)
        res = test_client.post(
            "/api/intake",
            json={
                "subject": "Test subject",
                "body": "Test body",
                "sender_name": "Test Sender"
            }
        )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["id"].startswith("live-")
        assert data["category"] == "support"
        assert data["priority"] == "normal"
        assert data["confidence"] == 0.9
        assert data["reason"] == "test reason"
        assert data["queue"] == "Support"
        assert data["source"] == "llm"
        assert data["model"] == "gpt-oss:20b"
        assert data["decided_at"] == "2023-01-01T00:00:00Z"

def test_intake_missing_subject():
    res = client.post(
        "/api/intake",
        json={
            "body": "Test body",
            "sender_name": "Test Sender"
        }
    )
    assert res.status_code == 422

def test_intake_missing_body():
    res = client.post(
        "/api/intake",
        json={
            "subject": "Test subject",
            "sender_name": "Test Sender"
        }
    )
    assert res.status_code == 422

def test_intake_low_confidence_results_in_needs_human():
    # Mock the call_llm function to raise an exception to trigger fallback to rules
    with patch('app.classify.call_llm') as mock_call_llm:
        mock_call_llm.side_effect = httpx.RequestError("Network error")
        # Create a test client inside the patch
        from fastapi.testclient import TestClient
        from app.main import app
        test_client = TestClient(app)
        res = test_client.post(
            "/api/intake",
            json={
                "subject": "Vague message",
                "body": "This is vague",
                "sender_name": "Test Sender"
            }
        )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["id"].startswith("live-")
        # The rule-based classifier returns confidence <= 0.5, so queue should be Needs human
        assert data["queue"] == "Needs human"
        assert data["source"] == "rules"
        assert data["model"] is None
