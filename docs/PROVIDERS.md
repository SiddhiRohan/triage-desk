# Which model provider ran what, and when

The brief asked for free models and no paid keys. That held, but it took three providers.

| When (ET) | Provider | Plan | Agents | Classifier | How it ended |
|---|---|---|---|---|---|
| Sat Oct 11 evening to Sun 00:56 | Ollama Cloud | free | all five: gpt-oss:120b (orchestrator), gemma4:31b (builders), nemotron-3-super (reviewer), gpt-oss:20b then 120b (tester) | gpt-oss:20b | monthly free usage reached 0% mid-way through ticket 11 (1,580 requests that day; see docs/ollama-usage.png). Refills in four weeks. |
| Sun 01:02 to 01:26 | OpenRouter | free tier | reviewer and orchestrator on nvidia/nemotron-3-super-120b-a12b:free; builder-core the same for one fix | not used | 50 free requests per day; reached during ticket 12's review. Lifting it needs a one-time credit purchase, which the brief rules out. |
| Sun 01:40 onwards | NVIDIA (build.nvidia.com) | free developer API | all five on nvidia/nemotron-3-super-120b-a12b | not used | still running |
| Sun 01:49 onwards | Groq | free tier | not used | openai/gpt-oss-20b for the 30 feed messages | still running |

Tried and skipped: Cerebras, because activating the key now requires a card on file.

## What changed in config, and nothing else

- Hermes profiles: `model.provider`, `model.base_url`, `model.default`, `model.api_key`
  (`hermes -p <profile> config set ...`).
- OpenClaw agents: `openclaw models auth paste-api-key --provider nvidia --agent <a>` once per
  agent, then `--model <provider/model>` on each call. `agents/run_ticket.sh` passes it through
  `BUILDER_MODEL`.
- The product: ticket 12 made the classifier endpoint and key env vars (`TRIAGE_API_URL`,
  `TRIAGE_API_KEY`), set in the git-ignored `.env`; the model name is a systemd override.

While the classifier had no working provider (between the Ollama cap and ticket 12), the app did
what PLAN.md says it should: the rules fallback would have sent every message to Needs human with
confidence capped at 0.5. Nothing was auto-routed on a guess.

## Why the same model everywhere at the end

Ollama's free list let the reviewer sit on a different model family from the builders, which is
the cheap way to get a second opinion. NVIDIA's free API serves one model that fit, so from ticket
12 on, builder and reviewer were the same nemotron. The reviewer's two wrong calls (PR #22
approved with workspace paths and an inline key; PR #28 rejected over a declared test file) both
happened after that switch. One model reviewing its own habits is a real cost, and the first thing
to undo once a second free provider with a different model family is available.
