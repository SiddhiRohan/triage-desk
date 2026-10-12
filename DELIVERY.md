# Triage Desk: delivery notes

Live board: http://18.217.125.82
Repo: https://github.com/SiddhiRohan/triage-desk
Author: Siddhi Rohan Chakka, Oct 10 to 12, 2026

A small intake router. Thirty synthetic messages come in, each gets a category, a priority, a
confidence score and a one-line reason from a model, and lands in a queue on a public board.
Anything under the confidence threshold (0.70, configurable) goes to "Needs human" and gets no
action buttons. Nothing is ever sent, closed or deleted. SQLite underneath, FastAPI and one HTML
page on top, Caddy in front, on an AWS VM that Terraform built.

The agents wrote the code. I wrote the plan (`docs/PLAN.md`) and the role files (`agents/`),
ran the loop, filed the bugs I found when I started the service, rejected pull requests when the
reviewer let something through, and merged. Thirteen tickets, thirteen PRs, every commit on
`main` authored by an agent. `git log --format='%an %s'` shows it.

## 1. Roster

| Agent | Runtime | Job | Model (tickets 1 to 11) | Model (from ticket 11) |
|---|---|---|---|---|
| orchestrator | Hermes Agent profile | turns PLAN.md into GitHub issues, assigns, routes rejections back to the builder | gpt-oss:120b, Ollama Cloud | nemotron-3-super-120b, NVIDIA |
| builder-core | OpenClaw agent | backend, data model, feed, classifier, deploy files | gemma4:31b, Ollama Cloud | nemotron-3-super-120b, NVIDIA |
| builder-ui | OpenClaw agent | the board page and its JS | gemma4:31b, Ollama Cloud | nemotron-3-super-120b, NVIDIA |
| reviewer | Hermes Agent profile | reviews every PR against its issue and the hard rules, approves or rejects | nemotron-3-super, Ollama Cloud | nemotron-3-super-120b, NVIDIA |
| tester | OpenClaw agent | the hard-rules test suite | gpt-oss:20b then gpt-oss:120b, Ollama Cloud | nemotron-3-super-120b, NVIDIA |

Each OpenClaw agent has its own workspace, its own clone of the repo, its own git identity
(`builder-core (OpenClaw) <builder-core@triage-desk.agents>`) and its own venv. The Hermes
profiles run in my clone and never commit. Every model was a free tier; the provider changed
twice when free quotas ran out, which is section 4. Details in `agents/README.md` and
`docs/PROVIDERS.md`.

## 2. How a ticket moves

```
docs/PLAN.md
     |
     v
orchestrator opens the issue: title, agent, files touched, acceptance criteria. label: ready
     |
     v
orchestrator assigns: label in-progress, comment, starts the builder and waits
     |
     v
builder: branch ticket/<n>-<slug>, code and tests, pytest, commits as itself, pushes,
         PR with "Agent / Runtime / Model" header and "Closes #<n>". label: needs-review
     |
     v
reviewer: gh pr diff, the issue, the hard rules, checks the branch out, pytest twice
     |-- LGTM  -> label approved
     |-- no    -> label changes-requested, numbered findings
     |             -> orchestrator reads them, says which are valid, sends the builder back
     |             -> builder fixes on the same branch -> needs-review -> reviewer again
     v
I merge (merge commit, never squash, so the agent stays the author)
     |
     v
I deploy and open the page
     |-- wrong at runtime -> I open an issue "Bug found at deploy" -> same loop from the top
```

`agents/run_ticket.sh` runs one issue through everything above the merge and writes a log per
step to `logs/`. The orchestrator created the first eight issues from PLAN.md in one go
(`logs/01-orchestrator-creates-issues.log`), then produced two duplicates and some bodies with
literal `\n` in them, and cleaned both up when told (`logs/02`, `logs/03`). Tickets 9 to 13 are
the ones I filed.

## 3. What each agent actually did

