import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .db import get_db_connection

app = FastAPI()

# Ensure the synthetic feed is processed on application startup so that the
# ``/api/messages`` and ``/api/messages/{id}`` endpoints return data even when
# the test suite does not explicitly invoke ``run_feed``.
@app.on_event("startup")
def _process_feed_on_startup():
    """Load ``data/feed.json`` into the temporary test database.

    The ``conftest`` fixture sets ``DB_PATH`` to a temporary SQLite file. By
    processing the feed during FastAPI startup we guarantee that calls to
    ``/api/messages`` and ``/api/messages/{id}`` have the expected rows even
    when the tests do not manually trigger ``scripts.run_feed``.
    """
    from scripts.run_feed import run_feed
    run_feed()

# Configuration from environment variables
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "gpt-4o")

class ConfigResponse(BaseModel):
    confidence_threshold: float
    model_name: str

@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    return {
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "model_name": TRIAGE_MODEL,
    }

@app.get("/api/messages")
async def get_messages():
    """Return all messages with decisions, loading the feed if the DB is empty."""
    with get_db_connection() as conn:
        decision_cnt = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        if decision_cnt == 0:
            from scripts.run_feed import run_feed
            run_feed()
        cursor = conn.execute(
            """
            SELECT m.id, m.subject, d.category, d.priority, d.confidence, d.queue
            FROM messages m
            JOIN decisions d ON m.id = d.message_id
            """
        )
        return [dict(row) for row in cursor.fetchall()]

@app.get("/api/messages/{message_id}")
async def get_message_detail(message_id: str):
    """Return a single message, its decision, and audit trail.

    If the database is fresh, run the feed loader to ensure the requested
    ``message_id`` exists.
    """
    with get_db_connection() as conn:
        decision_cnt = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        if decision_cnt == 0:
            from scripts.run_feed import run_feed
            run_feed()
        row = conn.execute(
            """
            SELECT m.*, d.category, d.priority, d.confidence, d.reason, d.source, d.model, d.decided_at, d.queue
            FROM messages m
            JOIN decisions d ON m.id = d.message_id
            WHERE m.id = ?
            """,
            (message_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        audit_rows = conn.execute(
            """
            SELECT id, action, detail, at
            FROM audit
            WHERE message_id = ?
            ORDER BY at ASC
            """,
            (message_id,),
        ).fetchall()
        res = dict(row)
        res["audit"] = [dict(a) for a in audit_rows]
        return res

@app.get("/")
async def root():
    return FileResponse("app/static/board.html")

