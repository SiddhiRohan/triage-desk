import os
import json
import httpx
import datetime
from app.db import get_db_connection
from app.rules import rule_based_classify

# Configuration from environment variables
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "gpt-oss:20b")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))

def build_prompt(message_text: str):
    return (
        "You are a triage assistant. Classify the following message into one of these categories: "
        "support, billing, bug, sales, other. Also assign a priority: low, normal, high. "
        "Return a JSON object with keys: category, priority, confidence (0.0 to 1.0), and reason (one short sentence). "
        "Message: " + message_text
    )

def call_llm(prompt: str, retry_error: str = None):
    full_prompt = prompt
    if retry_error:
        full_prompt += f"\n\nYour previous response was invalid: {retry_error}. Please try again and return valid JSON."

    # Read env vars per call to allow runtime changes
    api_key = os.getenv("TRIAGE_API_KEY", os.getenv("OLLAMA_API_KEY", ""))
    api_url = os.getenv("TRIAGE_API_URL", "https://ollama.com/v1/chat/completions")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": TRIAGE_MODEL,
        "messages": [{"role": "user", "content": full_prompt}],
        "response_format": {"type": "json_object"}
    }

    # Use a short timeout to avoid hanging
    with httpx.Client(timeout=10.0) as client:
        response = client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)

def classify_message(message_id: str, subject: str, body: str):
    text = f"Subject: {subject}\nBody: {body}"
    prompt = build_prompt(text)
    
    try:
        # First attempt
        decision = call_llm(prompt)
        source = "llm"
    except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError, KeyError) as e:
        # Retry once if it was a parse error (JSONDecodeError or KeyError)
        if isinstance(e, (json.JSONDecodeError, KeyError)):
            try:
                decision = call_llm(prompt, retry_error=str(e))
                source = "llm"
            except Exception:
                decision = None
        else:
            decision = None

    # Fallback to rules on error, second parse failure, or specific HTTP codes (402, 429)
    # Note: httpx.HTTPStatusError handles non-2xx. We specifically check for 402/429 if needed, 
    # but any network/status error triggers fallback per spec.
    if decision is None:
        cat, prio, conf, reason = rule_based_classify(text)
        decision = {
            "category": cat,
            "priority": prio,
            "confidence": conf,
            "reason": reason
        }
        source = "rules"

    # Queue logic
    category = decision["category"]
    if decision["confidence"] < CONFIDENCE_THRESHOLD:
        queue = "Needs human"
    elif category == "other":
        queue = "General"
    else:
        queue = category.capitalize()

    # Save to DB
    model_value = TRIAGE_MODEL if source == "llm" else None
    decided_at = datetime.datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        # Decision table
        conn.execute(
            "INSERT OR REPLACE INTO decisions (message_id, category, priority, confidence, reason, queue, source, model, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (message_id, category, decision["priority"], decision["confidence"], decision["reason"], queue, source, model_value, decided_at)
        )
        # Audit table
        conn.execute(
            "INSERT INTO audit (message_id, action, detail, at) VALUES (?, ?, ?, ?)",
            (message_id, "classify", f"Routed to {queue} via {source}", decided_at)
        )
        conn.commit()

    # Return the full decision dict (including queue, source, model, decided_at)
    return {
        "category": decision["category"],
        "priority": decision["priority"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "queue": queue,
        "source": source,
        "model": model_value,
        "decided_at": decided_at
    }