| Ticket | Issue | PR | Agent | Review rounds | What happened |
|---|---|---|---|---|---|
| T1 skeleton | #1 | #15 | builder-core | 4 | reviewer approved with `__pycache__` files in it; I rejected; the reviewer got a rule and rejected on re-run; orchestrator then committed the fix itself under my name; I force-pushed that out and the builder redid it |
| T2 feed | #2 | #16 | builder-core | 1 | clean |
| T3 rules classifier | #4 | #17 | builder-core | 1 | clean |
| T4 LLM classifier | #6 | #18 | builder-core | 1 | clean |
| T5 board page | #11 | #19 | builder-ui | 2 | one round of findings, fixed |
| T6 audit trail | #12 | #20 | builder-core | 3 | tests wrote to the real `data/triage.db`; I rejected; the fix was a DELETE-rows cleanup; I rejected again; tmp_path fixture via conftest |
| T7 hard-rules tests | #13 | #21 | tester | 5 | on gpt-oss:20b the tester stalled, then shipped a one-line tweak to an existing test with a PR body claiming a full suite; the reviewer approved it; I rejected; moved to gpt-oss:120b, which wrote the suite but edited `app/main.py` and `run_feed.py` to make it pass; I rejected again |
| T8 deploy | #14 | #22 | builder-core | 4 | unit files pointed at the builder's own workspace clone, named `gpt-4o` as the model, put the API key inline; the reviewer approved it; I rejected; fix added DB_PATH twice; reviewer then rejected from a stale local branch, then rejected README as out of scope when the issue required it; I overrode |
| T9 feed import path | #23 | #24 | builder-core | 1 | found at deploy: `ModuleNotFoundError: app` under systemd. PYTHONPATH |
| T10 messages never inserted | #25 | #26 | builder-core | 1 | found at deploy: 30 decisions, 0 messages, empty board |
| T11 schema never created | #27 | #28 | builder-core | 3 | found at deploy on a wiped DB: nobody called `init_db()`; worked until then only because an old test run had created the tables. Ollama's cap hit mid-review; finished on OpenRouter |
| T12 classifier endpoint by env | #29 | #30 | builder-core | 1 | needed to move the classifier off Ollama. OpenRouter's cap hit mid-review; finished on NVIDIA |
| T13 board.js not served | #31 | #32 | builder-ui | 1 | found in the browser: `/static/board.js` 404, page stuck on "Loading config..." |

Per role:

- **orchestrator**: 8 issues from the plan, 13 assignments, 7 rejection routings, a status file
  (`docs/status.md`) it kept on its own. It misread the branch once (reported a fix missing that
  `gh pr diff` showed present, `logs/ticket-14-fix-2.log`) and committed once when it should not
  have (T1). About 860 model calls, most of them to run `gh` commands.
- **builder-core**: 10 of the 13 PRs, all the backend. Good at the ticket as written, bad at
  anything the ticket did not spell out: paths on the real box, whether the app actually starts
  from nothing.
- **builder-ui**: the board page (T5) and the static mount fix (T13). Clean both times.
- **reviewer**: about 30 review runs. It caught real things (the `__pycache__` files on re-run,
  the DB_PATH line the builder dropped, scope leaks) and missed real things (the deploy paths,
  the inline key, the one-line tweak posing as a suite). It got pedantic about "files touched"
  twice and judged from a stale checkout twice. Every miss became a rule in `agents/reviewer.md`,
  dated by PR number.
- **tester**: one ticket, five rounds, two of them my rejections. Its first instinct on a failing
  test was to change the product.

Five of the thirteen tickets (T9 to T13) are bugs that only show up when the service runs. Every
one passed pytest and review. No agent ever started the server or opened the page; I did, once
T8 merged. That is the biggest gap in the loop and item 2 in section 5.

## 4. What broke and what I did about it

**Oracle had no capacity.** The brief's first choice was Oracle's free A1 VM. `terraform apply`
returned "Out of host capacity" in every Ashburn availability domain for 15 hours of retries.
I kept the Terraform in `infra/oracle/` as evidence and moved to the brief's plan B, AWS, on
Sunday morning. First `apply` there was denied by the Free-plan SCP in us-east-1; the account
lives in us-east-2. `infra/aws/` is what built the box.

