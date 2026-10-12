import sqlite3
import os

def get_db_connection():
    # Read DB_PATH at connection time to allow test overrides via env var
    db_path = os.getenv("DB_PATH", "data/triage.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                subject TEXT,
                body TEXT,
                sender_name TEXT,
                received_at TEXT
            )
        """)
        # Decisions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                message_id TEXT PRIMARY KEY,
                category TEXT,
                priority TEXT,
                confidence REAL,
                reason TEXT,
                queue TEXT,
                source TEXT,
                model TEXT,
                decided_at TEXT,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )
        """)
        # Audit table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                action TEXT,
                detail TEXT,
                at TEXT,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )
        """)
        conn.commit()
