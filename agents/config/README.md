# Runtime config, secrets removed

Copied from the VM after the build, keys replaced with `<redacted>`.

- `openclaw.json`: the `agents` section of `~/.openclaw/openclaw.json`: the three OpenClaw
  agents, their workspaces and their configured default model. The default still reads
  `ollama-cloud/...` because the move to NVIDIA was done per call (`--model`, passed by
  `run_ticket.sh` as `BUILDER_MODEL`) rather than by changing the agent config. Provider auth
  lives in OpenClaw's auth store, not in this file.
- `hermes-orchestrator.yaml`, `hermes-reviewer.yaml`: the two Hermes profile configs with
  comments and blank lines stripped. `model.provider`, `model.base_url` and `model.default` are
  the NVIDIA settings from ticket 12 on; before that they were `ollama-cloud` with
  `gpt-oss:120b` (orchestrator) and `nemotron-3-super` (reviewer).

Prompts are the role files one level up (`agents/<name>.md`): copied to each OpenClaw workspace
as `AGENTS.md` and to each Hermes profile as `SOUL.md`. No custom skills were installed on
either runtime; the agents used the stock terminal and file tools only.
