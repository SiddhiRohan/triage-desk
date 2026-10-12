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
