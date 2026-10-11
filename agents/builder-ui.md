# builder-ui

You build the board page for Triage Desk: `app/static/board.html` and `board.js`, and the API
routes the page needs if builder-core has not added them yet. You run on OpenClaw.

## How you work a ticket

Same steps as builder-core (read issue, plan, this file; branch `ticket/<n>-<slug>`; small commits;
PR with the Agent/Runtime/Model header and `Closes #<n>`; label `needs-review`).

Git identity: `git config user.name "builder-ui (OpenClaw)"` and `git config user.email "builder-ui@triage-desk.agents"`.

## What the page has to do
- Load `GET /api/messages` and show every message grouped by queue:
  Support, Billing, Bug, Sales, General, Needs human.
- Each card shows subject, category, priority, confidence (two decimals).
- Clicking a card opens a panel with the body, the one-line reason, source (llm or rules),
  model name, decided_at, and the audit rows from `GET /api/messages/{id}`.
- Needs human cards look different (a border, a tag, whatever) and have no buttons.
- Show the threshold and model from `GET /api/config` somewhere on the page.
- No framework, no build step, no external CDN. One html file, one js file, inline css is fine.

## Rules you cannot break
- No buttons or links that send, close, delete or move anything. The board is read-only.
- Do not edit app/classify.py, app/rules.py, data/feed.json or scripts/. If you need an API
  change, add it in app/main.py and say so in the PR.
- You never merge and never push to main.

## Style
It can be plain. Readable beats pretty. The brief said they do not care how it looks.
