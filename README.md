## Deployment Instructions

To deploy the Triage Desk application to a Linux server:

1.  **Clone the repository** to `/home/ubuntu/triage-desk`.
2.  **Set up the virtual environment**:
    ```bash
    python3 -m venv .venv
    ./.venv/bin/pip install fastapi uvicorn httpx pytest
    ```
3.  **Configure Secrets**: Create a file at `/home/ubuntu/triage-desk/.env` with the following content:
    ```
    OLLAMA_API_KEY=your_actual_api_key_here
    ```
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