**Agents did things that passed and were wrong.** Six times I rejected a PR the reviewer had
approved or was about to. The pattern was always the same: the letter of the ticket was met, the
point was missed. Each one turned into a line in a role file:

- T1: reviewer approved generated files. Rule: generated files are a rejection.
- T1: orchestrator committed under my name. Rule: the orchestrator never commits; builders do.
- T6: tests used the real database, then "fixed" it with a DELETE. Rule: tests use tmp_path,
  never `data/triage.db`, never a cleanup.
- T7: a one-line tweak with a PR body describing a full suite, approved. Rule: the PR must
  deliver the acceptance criteria; body claims must match the diff.
- T7: tester edited product code so its tests passed. Rule: tester never touches `app/`,
  `scripts/`, `data/`; it files an issue instead.
- T8: deploy files pointed at the agent's own clone with the key inline, approved. Rule: deploy
  files use the real checkout path and an EnvironmentFile; model names must be ones we can call.

**The reviewer trusted its local checkout.** Twice it rejected a PR for something `gh pr diff`
showed was fixed, because the branch in my clone was behind. Rule: the diff from GitHub is the
only source of truth.

**Three deploy-time bugs in a row.** Import path (T9), messages never inserted (T10), schema
never created (T11). The last one is the instructive one: the app had worked all evening because
an early test run had created the tables in `data/triage.db`. The moment I deleted that file to
test a clean start, nothing worked. PLAN.md's definition of done says "starts with an empty db"
and nobody, agent or reviewer, had checked that.

**Two free quotas ran out in one hour.** At 00:56 Ollama Cloud's free plan reported 0% left
(1,580 requests that day, refills in four weeks). I moved the Hermes profiles to OpenRouter's free
tier (same nemotron model with a `:free` suffix) with four config lines, moved OpenClaw's builder
with a per-call `--model` flag, and finished T11. At 01:23 OpenRouter's 50-requests-a-day cap hit
in the middle of T12's review. Both providers offer to lift the cap for a one-time payment; the
brief says no paid keys, so no. I signed up for NVIDIA's free developer API (same nemotron model,
no card) and Groq's free tier (gpt-oss-20b, no card), pointed the agents at the first and the
classifier at the second, and finished T12 and T13. Cerebras was tried and dropped because it now
wants a card on file before the key works.

While the classifier had no provider, the product behaved as designed: the rules fallback with
confidence capped at 0.5 would have put all 30 messages in Needs human. Ugly board, zero wrong
routes.

**The reviewer misreported its own model twice.** It wrote `deepseek-v4-flash` in a PR header
while its config said nemotron. All model names in this document come from config files, the
runtimes' usage records and Ollama's usage page, not from what agents wrote about themselves.

**One GitHub token for everyone.** All five agents call `gh` with my token, so issue comments and
PR reviews show my account as the poster. The agent's identity is in the comment header
("Reviewer: reviewer / Runtime: Hermes / Model: ...") and in the commit author. I decided not to
make five GitHub accounts for a weekend project; it is first on the list below.

## 5. What I would change

1. **Fresh session per ticket for OpenClaw agents.** Each agent kept one session for the whole
   day, so every call re-sent the entire history. By the end, builder-core's one-word test
   message cost 168k input tokens. 40 million of the 51 million tokens of context processed were
   cached re-reads of old turns. One flag fixes it.
2. **A "run it" gate before merge.** The tester, or a script, starts the service against an
   empty database, hits `/`, `/static/board.js`, `/api/config` and `/api/messages`, and fails the
   PR if any of them does not answer. It would have caught T9, T10, T11 and T13 before I did.
3. **Reviewer reads less.** It read about a million input tokens for 13 PRs, re-reading PLAN.md
   and its own checklist every round. Give it the diff and the acceptance list only, and PLAN.md
   on request.
4. **Reviewer on a different model family from the builders, always.** That was true on Ollama
   and stopped being true on NVIDIA, where one model was the only fit.
5. **Provider fallback chain from day one.** Both runtimes support it (`hermes fallback add`,
   `openclaw models fallbacks`). I wired providers by hand at 1am; a chain would have made the
   switch a non-event.
