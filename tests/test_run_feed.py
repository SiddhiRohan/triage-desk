import pytest
import json
import os
from unittest.mock import patch, MagicMock
from app.db import init_db, get_db_connection
from scripts.run_feed import run_feed
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_triage.db"
    os.environ["DB_PATH"] = str(db_path)
    init_db()
    yield
    if db_path.exists():
        os.remove(db_path)

def test_run_feed_idempotency_and_inserts():
    # Mock LLM classifier to return constant a a simple result
    with patch("app.classify.call_llm") as mock_llm:
        mock_llm.return_value = {
            "category": "support",
            "priority": "normal",
            "confidence": 0.9,
            "reason": "Mocked reason"
        }
        
        # Run feed once
        run_feed()
        
        # Verify 30 messages and 30 decisions
        with get_db_connection() as conn:
            msg_count = conn.execute("SELECT count(*) FROM messages").fetchone()[0]
            dec_count = conn.execute("SELECT count(*) FROM decisions").fetchone()[0]
            assert msg_count == 30
            assert dec_count == 30
        
        # Verify API returns 30 items
        response = client.get("/api/messages")
        assert response.status_code == 200
        assert len(response.json()) == 30
        
        # Run feed a second time (idempotency check)
        run_feed()
        
        with get_db_connection() as conn:
            msg_count_2 = conn.execute("SELECT count(*) FROM messages").fetchone()[0]
            dec_count_2 = conn.execute("SELECT count(*) FROM decisions").fetchone()[0]
            assert msg_count_2 == 30
            assert dec_count_2 == 30
