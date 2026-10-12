#!/usr/bin/env bash
# Sets up a fresh Ubuntu 24.04 box as the Triage Desk agent host and runs the app.
# Run as the ubuntu user after `terraform apply` in infra/aws:
#
#   export GH_TOKEN=...            # fine-grained token scoped to the repo (contents, issues, pull requests: write)
#   export NVIDIA_API_KEY=...      # build.nvidia.com, free, runs all five agents
#   export GROQ_API_KEY=...        # console.groq.com, free, runs the classifier
#   export OLLAMA_API_KEY=...      # optional. ollama.com free plan; what the build used until its monthly cap
#   export OPENROUTER_API_KEY=...  # optional. second fallback
#   bash infra/setup.sh
#
# Safe to re-run; it skips what is already there.
#
# Provider history, so the choices below make sense: the build ran on Ollama Cloud's free
# plan (gemma4:31b, gpt-oss:120b/20b, nemotron-3-super) until it hit the monthly cap at
# ticket 11, then on OpenRouter's free tier until the 50/day cap, then on NVIDIA's free
# API (same nemotron model) for the agents and Groq's free tier (gpt-oss-20b) for the
# classifier. No paid key anywhere. See docs/PROVIDERS.md.
set -euo pipefail

REPO="SiddhiRohan/triage-desk"
: "${GH_TOKEN:?set GH_TOKEN}"
: "${NVIDIA_API_KEY:?set NVIDIA_API_KEY}"
: "${GROQ_API_KEY:?set GROQ_API_KEY}"
OLLAMA_API_KEY="${OLLAMA_API_KEY:-}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

AGENT_MODEL="nvidia/nvidia/nemotron-3-super-120b-a12b"   # OpenClaw spelling: provider/model
HERMES_MODEL="nvidia/nemotron-3-super-120b-a12b"
NVIDIA_URL="https://integrate.api.nvidia.com/v1"

echo "== packages"
sudo apt-get update -q
sudo apt-get install -y -q build-essential git curl jq python3 python3-venv python3-pip sqlite3

echo "== gh (GitHub's apt repo; Ubuntu's 2.45 fails on label edits with a GraphQL deprecation)"
if ! gh --version 2>/dev/null | grep -qE "gh version (2\.(6[0-9]|[7-9][0-9]|1[0-9][0-9])|[3-9])"; then
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
  sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
  sudo apt-get update -q && sudo apt-get install -y -q gh
fi

echo "== caddy (serves the board on :80)"
if ! command -v caddy >/dev/null; then
  sudo apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -q && sudo apt-get install -y -q caddy
fi

echo "== keys into ~/.bashrc"
for k in GH_TOKEN NVIDIA_API_KEY GROQ_API_KEY OLLAMA_API_KEY OPENROUTER_API_KEY; do
  v="${!k}"
  [ -n "$v" ] || continue
  grep -q "export $k=" ~/.bashrc || echo "export $k=\"$v\"" >> ~/.bashrc
done

echo "== github"
# gh refuses --with-token while GH_TOKEN is exported, so hide it for this one call
env -u GH_TOKEN gh auth login --with-token <<< "$GH_TOKEN"
gh auth setup-git
sudo loginctl enable-linger "$USER"   # user services survive logout

echo "== my clone (orchestrator + reviewer run here, I merge here)"
[ -d ~/triage-desk ] || gh repo clone "$REPO" ~/triage-desk
git -C ~/triage-desk config user.name  "Siddhi Rohan Chakka"
git -C ~/triage-desk config user.email "siddhirohanwork@gmail.com"
[ -d ~/triage-desk/.venv ] || python3 -m venv ~/triage-desk/.venv
~/triage-desk/.venv/bin/pip install -q fastapi uvicorn httpx pytest zstandard

echo "== openclaw"
if ! command -v openclaw >/dev/null && [ ! -x "$HOME/.npm-global/bin/openclaw" ]; then
  curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard || curl -fsSL https://openclaw.ai/install.sh | bash
