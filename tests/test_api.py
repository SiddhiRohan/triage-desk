import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

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
