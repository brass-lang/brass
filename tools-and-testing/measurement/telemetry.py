#!/usr/bin/env python3
"""Per-session telemetry for a trial, from the harness transcript and the session's finished tree.

usage: telemetry.py <transcripts-dir> <run-dir> LABEL=agentId [LABEL=agentId ...] [--harness harness.json]

Writes <run-dir>/<LABEL>/telemetry.json and <run-dir>/telemetry.json (all sessions), and prints a table.
Every figure is taken from what the harness logged or from the files the session left; nothing is estimated.

Tokens: one request counted once, its usage from the last logged line of that request.
  ctx_first, ctx_second: context size at the first and second model call (the second follows the prompt read)
  ctx_final: context at the last call; task_tokens = ctx_final - ctx_second
  input_total: context summed over every call (what the model re-read); fresh: the uncached part of it
  output_written_chars: characters the model wrote, in text and tool inputs; exact. The transcript logs output
  tokens only as streaming snapshots, often missing the final count, so output_tokens_logged_unreliable is a floor.
  Thinking is not logged in a countable form and is not reported.
Tools: calls by tool; shell commands by first word (brass by verb); files read; reads of the reference after
  the prompt; edits and writes; tool results flagged as errors.
Outcome: the final answer's length; lines of source written; for Brass, `brass check`'s result line and its
  rejections; for Python, whether every file compiles.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRASS = HERE.parent / "proxy" / "bin" / "brass"


def transcript(path):
    reqs, tools, shell, reads, errors, stamps, models = OrderedDict(), Counter(), Counter(), [], 0, [], Counter()
    edits, answer, written = 0, "", 0
    for line in open(path):
        o = json.loads(line)
        if o.get("timestamp"):
            stamps.append(o["timestamp"])
        m = o.get("message") or {}
        if o.get("type") == "assistant":
            if m.get("model"):
                models[m["model"]] += 1
            if m.get("usage"):
                prev = reqs.get(o.get("requestId"))
                u = dict(m["usage"])
                if prev is not None:              # streaming snapshots: keep the largest output seen for the request
                    u["output_tokens"] = max(u.get("output_tokens", 0), prev.get("output_tokens", 0))
                reqs[o.get("requestId")] = u
            for c in m.get("content", []):
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    written += len(c.get("text", ""))
                if c.get("type") == "tool_use":
                    written += len(json.dumps(c.get("input") or {}))
                    name, inp = c.get("name"), c.get("input") or {}
                    tools[name] += 1
                    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                        edits += 1
                    if name == "Read" and inp.get("file_path"):
                        reads.append(inp["file_path"])
                    if name == "Bash":
                        cmd = inp.get("command", "")
                        for part in re.split(r"&&|;|\s\|\s", cmd):
                            words = part.strip().split()
                            if not words:
                                continue
                            w0 = words[0]
                            if w0 == "cd":
                                continue
                            if w0.endswith("brass"):
                                shell["brass " + (words[1] if len(words) > 1 else "(usage)")] += 1
                            else:
                                shell[w0] += 1
                    txt = json.dumps(inp)
                    if len(txt) > len(answer) and ("assumption" in txt.lower() or "patch" in txt.lower()) and name not in ("Edit", "Write", "Bash", "Read"):
                        answer = max((v for v in inp.values() if isinstance(v, str)), key=len, default="")
                if c.get("type") == "text" and len(c.get("text", "")) > len(answer):
                    answer = c["text"]
        if o.get("type") == "user" and isinstance(m.get("content"), list):
            for c in m["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                    errors += 1
    us = list(reqs.values())
    ctx = [u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in us]
    fresh = sum(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) for u in us)
    out = sum(u.get("output_tokens", 0) for u in us)
    t0 = datetime.fromisoformat(stamps[0].replace("Z", "+00:00")) if stamps else None
    t1 = datetime.fromisoformat(stamps[-1].replace("Z", "+00:00")) if stamps else None
    return {
        "models": dict(models), "calls": len(us),
        "ctx_first": ctx[0] if ctx else 0, "ctx_second": ctx[1] if len(ctx) > 1 else 0, "ctx_final": ctx[-1] if ctx else 0,
        "task_tokens": (ctx[-1] - ctx[1]) if len(ctx) > 1 else 0, "input_total": sum(ctx), "fresh_input": fresh,
        "output_written_chars": written, "output_tokens_logged_unreliable": out,
        "tools": dict(tools), "shell": dict(shell), "files_read": reads, "edits": edits, "tool_errors": errors,
        "seconds": round((t1 - t0).total_seconds()) if t0 and t1 else None, "answer_chars": len(answer),
    }


def outcome(project):
    src = project / "src"
    keel = sorted(list(src.rglob("*.brass")) + list(src.rglob("*.keel"))) if src.is_dir() else []
    py = sorted(src.rglob("*.py")) if src.is_dir() else []
    loc = sum(1 for f in keel + py for l in f.read_text().splitlines() if l.strip() and not l.strip().startswith("#"))
    res = {"source_lines": loc, "files": [str(f.relative_to(project)) for f in keel + py]}
    if keel:
        env = dict(os.environ, BRASS_PROJECT=str(project), BRASS_NO_LOG="1", BRASS_SRC=next((d.name for d in (project / "src").iterdir() if d.is_dir()), "park"))
        env.pop("BRASS_INFO_ONLY", None)
        text = subprocess.run([sys.executable, str(BRASS), "check"], env=env, capture_output=True, text=True).stdout
        res["brass_check"] = next((l.split(None, 1)[1] for l in text.splitlines() if l.startswith("result")), "no result line")
        res["brass_rejections"] = [l.strip() for l in text.splitlines() if re.match(r"\s+\S+\.(brass|keel):\d+", l)]
    if py:
        bad = []
        for f in py:
            try:
                compile(f.read_text(), str(f), "exec")
            except SyntaxError as e:
                bad.append(f"{f.name}:{e.lineno}: {e.msg}")
        res["python_compiles"] = not bad
        res["python_errors"] = bad
    return res


def brass_log(session_dir):
    logs = [lg for d in ("brass-logs", "keelc-logs") if (session_dir / d).is_dir() for lg in (session_dir / d).glob("*.log")]   # past runs wrote keelc-logs
    verbs = Counter()
    for lg in logs:
        for row in lg.read_text().splitlines():
            parts = row.split("\t")
            if len(parts) > 1:
                verbs[(parts[1].split() or ["(usage)"])[0]] += 1
    return dict(verbs)


def main(argv):
    tdir, run = Path(argv[0]), Path(argv[1])
    harness = {}
    if "--harness" in argv:                      # the harness's own end-of-session totals, as it reported them
        i = argv.index("--harness"); harness = json.loads(Path(argv[i + 1]).read_text()); argv = argv[:i] + argv[i + 2:]
    pairs = [a.split("=", 1) for a in argv[2:]]
    allrows = {}
    for label, aid in pairs:
        t = transcript(tdir / f"agent-{aid}.jsonl")
        sd = run / label
        log = brass_log(sd)                      # read before the outcome check runs brass
        o = outcome(sd / "project")
        rec = {"session": label, "agent": aid, **t, **o, "brass_log": log, "harness_reported": harness.get(label)}
        (sd / "telemetry.json").write_text(json.dumps(rec, indent=1))
        allrows[label] = rec
    (run / "telemetry.json").write_text(json.dumps(allrows, indent=1))
    cols = ["calls", "ctx_second", "task_tokens", "input_total", "output_written_chars", "edits", "tool_errors", "seconds", "source_lines"]
    print(f"{'session':9}" + "".join(f"{c:>13}" for c in cols) + "  check")
    for label, r in allrows.items():
        chk = r.get("brass_check") or ("compiles" if r.get("python_compiles") else f"py errors {r.get('python_errors')}")
        print(f"{label:9}" + "".join(f"{str(r.get(c)):>13}" for c in cols) + f"  {chk}")


if __name__ == "__main__":
    main(sys.argv[1:])
