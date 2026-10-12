import pytest
import os

@pytest.fixture(autouse=True)
def db_path(tmp_path):
    # Create a temporary database path
    db_file = tmp_path / "test_triage.db"
    db_path_str = str(db_file)
    
    # Set the environment variable for the app to use
    os.environ["DB_PATH"] = db_path_str
    
    # Import init_db here to ensure it uses the updated DB_PATH
    from app.db import init_db
    init_db()
    
    return db_path_str

# Ensure the temporary test database is populated with synthetic feed data
# before each test suite runs. We monkey‑patch the LLM call to return a fixed
# high‑confidence decision so that the feed processing is deterministic and
# offline. We also manually insert the raw messages into the ``messages``
# table because ``scripts/run_feed.py`` only creates decisions.
@pytest.fixture(autouse=True)
def populate_feed():
    """Insert feed messages and deterministic decisions into the temporary DB.

    We avoid patching ``app.classify.call_llm`` so that other tests (which
    monkey‑patch the HTTP client to simulate LLM errors) see the real logic.
    Decisions are generated using the rule‑based classifier, which always
    returns a confidence ≤ 0.5 and therefore routes to ``Needs human``.
    """
    from app.db import get_db_connection
    from app.rules import rule_based_classify
    import json, os

    feed_path = os.path.join("data", "feed.json")
    with open(feed_path, "r") as f:
        feed = json.load(f)

    conn = get_db_connection()
    for msg in feed:
        # Insert message record
        conn.execute(
            "INSERT OR IGNORE INTO messages (id, subject, body, sender_name, received_at) VALUES (?,?,?,?,?)",
            (msg.get("id"), msg.get("subject"), msg.get("body"), msg.get("sender_name"), msg.get("received_at")),
        )
        # Generate a deterministic decision via rule‑based classifier
        cat, prio, conf, reason = rule_based_classify(f"{msg.get('subject')} {msg.get('body')}")
        queue = "Needs human" if conf <= 0.5 else (cat.capitalize() if cat != "other" else "General")
        # Insert decision
        conn.execute(
            "INSERT OR REPLACE INTO decisions (message_id, category, priority, confidence, reason, queue, source, model, decided_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                msg.get("id"),
                cat,
                prio,
                conf,
                reason,
                queue,
                "rules",
                os.getenv("TRIAGE_MODEL", "gpt-4o"),
                "2023-01-01T00:00:00Z",
            ),
        )
        # Insert a minimal audit row
        conn.execute(
            "INSERT INTO audit (message_id, action, detail, at) VALUES (?,?,?,?)",
            (msg.get("id"), "classify", f"Routed to {queue} via rules", "2023-01-01T00:00:00Z"),
        )
    conn.commit()
