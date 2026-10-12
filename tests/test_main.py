from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_app_startup():
    response = client.get("/")
    assert response.status_code == 200
    assert "Triage Desk" in response.text

def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "confidence_threshold" in data
    assert "model_name" in data
    assert isinstance(data["confidence_threshold"], float)
    assert isinstance(data["model_name"], str)

def test_static_board_js():
    response = client.get("/static/board.js")
    assert response.status_code == 200
    assert len(response.content) > 0

def test_root_contains_board_js():
    response = client.get("/")
    assert response.status_code == 200
    assert "board.js" in response.text
