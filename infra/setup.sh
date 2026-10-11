#!/usr/bin/env bash
# Sets up a fresh Ubuntu 24.04 box as the Triage Desk agent host.
# Run as the ubuntu user after `terraform apply`:
#
#   export OLLAMA_API_KEY=... OPENROUTER_API_KEY=... GH_TOKEN=...
#   bash setup.sh
#
# Idempotent-ish: safe to re-run, it skips what is already there.
set -euo pipefail

REPO="SiddhiRohan/triage-desk"
: "${OLLAMA_API_KEY:?set OLLAMA_API_KEY}"
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
: "${GH_TOKEN:?set GH_TOKEN (a fine-grained token scoped to the repo)}"

echo "== packages"
sudo apt-get update -q
sudo apt-get install -y -q build-essential git curl jq gh python3 python3-venv python3-pip sqlite3

echo "== docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
fi

echo "== caddy (serves the board on :80)"
if ! command -v caddy >/dev/null; then
  sudo apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -q && sudo apt-get install -y -q caddy
fi

echo "== keys into ~/.bashrc"
grep -q OLLAMA_API_KEY ~/.bashrc     || echo "export OLLAMA_API_KEY=\"$OLLAMA_API_KEY\"" >> ~/.bashrc
grep -q OPENROUTER_API_KEY ~/.bashrc || echo "export OPENROUTER_API_KEY=\"$OPENROUTER_API_KEY\"" >> ~/.bashrc
grep -q GH_TOKEN ~/.bashrc           || echo "export GH_TOKEN=\"$GH_TOKEN\"" >> ~/.bashrc

echo "== github"
echo "$GH_TOKEN" | gh auth login --with-token
gh auth setup-git
sudo loginctl enable-linger "$USER"   # user services survive logout

echo "== repo clone for me (orchestrator + reviewer + merging)"
[ -d ~/triage-desk ] || gh repo clone "$REPO" ~/triage-desk
git -C ~/triage-desk config user.name  "Siddhi Rohan Chakka"
git -C ~/triage-desk config user.email "siddhirohanwork@gmail.com"

echo "== openclaw"
if ! command -v openclaw >/dev/null; then
  curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard || curl -fsSL https://openclaw.ai/install.sh | bash
fi
export PATH="$HOME/.npm-global/bin:$PATH"
openclaw onboard --auth-choice ollama-cloud --non-interactive || true
openclaw models set ollama-cloud/gpt-oss:120b
openclaw gateway install || true
systemctl --user restart openclaw-gateway.service || true

# the three openclaw agents, each with its own workspace, model, clone and git identity
declare -A MODEL=( [builder-core]=gemma4:31b [builder-ui]=gemma4:31b [tester]=gpt-oss:20b )
for a in builder-core builder-ui tester; do
  ws=~/.openclaw/workspace-$a
  openclaw agents add "$a" --workspace "$ws" --model "ollama-cloud/${MODEL[$a]}" --non-interactive 2>/dev/null || true
  mkdir -p "$ws"
  cp ~/triage-desk/agents/$a.md "$ws/AGENTS.md"
  [ -d "$ws/triage-desk" ] || gh repo clone "$REPO" "$ws/triage-desk"
  git -C "$ws/triage-desk" config user.name  "$a (OpenClaw)"
  git -C "$ws/triage-desk" config user.email "$a@triage-desk.agents"
done

echo "== hermes"
if ! command -v hermes >/dev/null; then
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi
export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
mkdir -p ~/.hermes
grep -q OLLAMA_API_KEY ~/.hermes/.env 2>/dev/null || echo "OLLAMA_API_KEY=$OLLAMA_API_KEY" >> ~/.hermes/.env
grep -q OPENROUTER_API_KEY ~/.hermes/.env 2>/dev/null || echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> ~/.hermes/.env
# minimal config; if ~/.hermes/config.yaml was copied from a working machine this is skipped
if [ ! -f ~/.hermes/config.yaml ]; then
cat > ~/.hermes/config.yaml <<'EOF'
model:
  provider: "ollama-cloud"
  default: "gpt-oss:120b"
agent:
  reasoning_effort: medium
terminal:
  backend: local
EOF
fi
for p in orchestrator reviewer; do
  hermes profile create "$p" --clone 2>/dev/null || true
  cp ~/triage-desk/agents/$p.md ~/.hermes/profiles/$p/SOUL.md
done
hermes -p reviewer config set model.default nemotron-3-super || true

echo "== caddy config (proxy :80 -> uvicorn :8000)"
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
:80 {
    reverse_proxy 127.0.0.1:8000
}
EOF
sudo systemctl restart caddy

echo "== keepalive cron so the box never looks idle"
( crontab -l 2>/dev/null | grep -v triage-keepalive; echo "*/30 * * * * date >> /tmp/triage-keepalive.log" ) | crontab -

echo
echo "done. open a new shell (or: source ~/.bashrc) then check:"
echo "  openclaw agents list"
echo "  hermes profile list"
echo "  openclaw agent --agent builder-core --message 'one sentence: your role?' --json | jq -r '.result.payloads[0].text'"
echo "  hermes -p reviewer chat -Q -t terminal,file -q 'one sentence: your role?'"
