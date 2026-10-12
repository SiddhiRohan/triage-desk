# The delivery team

Five agents across two runtimes built Triage Desk. I (Rohan) wrote the plan (docs/PLAN.md), set
the agents up, filed bugs I found at deploy time, rejected PRs when the reviewer let something
through, and merged. The agents wrote every line of product code; `git log` shows it.

| Agent | Runtime | Role | Model, tickets 1 to 11 | Model, tickets 11 to 13 and from here on |
|---|---|---|---|---|
| orchestrator | Hermes profile | turns the plan into issues, assigns, routes rejections back | gpt-oss:120b (Ollama Cloud) | nemotron-3-super-120b (NVIDIA) |
| builder-core | OpenClaw agent | backend, data, classifier, deploy files | gemma4:31b (Ollama Cloud) | nemotron-3-super-120b (NVIDIA) |
| builder-ui | OpenClaw agent | the board page and its JS | gemma4:31b (Ollama Cloud) | nemotron-3-super-120b (NVIDIA) |
| reviewer | Hermes profile | checks every PR against its issue and the hard rules, can reject | nemotron-3-super (Ollama Cloud) | nemotron-3-super-120b (NVIDIA) |
| tester | OpenClaw agent | the hard-rules test suite (ticket 7) | gpt-oss:20b, then gpt-oss:120b (Ollama Cloud) | nemotron-3-super-120b (NVIDIA) |

Every model was a free tier. Ollama Cloud's free plan ran out (monthly cap) during ticket 11;
OpenRouter's free tier (same nemotron model, `:free` suffix) carried ticket 11 and part of 12 until
its 50 requests/day cap; NVIDIA's free API at build.nvidia.com ran the rest. The classifier inside
the product moved the same way: Ollama gpt-oss:20b for the first feed run, Groq's free
openai/gpt-oss-20b afterwards. Nothing was paid for. Details and dates in docs/PROVIDERS.md.

Why two builders: data/classifier work and UI work touch different files, so tickets can run
without merge conflicts. Why the reviewer started on a different model family from the builders: a
model is bad at spotting its own habits. That advantage went away when everything landed on
nemotron, and the reviewer did get more lenient at the end (see DELIVERY.md).

Each role file in this folder is that agent's standing instructions. For OpenClaw agents it is
copied into the agent workspace as AGENTS.md; for Hermes profiles it is the profile's SOUL.md.
The sections headed "Added after PR #n" at the bottom of each file are rules I added when a
ticket went wrong; the PR number says which one.

## Running a ticket

`run_ticket.sh` drives one issue through the loop and stops before the merge:

```
BUILDER_MODEL=nvidia/nvidia/nemotron-3-super-120b-a12b bash agents/run_ticket.sh <issue> <builder-core|builder-ui|tester>
```

It runs from `~/triage-desk` on the VM and writes `logs/ticket-<n>-*.log` for every step:
orchestrator assigns (labels, comment, starts the builder and waits), finds the PR by its
`Closes #<n>` line, runs the reviewer, and if the verdict is changes-requested it sends the
orchestrator back to route the fix to the builder, up to three review rounds. `BUILDER_MODEL` is
optional; without it the builder uses its configured default.

When it prints `== APPROVED`, I merge:

```
gh pr merge <PR> --merge --delete-branch && gh issue edit <issue> --remove-label in-progress --add-label done
```

Always `--merge`, never `--squash`: a squash commit carries the merger's name, and the brief wants
agent-authored commits visible in history.

Agents can also be called directly, which I did for one-line fix-ups when the orchestrator had
nothing to decide:

```
openclaw agent --agent builder-core --model <provider/model> --timeout 600 --message '...'
hermes -p reviewer chat -Q --yolo --in ~/triage-desk -t terminal,file --max-turns 40 --run-budget 900 -q '...'
```

## How a ticket moves

```
docs/PLAN.md
     |
     v
orchestrator  --opens issue: title, agent, files touched, acceptance criteria; label ready-->  GitHub issue
     |
     v
orchestrator assigns: label in-progress, comment, starts the builder
     |
     v
builder: branch ticket/<n>-<slug>, code + tests, pytest, commits as itself, pushes,
         opens PR with "Agent / Runtime / Model" header and "Closes #<n>", label needs-review
     |
     v
reviewer reads gh pr diff, the issue, the hard rules; checks out the branch; runs pytest twice
     |-- ok -> label approved, comment "LGTM: <what it checked>"
     |-- not ok -> label changes-requested, numbered findings
     |              -> orchestrator decides which findings are valid, sends the builder back
     |              -> builder fixes on the same branch, label needs-review -> reviewer again
     v
Rohan merges. Nobody else merges.
     |
     v
Rohan deploys (scripts/deploy.sh) and looks at the running thing.
     |-- something is wrong at runtime -> Rohan opens an issue "Bug found at deploy" -> same loop
```

The last step is where the plan and reality differed. PLAN.md had the tester running after the
UI and classifier merged and filing bugs; in practice the tester's ticket (T7) ran through the
normal loop like any other, and the bugs that mattered (T9 to T13) were only visible by starting
the service and opening the page, which no agent did. Those five issues were filed by me and fixed
by the builders through the same loop.

Labels: `ready`, `in-progress`, `needs-review`, `changes-requested`, `approved`, `done`,
`blocked`, plus one `agent/<name>` label per agent. `testing` and `verified` exist but went
unused for the reason above.

## Git identity

Every agent commits under its own name so the history shows who did what:

```
git config user.name  "builder-core (OpenClaw)"
git config user.email "builder-core@triage-desk.agents"
```

Same pattern for the others, in each agent's own clone under its workspace. PR descriptions start
with `Agent: <name> / Runtime: <runtime> / Model: <model>`. One caveat: the model line is what the
agent believes it is, and the reviewer twice wrote a model it was not running on. The numbers in
DELIVERY.md come from config files and the runtimes' own usage records, not from these headers.

All five agents share one GitHub token (mine), so issue comments and PR reviews show my GitHub
account as the poster; the agent identity is in the comment header and in the commit author.
Separate GitHub accounts per agent would fix that and is on the "what I'd change" list.

## What every agent must never do

- merge anything
- push to main
- change a file outside its ticket's scope without saying so in the PR
- put a secret in a file
- add code that sends email, calls a webhook, closes or deletes a message
- commit generated files (`__pycache__`, `.venv`, `data/*.db`, `.env`, logs)

And the ones that got added the hard way:

- orchestrator: never commit or edit repo files; builders commit (PR #15)
- reviewer: `gh pr diff` is the source of truth, never a local checkout that may be stale (PR #15, again at PR #22)
- reviewer: reject generated files, tests that touch the real database, deploy files that point at an agent workspace or carry an inline secret (PRs #15, #20, #22)
- tester: tests only; never edit `app/`, `scripts/` or `data/` to make a test pass (PR #21)
- all builders: run pytest from the clone's `.venv`, never system Python (PR #21)
