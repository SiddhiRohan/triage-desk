#!/usr/bin/env python3
"""Sum model usage from the OpenClaw agent transcript stores.

Usage: .venv/bin/python tools/token_report.py
Reads ~/.openclaw/agents/<agent>/agent/openclaw-agent.sqlite for the three
OpenClaw agents and prints calls / input / output / cache-read tokens per
agent and per model. Hermes agents report their own numbers via
`hermes -p <profile> insights`.
"""
import json, os, sqlite3, sys
from collections import defaultdict

try:
    import zstandard
    dctx = zstandard.ZstdDecompressor()
except ImportError:
    dctx = None

AGENTS = ["builder-core", "builder-ui", "tester"]
home = os.path.expanduser("~")

def events(db_path):
    conn = sqlite3.connect(db_path)
    skipped = 0
    for ej, ez in conn.execute("select event_json, event_zstd from transcript_events"):
        raw = ej
        if (raw is None or raw == "") and ez is not None:
            if dctx is None:
                skipped += 1
                continue
            raw = dctx.decompress(ez).decode("utf-8", "replace")
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            skipped += 1
    if skipped:
        print(f"  (skipped {skipped} rows in {os.path.basename(os.path.dirname(os.path.dirname(db_path)))}: compressed and no zstandard module, or bad json)", file=sys.stderr)

def find_usage(ev):
    # usage sits on assistant messages; walk one level of nesting to be safe
    if isinstance(ev, dict):
        if "usage" in ev and isinstance(ev["usage"], dict) and "input" in ev["usage"]:
            return ev.get("model") or ev.get("modelId") or "?", ev["usage"]
        for v in ev.values():
            if isinstance(v, dict):
                r = find_usage(v)
                if r:
                    return r
    return None

totals = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))  # agent -> model -> [calls, in, out, cache]
for a in AGENTS:
    db = f"{home}/.openclaw/agents/{a}/agent/openclaw-agent.sqlite"
    if not os.path.exists(db):
        print(f"no store for {a}", file=sys.stderr)
        continue
    for ev in events(db):
        r = find_usage(ev)
        if not r:
            continue
        model, u = r
        t = totals[a][model]
        t[0] += 1
        t[1] += int(u.get("input", 0) or 0)
        t[2] += int(u.get("output", 0) or 0)
        t[3] += int(u.get("cacheRead", 0) or 0)

print(f"{'agent':13} {'model':40} {'calls':>6} {'input':>10} {'output':>8} {'cacheRead':>10}")
grand = [0, 0, 0, 0]
for a in AGENTS:
    for model, t in sorted(totals[a].items(), key=lambda kv: -kv[1][1]):
        print(f"{a:13} {model:40} {t[0]:>6} {t[1]:>10,} {t[2]:>8,} {t[3]:>10,}")
        for i in range(4):
            grand[i] += t[i]
print(f"{'total':13} {'':40} {grand[0]:>6} {grand[1]:>10,} {grand[2]:>8,} {grand[3]:>10,}")
