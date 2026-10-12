import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db_connection
from scripts.run_feed import run_feed
from unittest.mock import patch

client = TestClient(app)

@pytest.fixture
def empty_db(tmp_path):
    db_path = tmp_path / "empty_triage.db"
    os.environ["DB_PATH"] = str(db_path)
    return db_path

def test_app_creates_schema_on_startup(empty_db):
    # We use a context manager to ensure lifespan is triggered
    with client:
        client.get("/")
        with get_db_connection() as conn:
            res = conn.execute("SELECT count(*) FROM messages").fetchone()
            assert res[0] == 0

def test_run_feed_creates_schema(empty_db):
    with patch("app.classify.call_llm") as mock_llm:
        mock_llm.return_value = {
            "category": "support",
            "priority": "normal",
            "confidence": 0.9,
            "reason": "Mocked"
        }
        run_feed()
        with get_db_connection() as conn:
            res = conn.execute("SELECT count(*) FROM messages").fetchone()
            assert res[0] == 30