fi
export PATH="$HOME/.npm-global/bin:$PATH"
openclaw onboard --auth-choice nvidia-api-key --nvidia-api-key "$NVIDIA_API_KEY" --non-interactive --accept-risk || true
openclaw models set "$AGENT_MODEL" || true
# the gateway's systemd unit refuses to install while ~/.config is group-writable
chmod go-w ~/.config ~/.config/systemd ~/.config/systemd/user 2>/dev/null || true
openclaw gateway install || true
systemctl --user restart openclaw-gateway.service || true

# three OpenClaw agents: own workspace, own clone, own git identity, own venv, own provider auth
for a in builder-core builder-ui tester; do
  ws=~/.openclaw/workspace-$a
  openclaw agents add "$a" --workspace "$ws" --model "$AGENT_MODEL" --non-interactive 2>/dev/null || true
  mkdir -p "$ws"
  cp ~/triage-desk/agents/$a.md "$ws/AGENTS.md"
  [ -d "$ws/triage-desk" ] || gh repo clone "$REPO" "$ws/triage-desk"
  git -C "$ws/triage-desk" config user.name  "$a (OpenClaw)"
  git -C "$ws/triage-desk" config user.email "$a@triage-desk.agents"
  [ -d "$ws/triage-desk/.venv" ] || python3 -m venv "$ws/triage-desk/.venv"
  "$ws/triage-desk/.venv/bin/pip" install -q fastapi uvicorn httpx pytest
  echo "$NVIDIA_API_KEY" | openclaw models auth paste-api-key --provider nvidia --agent "$a" >/dev/null 2>&1 || true
done
openclaw gateway restart >/dev/null 2>&1 || true

echo "== hermes"
# note: on a brand-new box the Hermes installer runs a short wizard. Answers that match this
# setup: provider "custom", terminal backend "local", no messaging platforms, telemetry off.
if ! command -v hermes >/dev/null && [ ! -x "$HOME/.hermes/bin/hermes" ]; then
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi
export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
mkdir -p ~/.hermes
for p in orchestrator reviewer; do
  hermes profile create "$p" --clone 2>/dev/null || true
  cp ~/triage-desk/agents/$p.md ~/.hermes/profiles/$p/SOUL.md
  hermes -p "$p" config set model.provider custom >/dev/null
  hermes -p "$p" config set model.base_url "$NVIDIA_URL" >/dev/null
  hermes -p "$p" config set model.default "$HERMES_MODEL" >/dev/null
  hermes -p "$p" config set model.api_key "$NVIDIA_API_KEY" >/dev/null
  hermes -p "$p" config set terminal.backend local >/dev/null || true
done

echo "== the app: env, systemd units, caddy"
cd ~/triage-desk
cat > .env <<EOF
TRIAGE_API_URL=https://api.groq.com/openai/v1/chat/completions
TRIAGE_API_KEY=$GROQ_API_KEY
OLLAMA_API_KEY=${OLLAMA_API_KEY:-unused}
EOF
chmod 600 .env
bash scripts/deploy.sh
# the committed units default to Ollama's model name; this box classifies through Groq
for u in triage triage-feed; do
  sudo mkdir -p /etc/systemd/system/$u.service.d
  printf '[Service]\nEnvironment=TRIAGE_MODEL=openai/gpt-oss-20b\n' | sudo tee /etc/systemd/system/$u.service.d/override.conf >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl restart triage.service
sudo systemctl start triage-feed.service || true

echo "== keepalive cron so the box never looks idle"
( crontab -l 2>/dev/null | grep -v triage-keepalive; echo "*/30 * * * * date >> /tmp/triage-keepalive.log # triage-keepalive" ) | crontab -

echo
echo "done. open a new shell (or: source ~/.bashrc) then check:"
echo "  curl -s http://127.0.0.1/api/config"
echo "  openclaw agents list"
echo "  hermes profile list"
echo "  openclaw agent --agent builder-core --message 'one sentence: your role?'"
echo "  hermes -p reviewer chat -Q -t terminal,file -q 'one sentence: your role?'"
echo "run a ticket:"
echo "  BUILDER_MODEL=$AGENT_MODEL bash agents/run_ticket.sh <issue> <builder-core|builder-ui|tester>"
