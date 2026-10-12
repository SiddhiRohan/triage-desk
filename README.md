## Deployment Instructions

To deploy the Triage Desk application to a Linux server:

1.  **Clone the repository** to `/home/ubuntu/triage-desk`.
2.  **Set up the virtual environment**:
    ```bash
    python3 -m venv .venv
    ./.venv/bin/pip install fastapi uvicorn httpx pytest
    ```
3.  **Configure Environment Variables**: Create a file at `/home/ubuntu/triage-desk/.env` with the following content:
    ```
    TRIAGE_API_URL=https://ollama.com/v1/chat/completions
    TRIAGE_API_KEY=your_actual_api_key_here
    ```
    The classifier will use `TRIAGE_API_KEY` for authentication, falling back to `OLLAMA_API_KEY` if set. The `TRIAGE_API_URL` defaults to the Ollama OpenAI-compatible endpoint.
4.  **Run the deployment script**:
    ```bash
    sudo ./scripts/deploy.sh
    ```
    This script will:
    - Install Caddy as a reverse proxy.
    - Set up the `triage.service` systemd unit to run the FastAPI app via Uvicorn.
    - Set up the `triage-feed.service` to process the synthetic feed on boot.
    - Configure Caddy to route traffic from port 80 to the app on port 8000.

5.  **Configuration**: Other environment variables are set in the systemd unit files.

## Live Intake Endpoint

The application provides a POST endpoint to submit a live message for triage.

**Endpoint**: `POST /api/intake`

**Request Body**:
```json
{
  "subject": "string",
  "body": "string",
  "sender_name": "string"
}
```

**Response** (HTTP 201):
```json
{
  "id": "message-id",
  "category": "category",
  "priority": "priority",
  "confidence": 0.0-1.0,
  "reason": "reason",
  "queue": "queue",
  "source": "llm or rules",
  "model": "model-name or null",
  "decided_at": "timestamp"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Help with login",
    "body": "I cannot log into my account.",
    "sender_name": "John Doe"
  }'
```

The message will be stored, classified, and appear on the board in the appropriate queue.
