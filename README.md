# Triage Desk

An intake router built by a team of five AI agents (OpenClaw and Hermes Agent) for Confer's take-home. Messages come in, each gets a category, priority, confidence and a one-line reason from a model, and lands in a queue on a public board. Anything under the confidence threshold goes to "Needs human" and nothing is ever sent, closed or deleted.

- Live board: http://18.217.125.82
- **[DELIVERY.md](DELIVERY.md)**: the agent roster, how a ticket moves, what each agent did, what broke, the token and model report, trace excerpts, how to reproduce. Start there.
- `agents/`: the role files, runtime configs (secrets removed) and the script that runs one ticket through the team.
- `infra/`: Terraform for the VM (AWS; the Oracle attempt is kept too) and the install script.
- `logs/`: every orchestrator, builder and reviewer run, by ticket.
- `docs/`: the plan the orchestrator worked from, provider history, screenshots.

The agents wrote the code under `app/`, `scripts/`, `tests/`, `data/` and `deployment/`; `git log` shows the author of every commit. The deployment notes below were written by builder-core as part of ticket 8.

## Deployment Instructions

To deploy the Triage Desk application to a Linux server:

1.  **Clone the repository** to `/home/ubuntu/triage-desk`.
2.  **Set up the virtual environment**:
    ```bash
    python3 -m venv .venv
    ./.venv/bin/pip install fastapi uvicorn httpx pytest
    ```
3.  **Configure Environment Variables**: Create a file at `/home/ubuntu/triage-desk/.env` with the following content (TRIAGE_MODEL defaults to gpt-oss:20b if not set):
    ```
    TRIAGE_API_URL=https://ollama.com/v1/chat/completions
    TRIAGE_API_KEY=your_actual_api_key_here
TRIAGE_MODEL=gpt-oss:20b
    ```
    The classifier will use `TRIAGE_API_KEY` for authentication, falling back to `OLLAMA_API_KEY` if set. The `TRIAGE_API_URL` defaults to the Ollama OpenAI-compatible endpoint.
4.  **Run the deployment script**:
    ```bash
    sudo ./scripts/deploy.sh
    ```
    This script will:
    - Install Caddy as a reverse proxy.
    - Set up the `triage.service` systemd unit to run the FastAPI app via Uvicorn.
3.  **Configure Environment Variables**: Create a file at `/home/ubuntu/triage-desk/.env` with the following content (TRIAGE_MODEL defaults to gpt-oss:20b if not set):
```
TRIAGE_API_URL=https://ollama.com/v1/chat/completions
TRIAGE_API_KEY=your_actual_api_key_here
TRIAGE_MODEL=gpt-oss:20b
```

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
