import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
from .db import get_db_connection

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database schema on startup
    from .db import init_db
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

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
        "model_name": TRIAGE_MODEL
    }

@app.get("/api/messages")
async def get_messages():
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT m.id, m.subject, d.category, d.priority, d.confidence, d.queue
            FROM messages m
            JOIN decisions d ON m.id = d.message_id
        """)
        return [dict(row) for row in cursor.fetchall()]

@app.get("/api/messages/{message_id}")
async def get_message_detail(message_id: str):
    with get_db_connection() as conn:
        # Message and decision
        row = conn.execute("""
            SELECT m.*, d.category, d.priority, d.confidence, d.reason, d.source, d.model, d.decided_at, d.queue
            FROM messages m
            JOIN decisions d ON m.id = d.message_id
            WHERE m.id = ?
        """, (message_id,)).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Audit trail
        audit_rows = conn.execute("""
            SELECT id, action, detail, at 
            FROM audit 
            WHERE message_id = ? 
            ORDER BY at ASC
        """, (message_id,)).fetchall()
        
        res = dict(row)
        res["audit"] = [dict(a) for a in audit_rows]
        return res

@app.get("/")
async def root():
    return FileResponse("app/static/board.html")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
