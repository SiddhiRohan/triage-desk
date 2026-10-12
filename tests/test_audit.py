import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db, get_db_connection
import os
import sqlite3

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
    
    # Note: app config is loaded at import. For tests we might need to 
    # reload the app or set env vars before import. 
    # Since they are global in main.py, we can't easily change them 
    # without restarting the process or patching.
    # But the issue asks for the endpoint to return these values.
    
    # To test this properly without restarting, we patch the values in main.
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
        conn.execute("INSERT INTO messages (id, subject, body, sender_name, received_at) VALUES (?, ?, ?, ?, ?)", 
                     ("msg-123", "Audit Test", "Test body", "Tester", "2026-10-12T00:00:00Z"))
        conn.execute("INSERT INTO decisions (message_id, category, priority, confidence, reason, queue, source, model, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
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