6. **The orchestrator's assign step is a script, not a model call.** 860 calls, most of them
   running `gh issue edit` and waiting. A 20-line shell script does that; keep the model for
   routing rejections, where there is a judgement to make.
7. **Issue template says "tests may add files under tests/".** Two review rounds were spent on
   a new test file not being in the "files touched" list.
8. **One GitHub account per agent**, or a GitHub App, so the trail shows who said what without
   reading headers.

## 6. Token and model report

Sources: `hermes -p <profile> insights` for the two Hermes agents, `tools/token_report.py` over
the three OpenClaw agents' transcript stores, and Ollama's usage page (`docs/ollama-usage.png`).
Input and output are what the providers reported per call; "context processed" adds cached
re-reads, which is where the real cost sits.

| Agent | Runtime | Calls | Input tokens | Output tokens | Context processed |
|---|---|---|---|---|---|
| orchestrator | Hermes | 863 | 261,222 | 72,436 | 4.2M |
| reviewer | Hermes | 982 | 1,000,487 | 115,803 | 6.5M |
| builder-core | OpenClaw | 258 | 2,152,906 | 39,041 | 29.2M |
| builder-ui | OpenClaw | 55 | 102,235 | 10,109 | 1.8M |
| tester | OpenClaw | 247 | 1,231,856 | 65,030 | 12.5M |
| total | | 2,405 | 4.75M | 302k | 54M |

Per model, as the providers count them:

| Model | Provider | Requests | Used by |
|---|---|---|---|
| gpt-oss:120b | Ollama Cloud | 597 | orchestrator; tester after its 20b stall |
| nemotron-3-super | Ollama Cloud | 479 | reviewer |
| gemma4:31b | Ollama Cloud | 300 | builder-core, builder-ui |
| gpt-oss:20b | Ollama Cloud | 204 | tester's first T7 attempt; first feed run (30 classifier calls) |
| nemotron-3-super-120b-a12b:free | OpenRouter | ~45 | reviewer, orchestrator, builder-core during T11 and T12 |
| nemotron-3-super-120b-a12b | NVIDIA | ~60 | all five agents from T12 on |
| openai/gpt-oss-20b | Groq | 30 | the classifier, current board |

Cost: $0. No paid key, no credits, no card on any provider.

The classifier itself: 30 messages, 26 routed by the model, 4 by the rules fallback. The four are
the deliberately vague ones in the feed ("Uh...", "Hello", "Wait", "Maybe?"); the model did not
return usable JSON for them, the fallback scored them 0.2 to 0.4, and the 0.70 threshold put them
in Needs human. PLAN.md predicted 4 to 8 of 30 at that threshold. I did not change it.

## 7. Trace excerpts

All from `logs/` and the PR comment threads. Full files are in the repo.

The reviewer, on re-review of the first PR after I added the generated-files rule
(`logs/06-reviewer-rereviews-PR15.log`):

```
1. Generated files present: The diff adds __pycache__/*.pyc files:
   - app/__pycache__/__init__.cpython-312.pyc
   - app/__pycache__/main.cpython-312.pyc
   ...
2. Scope violation: The PR modifies files outside the ticket's scope:
   - agents/builder-core.md
   ...
   The PR author stated "Anything outside the ticket I had to touch: none," which is incorrect.
```

The reviewer approving a PR that did not do its ticket (`logs/ticket-13-review-3.log`, T7,
first attempt on gpt-oss:20b):

```
- The PR only modifies tests/test_api.py, adding a try-except block around res.json() ...
- Non-blocking: the PR body claims to have added comprehensive hard-rule unit tests, but the
  diff shows only a minor tweak. However, the test suite already exists and passes, so this
  does not block approval.
Approved PR #21 and removed needs-review label.
```

