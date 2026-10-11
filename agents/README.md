# The delivery team

Five agents across two runtimes build Triage Desk. I (Rohan) write the plan, set the agents up,
review and merge. The agents write the code.

| Agent | Runtime | Role | Model (Ollama Cloud) | Fallback (OpenRouter) |
|---|---|---|---|---|
| orchestrator | Hermes profile | breaks the plan into issues, assigns, watches for stalls | glm-5.2 | nvidia/nemotron-3-super-120b-a12b:free |
| builder-core | OpenClaw agent | backend, data, classifier | qwen3-coder:30b | cohere/north-mini-code:free |
| builder-ui | OpenClaw agent | the board page and its JS | qwen3-coder:30b | cohere/north-mini-code:free |
| reviewer | Hermes profile | checks every PR against its issue and the hard rules | deepseek-v4-flash | google/gemma-4-31b-it:free |
| tester | OpenClaw agent | writes and runs tests, confirms the hard rules hold | gemma4:26b | nvidia/nemotron-3.5-lightning:free |

Why two builders: data/classifier work and UI work touch different files, so they can run as
separate tickets without merge conflicts. Why the reviewer is on a different model family from the
builders: a model is bad at spotting its own habits.

Each role file in this folder is that agent's standing instructions. For OpenClaw agents it goes
in the agent workspace as AGENTS.md. For Hermes profiles it is the profile's system prompt.

## How a ticket moves

```
PLAN.md + brief
     |
     v
orchestrator  --opens issue, label: ready, assignee label: agent/<name>-->  GitHub issue
     |
     v
builder picks it up: label in-progress, branch ticket/<n>-<slug>, commits as itself
     |
     v
builder opens PR "Closes #<n>", label: needs-review
     |
     v
reviewer reads PR + issue + hard rules
     |-- ok -> label: approved, comment "LGTM: <what it checked>"
     |-- not ok -> label: changes-requested, comment with numbered reasons -> back to builder
     |
     v
tester (after the UI and classifier PRs merge): label: testing, writes/runs tests
     |-- pass -> comment on the issue, label: verified
     |-- fail -> opens a new issue "bug: ..." assigned to the builder, label: ready
     |
     v
Rohan merges approved + verified PRs. Nobody else merges.
```

Labels: `ready`, `in-progress`, `needs-review`, `changes-requested`, `approved`, `testing`,
`verified`, `blocked`, plus one `agent/<name>` label per agent for assignment.

## Git identity

Every agent commits under its own name so the history shows who did what:

```
git config user.name  "builder-core (OpenClaw)"
git config user.email "builder-core@triage-desk.agents"
```

Same pattern for the others. PR descriptions start with `Agent: <name> / Runtime: <runtime> / Model: <model>`.

## What every agent must never do

- merge anything
- push to main
- change a file outside its ticket's scope without saying so in the PR
- put a secret in a file
- add code that sends email, calls a webhook, closes or deletes a message
