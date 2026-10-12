import pytest
import os
from unittest.mock import patch, MagicMock
from app.classify import classify_message, call_llm
import json
import httpx

@patch("app.classify.get_db_connection")
def test_classify_llm_success(mock_db):
    # Mock DB connection
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn

    # Mock LLM response
    mock_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "category": "support",
                    "priority": "normal",
                    "confidence": 0.9,
                    "reason": "Clearly asking for support"
                })
            }
        }]
    }
    
    with patch("httpx.Client.post", return_value=MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)):
        res = classify_message("msg-1", "Help", "I need help")
        assert res["category"] == "support"
        assert res["confidence"] == 0.9

@patch("app.classify.get_db_connection")
def test_classify_llm_parse_error_retry_success(mock_db):
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn

    # First response is invalid JSON, second is valid
    responses = [
        MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"content": "invalid"}}]}, raise_for_status=lambda: None),
        MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"content": json.dumps({
            "category": "billing",
            "priority": "high",
            "confidence": 0.8,
            "reason": "Billing issue"
        })}}]}, raise_for_status=lambda: None)
    ]
    
    with patch("httpx.Client.post", side_effect=responses):
        res = classify_message("msg-2", "Bill", "Payment failed")
        assert res["category"] == "billing"

@patch("app.classify.get_db_connection")
def test_classify_fallback_on_network_error(mock_db):
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn

    # Mock network error
    with patch("httpx.Client.post", side_effect=httpx.RequestError("Connection failed")):
        res = classify_message("msg-3", "Crash", "It crashed")
        # Should fall back to rules.py (bug category for 'crash')
        assert res["category"] == "bug"
        assert res["confidence"] <= 0.5

@patch("app.classify.get_db_connection")
def test_classify_fallback_on_double_parse_failure(mock_db):
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn

    # Both attempts return invalid JSON
    mock_resp = MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"content": "bad"}}]}, raise_for_status=lambda: None)
    
    with patch("httpx.Client.post", return_value=mock_resp):
        res = classify_message("msg-4", "Hello", "Vague message")
        # Should fall back to rules.py (other category)
        assert res["category"] == "other"
        assert res["confidence"] <= 0.5


@patch("httpx.Client.post")
def test_classify_uses_custom_endpoint(mock_post):
    # Set env var for custom URL
    os.environ["TRIAGE_API_URL"] = "https://custom.example.com/v1/chat/completions"
    # Also need to set API key to avoid errors; we can set dummy
    os.environ["TRIAGE_API_KEY"] = "dummy"
    # Mock DB connection
    with patch("app.classify.get_db_connection") as mock_db:
        mock_conn = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"content": '{"category":"support","priority":"normal","confidence":0.9,"reason":"test"}'}}]}, raise_for_status=lambda: None)
        res = classify_message("msg-test", "Test", "Body")
        # Verify that the post was called with the custom URL
        args, kwargs = mock_post.call_args
        assert args[0] == "https://custom.example.com/v1/chat/completions"
        # Also verify that we got a successful classification
        assert res["category"] == "support"
