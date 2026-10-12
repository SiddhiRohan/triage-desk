#!/usr/bin/env bash
# One ticket through the team: orchestrator assigns -> builder builds -> reviewer reviews,
# with up to 2 fix rounds if the reviewer sends it back. Stops before merge; I merge.
#
#   bash agents/run_ticket.sh <issue-number> <builder-agent>
#   bash agents/run_ticket.sh 2 builder-core
#
# Runs from ~/triage-desk. Logs go to logs/ticket-<n>-*.log
set -uo pipefail
ISSUE="${1:?issue number}"
BUILDER="${2:?builder agent: builder-core, builder-ui or tester}"
REPO_DIR="$HOME/triage-desk"
OPENCLAW="$HOME/.npm-global/bin/openclaw"
cd "$REPO_DIR"
mkdir -p logs
git switch -q main && git pull -q

orch() {  # orchestrator, quiet one-shot
  hermes -p orchestrator chat -Q --yolo --in "$REPO_DIR" -t terminal,file --max-turns 30 --run-budget 1800 -q "$1"
}
rev() {
  hermes -p reviewer chat -Q --yolo --in "$REPO_DIR" -t terminal,file --max-turns 40 --run-budget 900 -q "$1"
}
pr_for_issue() {
  gh pr list --state open --json number,body --jq ".[] | select(.body | test(\"Closes #${ISSUE}\\\\b\")) | .number" | head -1
}

echo "== assign #$ISSUE to $BUILDER"
orch "Assign issue #$ISSUE to $BUILDER. Run: gh issue edit $ISSUE --remove-label ready --add-label in-progress, and comment on the issue that you are assigning it to $BUILDER. Then start the builder with exactly this command and wait for it: $OPENCLAW agent --agent $BUILDER --timeout 1500 --message 'Pick up issue #$ISSUE. The repo is at ./triage-desk in your workspace; cd into it, git checkout main, git pull. Read the issue with gh issue view $ISSUE --json title,body, read docs/PLAN.md and AGENTS.md, then do the ticket end to end: branch ticket/$ISSUE-<slug>, code, tests, pytest passing, git status to make sure no generated files are staged, commit as yourself, push, open the PR with gh pr create using the body format from AGENTS.md including the line Closes #$ISSUE, label it needs-review.' When it returns, run gh pr list and report." \
  2>&1 | tee "logs/ticket-$ISSUE-1-assign.log"

PR="$(pr_for_issue)"
if [ -z "$PR" ]; then
  echo "!! no open PR found that closes #$ISSUE. Check logs/ticket-$ISSUE-1-assign.log"; exit 1
fi
echo "== PR #$PR opened for #$ISSUE"

for round in 1 2 3; do
  echo "== review round $round"
  rev "Review PR #$PR as your SOUL.md says. git fetch origin first. Judge only from gh pr diff $PR, gh pr diff $PR --name-only, the PR body, gh issue view $ISSUE --json title,body, and docs/PLAN.md. Check out the branch and run pytest. Post your verdict as a PR comment with gh pr comment $PR, then set the label: approved (remove needs-review) or changes-requested (remove needs-review). Report the verdict." \
    2>&1 | tee "logs/ticket-$ISSUE-review-$round.log"

  LABELS="$(gh pr view "$PR" --json labels --jq '.labels[].name' | tr '\n' ' ')"
  echo "== labels now: $LABELS"
  case "$LABELS" in
    *approved*) echo "== APPROVED. merge with: gh pr merge $PR --merge --delete-branch && gh issue edit $ISSUE --remove-label in-progress --add-label done"; break ;;
    *changes-requested*)
      if [ "$round" -eq 3 ]; then echo "!! still rejected after 2 fixes, look at logs/ticket-$ISSUE-review-*.log"; break; fi
      echo "== routing rejection back to $BUILDER"
      orch "PR #$PR has changes-requested. Read the latest review comment with gh pr view $PR --comments. Decide which findings are valid (the files listed in issue #$ISSUE are in scope; .gitignore and __init__.py are in scope when declared). Comment on the PR saying which findings the builder must fix. Then send it back with this command and wait: $OPENCLAW agent --agent $BUILDER --timeout 1200 --message 'PR #$PR has changes requested. cd triage-desk, git fetch origin, git checkout the PR branch, git pull. Read the review with gh pr view $PR --comments, fix the findings the orchestrator marked valid on the same branch, run pytest, git status to check nothing generated is staged, commit as yourself, push, comment on the PR with what changed, then gh pr edit $PR --remove-label changes-requested --add-label needs-review.' Report when done." \
        2>&1 | tee "logs/ticket-$ISSUE-fix-$round.log"
      ;;
    *) echo "!! unexpected label state, stopping"; break ;;
  esac
done

git switch -q main
git clean -fdq app tests scripts data 2>/dev/null || true
echo "== done with #$ISSUE (PR #$PR). You merge."