My rejection on the same PR, and the second one two rounds later (PR #21 comments):

```
Manager review: this PR does not do ticket #13. The acceptance criteria call for a hard-rules
test suite (...). The diff is a one-line change to an existing test. Passing tests are
necessary, not sufficient: the PR must do what the ticket says. Sending back.

Manager review: the test suite is now there, good. But the tester changed app/main.py and
scripts/run_feed.py so the app runs the feed on startup and whenever a GET finds an empty
database. That is a product behavior change made to satisfy tests, and a harmful one: it would
fire 30 classifier calls on every cold start. The tester's role is tests only. Revert all
changes to app/ and scripts/. (...) If a test exposes a real bug in the app, open an issue for
builder-core instead of fixing it here. Sending back.
```

The reviewer judging from a stale branch (`logs/ticket-14-review-3.log`), one minute after
`gh pr diff` showed both lines present:

```
- deployment/triage.service: missing Environment=DB_PATH=/home/ubuntu/triage-desk/data/triage.db
- deployment/triage-feed.service: missing Environment=DB_PATH=...
Verdict: Changes are required.
```

The quota running out mid-ticket (`logs/ticket-27-review-2.log` and `ticket-29-1-assign.log`):

```
Billing or credits exhausted: HTTP 429: you (siddhirohanwork) have reached your monthly usage
limit, upgrade for higher limits: https://ollama.com/upgrade ...

OpenRouter rate-limited every one of 3 attempts.
Provider said: HTTP 429: Rate limit exceeded: free-models-per-day. Add 10 credits to unlock
1000 free model requests per day
```

A clean round, the shape most tickets had (`logs/ticket-25-review-1.log`, T10):

```
Reviewer: reviewer / Runtime: Hermes / Model: nemotron-3-super
- Acceptance criteria satisfied: run_feed inserts messages via INSERT OR IGNORE before
  classification, idempotent, test verifies 30 messages/30 decisions and API returns 30 items,
  runs twice.
- Hard rule 1: grep for prohibited outbound calls found none.
- Hard rule 2: traced threshold logic; items under confidence threshold still route to Needs
  human (classify.py unchanged).
...
All checks pass. LGTM.
```

Screenshots: `docs/board.png`, `docs/panel-llm.png`, `docs/panel-needs-human.png`,
`docs/ollama-usage.png`.

## 8. Reproduce

Needs: an AWS account (Free plan is enough; the account's home region must allow EC2, mine is
us-east-2), a GitHub fine-grained token for the repo (contents, issues, pull requests: write),
and free API keys from build.nvidia.com and console.groq.com.

```
# laptop
cd infra/aws
cp terraform.tfvars.example terraform.tfvars    # key pair name, region
terraform init && terraform apply               # prints public_ip
ssh ubuntu@<public_ip>

# on the VM
git clone https://github.com/SiddhiRohan/triage-desk ~/triage-desk
export GH_TOKEN=... NVIDIA_API_KEY=... GROQ_API_KEY=...
bash ~/triage-desk/infra/setup.sh
```

`setup.sh` installs OpenClaw and Hermes, creates the three OpenClaw agents and two Hermes
profiles with their role files, clones, identities and provider auth, installs the app's systemd
units and Caddy, and runs the feed. `curl http://<public_ip>/api/config` answers when it is done.
Honest note: the box you are looking at was built by an earlier version of this script plus the
fixes recorded in section 4; the current script folds those in but has not been run end to end on
a fresh VM.

To run the agent loop:

```
BUILDER_MODEL=nvidia/nvidia/nemotron-3-super-120b-a12b bash agents/run_ticket.sh <issue> <builder-core|builder-ui|tester>
gh pr merge <PR> --merge --delete-branch && gh issue edit <issue> --remove-label in-progress --add-label done
```

To have the orchestrator create issues from a plan: the command is the first line of
`logs/01-orchestrator-creates-issues.log`.

## 9. Infra

`infra/aws/`: one `m7i-flex.large` (the Free plan's allowed shape) on Ubuntu 24.04 in the
default VPC, a security group for 22/80/443, the public IP as an output. `infra/oracle/`: the
original A1.Flex plan with VCN, subnet, gateway and security list, which never got capacity.
`infra/setup.sh`: everything after the VM exists. The app runs under two systemd units
(`deployment/`), Caddy proxies :80 to uvicorn on 127.0.0.1:8000, the feed unit is a oneshot
that runs on boot and is idempotent.

The VM stays up until you say otherwise.
