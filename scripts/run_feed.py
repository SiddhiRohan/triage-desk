import json
import os
from app.db import get_db_connection

def run_feed():
    feed_path = "data/feed.json"
    if not os.path.exists(feed_path):
        print(f"Feed file not found at {feed_path}")
        return

    with open(feed_path, "r") as f:
        messages = json.load(f)

    from app.classify import classify_message

    for msg in messages:
        msg_id = msg["id"]

        # Insert the raw message into the ``messages`` table if not present.
        # This guarantees the ``GET /api/messages`` endpoint can join on it.
        with get_db_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO messages (id, subject, body, sender_name, received_at) VALUES (?,?,?,?,?)",
                (msg_id, msg.get("subject"), msg.get("body"), msg.get("sender_name"), msg.get("received_at")),
            )
            conn.commit()

        # Idempotency check: skip if a decision already exists for this message.
        with get_db_connection() as conn:
            exists = conn.execute("SELECT 1 FROM decisions WHERE message_id = ?", (msg_id,)).fetchone()
            if exists:
                print(f"Skipping {msg_id}: already decided")
                continue

        print(f"Classifying {msg_id}...")
        classify_message(msg_id, msg["subject"], msg["body"])

    print("Feed processing complete.")

if __name__ == "__main__":
    run_feed()
