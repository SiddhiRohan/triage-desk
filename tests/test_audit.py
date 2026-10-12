import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db, get_db_connection
from app.classify import classify_message
import os
import sqlite3
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    # Use a test database
    os.environ["DB_PATH"] = "data/test_triage.db"
    init_db()
    yield
    if os.path.exists("data/test_triage.db"):
        os.remove("data/test_triage.db")

def test_config_endpoint():
    os.environ["CONFIDENCE_THRESHOLD"] = "0.85"
    os.environ["TRIAGE_MODEL"] = "test-model"
    
    import app.main
    app.main.CONFIDENCE_THRESHOLD = 0.85
    app.main.TRIAGE_MODEL = "test-model"
    
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["confidence_threshold"] == 0.85
    assert data["model_name"] == "test-model"

def test_audit_trail():
    # Setup: Create a message, decision, and audit logs
    with get_db_connection() as conn:
        conn.execute("DELETE FROM audit WHERE message_id = ?", ("msg-123",))
        conn.execute("INSERT OR REPLACE INTO messages (id, subject, body, sender_name, received_at) VALUES (?, ?, ?, ?, ?)", 
                     ("msg-123", "Audit Test", "Test body", "Tester", "2026-10-12T00:00:00Z"))
        conn.execute("INSERT OR REPLACE INTO decisions (message_id, category, priority, confidence, reason, queue, source, model, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                     ("msg-123", "support", "normal", 0.9, "Test reason", "Support", "llm", "gpt-4o", "2026-10-12T00:01:00Z"))
        conn.execute("INSERT INTO audit (message_id, action, detail, at) VALUES (?, ?, ?, ?)", 
                     ("msg-123", "classify", "Routed to Support", "2026-10-12T00:01:00Z"))
        conn.execute("INSERT INTO audit (message_id, action, detail, at) VALUES (?, ?, ?, ?)", 
                     ("msg-123", "review", "Marked as resolved", "2026-10-12T00:05:00Z"))
        conn.commit()

    response = client.get("/api/messages/msg-123")
    assert response.status_code == 200
    data = response.json()
    
    assert "audit" in data
    assert len(data["audit"]) == 2
    assert data["audit"][0]["action"] == "classify"
    assert data["audit"][1]["action"] == "review"
    assert data["audit"][0]["detail"] == "Routed to Support"

def test_classifier_creates_audit_row():
    # Setup: Create a message in DB
    with get_db_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO messages (id, subject, body, sender_name, received_at) VALUES (?, ?, ?, ?, ?)", 
                     ("msg-audit-test", "Audit Check", "Body", "User", "2026-10-12T00:00:00Z"))
        conn.commit()

    # Mock LLM call to avoid network
    with patch("app.classify.call_llm") as mock_llm:
        mock_llm.return_value = {
            "category": "support",
            "priority": "normal",
            "confidence": 0.9,
            "reason": "Mocked reason"
        }
        
        classify_message("msg-audit-test", "Audit Check", "Body")

    # Verify audit row was created
    with get_db_connection() as conn:
        audit_row = conn.execute("SELECT * FROM audit WHERE message_id = ?", ("msg-audit-test",)).fetchone()
        assert audit_row is not None
        assert audit_row["action"] == "classify"
        assert "Routed to Support" in audit_row["detail"]
