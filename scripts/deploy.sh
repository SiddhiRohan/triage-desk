#!/bin/bash
set -e

echo "Deploying Triage Desk..."

# Install Caddy if not present
if ! command -v caddy &> /dev/null; then
    echo "Installing Caddy..."
    sudo apt-get update
    sudo apt-get install -y debian-keyring
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update
    sudo apt-get install -y caddy
fi

# Setup systemd services
echo "Setting up systemd services..."
sudo cp deployment/triage.service /etc/systemd/system/
sudo cp deployment/triage-feed.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable triage.service
sudo systemctl start triage.service
sudo systemctl enable triage-feed.service

# Configure Caddy
echo "Configuring Caddy..."
sudo cp deployment/Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy

echo "Deployment complete. App should be available on port 80."
