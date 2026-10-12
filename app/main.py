import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

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

@app.get("/")
async def root():
    return {"message": "Triage Desk API is running"}
