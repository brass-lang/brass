#!/usr/bin/env python3
"""Run the rerun's sessions, unattended, each its own instance, every step recorded under rerun/runs/<run-id>/<task>/.

usage:
  run.py preflight <run-id>              tools, sign-in, model, audit, freeze; writes preflight.json; exits 1 on any failure
  run.py build <run-id>                  builds every session of both tasks under /tmp/rerun-<run-id>/<task>/; records prompt hashes
  run.py launch <run-id> <task> <group>  starts one group in the background; a group starts when the one before it is collected
  run.py wait <run-id> [minutes]         waits up to <minutes> (default 8) while any session runs; prints status
  run.py collect <run-id>                for every finished session not yet collected: record, telemetry, scores, checks
  run.py retry <run-id> <task> <label>   once per session, only after a harness failure (no result, or an error result)
  run.py status <run-id>                 one line per session

Tasks: C (task C, small and grown; arms P, K, KC; ten groups of three, stage 1's order extended to five per cell) and
D (task D; arms P and KC; five groups of two). Model and effort are fixed here: claude-sonnet-5 at effort high
(author, 2026-10-18). Every arm has the same tools; the record counts the KC sessions' edits made outside `brass apply`.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RERUN = Path(__file__).resolve().parents[1]
PUB = RERUN.parent
MODEL, EFFORT, CAP = "claude-sonnet-5", "high", 150
TASKS = {
    "C": {"groups": [[f"small-P{i}", f"grown-K{i}", f"small-KC{i}"] if j == 0 else [f"grown-P{i}", f"small-K{i}", f"grown-KC{i}"]
                     for i in range(1, 6) for j in (0, 1)],
          "builder": "build.py", "cases": RERUN / "cases", "evaluator": "evaluate.py"},
    "D": {"groups": [[f"P{i}", f"KC{i}"] for i in range(1, 6)],
          "builder": "build_d.py", "cases": RERUN / "D" / "cases", "evaluator": "evaluate_d.py"},
}
FREEZE_ROW = re.compile(r"^\| [a-z0-9 -]+ \| `[^`]+` \| `[0-9a-f]{16}` \|$", re.M)
HARNESS_PATH = re.compile(r"/\.claude/|/claude-\d+/|/tool-results/|/scratchpad")
EDITORS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

_spec = importlib.util.spec_from_file_location("telemetry", PUB / "validation" / "tools" / "telemetry.py")
telemetry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(telemetry)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def run_dir(run_id):
    d = RERUN / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def rec(run_id, task, label):
    return run_dir(run_id) / task / label


def build_dir(run_id, task):
    return Path("/tmp") / f"rerun-{run_id}" / task


def labels(task):
    return [l for g in TASKS[task]["groups"] for l in g]


def every():
    return [(t, l) for t in TASKS for l in labels(t)]


def size_arm(task, label):
    if task == "C":
        size, rest = label.split("-")
        return size, re.sub(r"\d+$", "", rest)
    return "stage2", re.sub(r"\d+$", "", label)


def tables(task, label):
    if task == "C":
        return ["C.json", "baseline.json"] + (["grown.json"] if size_arm(task, label)[0] == "grown" else [])
    return ["D.json", "baseline.json", "C.json", "grown.json"]


def spec_of(task, label):
    size, arm = size_arm(task, label)
    return f"{label}:{size}:{arm}" if task == "C" else f"{label}:{arm}"


# --- preflight ---------------------------------------------------------------------------------------------------

def preflight(run_id):
    out, ok = {"at": now(), "run_id": run_id, "model": MODEL, "effort": EFFORT, "cap": CAP}, True
    for tool in ("python3", "patch", "git", "claude"):
        out[f"has_{tool}"] = shutil.which(tool) is not None
        ok &= out[f"has_{tool}"]
    out["claude_version"] = sh(["claude", "--version"]).stdout.strip() if out["has_claude"] else None
    out["python_version"] = sys.version.split()[0]
    out["platform"] = sh(["uname", "-srm"]).stdout.strip()
    out["env_names"] = sorted(k for k in os.environ if k.startswith(("CLAUDE", "ANTHROPIC")))   # names only, never values
    out["parent_session_id"] = next((os.environ[k] for k in ("CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_SESSION_ID") if os.environ.get(k)), None)
    out["git_head"] = sh(["git", "rev-parse", "HEAD"], cwd=RERUN).stdout.strip()
    out["tool_hash"] = digest(RERUN / "tools" / "brass-lean8" / "brass.py")
    probe = Path("/tmp") / f"rerun-preflight-{run_id}"
    (probe / "project").mkdir(parents=True, exist_ok=True)
    (probe / "prompt.md").write_text("Reply with the single word OK.")
    r = sh([str(RERUN / "tools" / "launch.sh"), str(probe)], env={**os.environ, "RERUN_MODEL": MODEL, "RERUN_EFFORT": EFFORT})
    try:
        res = json.loads((probe / "result.json").read_text())
    except (OSError, json.JSONDecodeError):
        res = {}
    out["auth_ok"] = bool(res) and not res.get("is_error") and "OK" in str(res.get("result", ""))
    out["auth_models"] = list(res.get("modelUsage", {}).keys())
    out["auth_error"] = None if out["auth_ok"] else ((probe / "stderr.txt").read_text()[-400:] if (probe / "stderr.txt").exists() else r.stderr[-400:])
    out["model_ok"] = out["auth_models"] == [MODEL]
    out["probe_session_id"] = res.get("session_id")
    out["probe_own_instance"] = bool(res.get("session_id")) and res.get("session_id") != out["parent_session_id"]
    out["session_env_names"] = (probe / "env-session.txt").read_text().split() if (probe / "env-session.txt").exists() else None
    ok &= out["auth_ok"] and out["model_ok"] and out["probe_own_instance"]
    a = sh([sys.executable, str(RERUN / "tools" / "audit.py"), "--freeze"])
    out["audit_pass"] = a.returncode == 0 and "PASS: 0 failures" in a.stdout
    readme_rows, audit_rows = set(FREEZE_ROW.findall((RERUN / "README.md").read_text())), set(FREEZE_ROW.findall(a.stdout))
    out["freeze_match"] = bool(audit_rows) and audit_rows == readme_rows
    out["freeze_mismatch"] = sorted(audit_rows ^ readme_rows)
    out["freeze"] = sorted(audit_rows)
    ok &= out["audit_pass"] and out["freeze_match"]
    (run_dir(run_id) / "audit.txt").write_text(a.stdout + a.stderr)
    out["ok"] = ok
    (run_dir(run_id) / "preflight.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        if k not in ("freeze", "session_env_names"):
            print(f"{k:<20} {v}")
    return 0 if ok else 1


# --- build and launch --------------------------------------------------------------------------------------------

def build(run_id):
    pre = run_dir(run_id) / "preflight.json"
    if not pre.exists() or not json.loads(pre.read_text()).get("ok"):
        sys.exit("preflight has not passed for this run id")
    for task, cfg in TASKS.items():
        b = build_dir(run_id, task)
        if b.exists():
            sys.exit(f"{b} exists; a run is built once")
        r = sh([sys.executable, str(RERUN / "tools" / cfg["builder"]), str(b), "--cap", str(CAP), "--tag", f"{run_id}/{task}",
                *[spec_of(task, l) for l in labels(task)]])
        print(r.stdout, r.stderr)
        if r.returncode != 0:
            return 1
        (run_dir(run_id) / task).mkdir(exist_ok=True)
        shutil.copy(b / "manifest.json", run_dir(run_id) / task / "manifest.json")
    return 0


def state(run_id, task, label):
    s, r = build_dir(run_id, task) / label, rec(run_id, task, label)
    if (r / "summary.json").exists():
        return "collected"
    if (s / "result.json").exists() and (s / "result.json").stat().st_size > 0:
        return "finished"
    if (s / "pid").exists():
        try:
            os.kill(int((s / "pid").read_text()), 0)
            return "running"
        except (ProcessLookupError, ValueError):
            return "ended-without-result"
    return "not-started"


def done(run_id, task, label):
    st = state(run_id, task, label)
    return st == "collected" or (st == "ended-without-result" and (rec(run_id, task, label) / "attempt-1").exists())


def start(run_id, task, label):
    s = build_dir(run_id, task) / label
    log = open(s / "launch.log", "w")
    p = subprocess.Popen([str(RERUN / "tools" / "launch.sh"), str(s)], env={**os.environ, "RERUN_MODEL": MODEL, "RERUN_EFFORT": EFFORT},
                         stdout=log, stderr=log, start_new_session=True)
    (s / "pid").write_text(str(p.pid))
    (s / "started").write_text(now())
    return p.pid


def launch(run_id, task, group):
    if task not in TASKS:
        sys.exit(f"no task {task}")
    if not (build_dir(run_id, task) / "manifest.json").exists():
        sys.exit(f"{build_dir(run_id, task)} is not built; run `run.py build {run_id}` first")
    g = int(group)
    if g > 1 and not all(done(run_id, task, l) for l in TASKS[task]["groups"][g - 2]):
        sys.exit(f"{task} group {g - 1} is not fully collected; a group starts when the one before has finished")
    for label in TASKS[task]["groups"][g - 1]:
        st = state(run_id, task, label)
        if st != "not-started":
            print(f"{task}/{label}: {st}, not launched")
            continue
        print(f"{task}/{label}: launched, pid {start(run_id, task, label)}")
    return 0


def wait(run_id, minutes=8.0):
    end = time.time() + float(minutes) * 60
    while time.time() < end and any(state(run_id, t, l) == "running" for t, l in every()):
        time.sleep(20)
    return status(run_id)


# --- collect -----------------------------------------------------------------------------------------------------

def transcript_for(session_id, project):
    base = Path.home() / ".claude" / "projects"
    enc = re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))
    hit = base / enc / f"{session_id}.jsonl"
    if hit.exists():
        return hit
    found = list(base.glob(f"*/{session_id}.jsonl")) if session_id else []
    return found[0] if found else None


def tool_uses(transcript):
    """Every tool_use in order, each with the thinking tokens accumulated up to it."""
    uses, thinking = [], 0
    for line in transcript.read_text().splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = o.get("message") or {}
        if o.get("type") != "assistant" or not isinstance(m, dict):
            continue
        thinking += ((m.get("usage") or {}).get("output_tokens_details") or {}).get("thinking_tokens", 0)
        for c in m.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                uses.append((c.get("name"), c.get("input") or {}, thinking))
    return uses


def paths_outside(uses, session_dir):
    """Absolute paths in tool inputs that are not under the session: the harness's own (scratchpad, tool results) apart."""
    allowed = str(session_dir.resolve())
    leaks, harness = set(), set()
    for name, inp, _ in uses:
        for p in re.findall(r"(/(?:Users|home|root|tmp|private|var|etc|opt)[^\s\"'`]*)", json.dumps(inp)):
            if p.startswith(allowed):
                continue
            (harness if HARNESS_PATH.search(p) else leaks).add(f"{name}: {p[:120]}")
    return sorted(leaks), sorted(harness)


def apply_facts(uses, project):
    """For a KC session: edits made outside `brass apply`, and the thinking spent before the first edit of any kind."""
    src = str((project / "src").resolve())
    bypass, first, applies = [], None, 0
    for name, inp, thinking in uses:
        cmd = inp.get("command", "") if name == "Bash" else ""
        is_apply = "brass apply" in cmd
        is_editor = name in EDITORS and str(Path(inp.get("file_path", "/")).resolve()).startswith(src)
        is_shell_write = bool(cmd) and "src/" in cmd and bool(re.search(r"(?<![0-9&])>|\btee\b|sed -i|open\([^)]*['\"]w", cmd))
        applies += is_apply
        if is_editor or is_shell_write:
            bypass.append(f"{name}: {inp.get('file_path') or cmd[:100]}")
        if first is None and (is_apply or is_editor or is_shell_write):
            first = thinking
    return {"apply_calls": applies, "edits_outside_apply": bypass, "thinking_before_first_edit": first}


def score(task, project, lang, label):
    out = {}
    for t in tables(task, label):
        j = project.parent / f"eval-{t}"
        r = sh([sys.executable, str(RERUN / "tools" / TASKS[task]["evaluator"]), str(project), lang, str(TASKS[task]["cases"] / t), "--json", str(j)])
        try:
            cases = json.loads(j.read_text())["cases"]
            out[t] = {"held": sum(c["holds"] for c in cases), "total": len(cases), "could_not_run": sum(1 for c in cases if c.get("run") != "ran"),
                      "failed": [c["id"] for c in cases if not c["holds"]],
                      "by_kind": {k: [sum(c["holds"] for c in cases if c.get("kind") == k), sum(1 for c in cases if c.get("kind") == k)]
                                  for k in sorted({c.get("kind") for c in cases})}}
        except (OSError, json.JSONDecodeError, KeyError):
            out[t] = {"error": (r.stdout + r.stderr)[-300:]}
    return out


def collect(run_id):
    pre = json.loads((run_dir(run_id) / "preflight.json").read_text())
    seen = {}
    for t, l in every():
        sm = rec(run_id, t, l) / "summary.json"
        if sm.exists():
            seen[json.loads(sm.read_text()).get("session_id")] = f"{t}/{l}"
    for task, label in every():
        st = state(run_id, task, label)
        if st == "ended-without-result":
            print(f"{task}/{label}: ended without a result; see {build_dir(run_id, task) / label / 'launch.log'} and stderr.txt")
            continue
        if st != "finished":
            continue
        size, arm = size_arm(task, label)
        s, r = build_dir(run_id, task) / label, rec(run_id, task, label)
        r.mkdir(parents=True, exist_ok=True)
        res = json.loads((s / "result.json").read_text())
        for f in ("prompt.md", "result.json", "stderr.txt", "launch.log", "started", "env-before.txt", "env-session.txt"):
            if (s / f).exists():
                shutil.copy(s / f, r / f)
        for d in ("project", "brass-logs"):
            if (s / d).exists():
                if (r / d).exists():
                    shutil.rmtree(r / d)
                shutil.copytree(s / d, r / d, ignore=shutil.ignore_patterns("__pycache__"))
        t = transcript_for(res.get("session_id", ""), s / "project")
        if t:
            shutil.copy(t, r / "transcript.jsonl")
        lang = "python" if arm == "P" else "brass"
        mu = res.get("modelUsage", {})
        manifest = json.loads((run_dir(run_id) / task / "manifest.json").read_text()).get(label, {})
        uses = tool_uses(r / "transcript.jsonl") if t else []
        leaks, harness = paths_outside(uses, s) if t else (["transcript not found"], [])
        sid = res.get("session_id")
        summary = {
            "run_id": run_id, "task": task, "label": label, "size": size, "arm": arm, "lang": lang,
            "started": (s / "started").read_text() if (s / "started").exists() else None, "collected": now(),
            "provenance": {"model": MODEL, "effort": EFFORT, "cap": CAP, "claude_version": pre.get("claude_version"), "git_head": pre.get("git_head"),
                           "tool_hash": pre.get("tool_hash"), "prompt_sha256": manifest.get("prompt_sha256"), "prompt_chars": manifest.get("prompt_chars"),
                           "freeze": pre.get("freeze")},
            "session_id": sid, "own_instance": bool(sid) and sid != pre.get("parent_session_id") and sid not in seen,
            "shares_id_with": seen.get(sid), "is_error": res.get("is_error"), "subtype": res.get("subtype"),
            "terminal_reason": res.get("terminal_reason"), "api_error_status": res.get("api_error_status"),
            "num_turns": res.get("num_turns"), "duration_ms": res.get("duration_ms"), "cost_usd": res.get("total_cost_usd"),
            "models": list(mu.keys()), "model_ok": list(mu.keys()) == [MODEL],
            "thinking_tokens": sum(v.get("thinkingTokens", 0) for v in mu.values()),
            "output_tokens": sum(v.get("outputTokens", 0) for v in mu.values()),
            "cache_read": sum(v.get("cacheReadInputTokens", 0) for v in mu.values()),
            "cache_write": sum(v.get("cacheCreationInputTokens", 0) for v in mu.values()),
            "input_uncached": sum(v.get("inputTokens", 0) for v in mu.values()),
            "transcript_saved": t is not None, "leaks": leaks, "harness_paths": harness,
            "telemetry": telemetry.transcript(r / "transcript.jsonl") if t else None,
            "brass_log_verbs": telemetry.brass_log(r) if arm != "P" else None,
            "scores": score(task, s / "project", lang, label),
        }
        if arm == "KC":
            summary.update(apply_facts(uses, s / "project"))
            c = sh([str(s / "project" / "bin" / "brass"), "check"], env={**os.environ, "BRASS_NO_LOG": "1"})
            summary["final_check"] = c.stdout.strip().splitlines()[-1] if c.stdout else c.stderr[-200:]
            summary["check_warnings"] = [l for l in c.stdout.splitlines() if "⚠" in l or "✗" in l]
        if sid:
            seen[sid] = f"{task}/{label}"
        (r / "summary.json").write_text(json.dumps(summary, indent=1))
        main_t = tables(task, label)[0]
        sc = summary["scores"].get(main_t, {})
        print(f"{task}/{label}: collected; {main_t} {sc.get('held')}/{sc.get('total')}; own instance {summary['own_instance']}; "
              f"leaks {len(leaks)}; model_ok {summary['model_ok']}" + (f"; edits outside apply {len(summary['edits_outside_apply'])}" if arm == "KC" else ""))
    return status(run_id)


def retry(run_id, task, label):
    if task not in TASKS or label not in labels(task):
        sys.exit(f"no session {task}/{label}")
    r, s = rec(run_id, task, label), build_dir(run_id, task) / label
    st = state(run_id, task, label)
    failed = st == "ended-without-result" or (st == "collected" and json.loads((r / "summary.json").read_text()).get("is_error"))
    if not failed:
        sys.exit(f"{task}/{label} is {st}; only a harness failure is retried. A finished session is a result, whatever it scored.")
    if (r / "attempt-1").exists():
        sys.exit(f"{task}/{label} was already retried once; record it as failed and go on")
    keep = r / "attempt-1"
    keep.mkdir(parents=True)
    for f in ("prompt.md", "result.json", "stderr.txt", "launch.log", "started", "summary.json", "transcript.jsonl", "env-before.txt", "env-session.txt"):
        for src in (s / f, r / f):
            if src.exists() and not (keep / f).exists():
                shutil.copy(src, keep / f)
    for f in ("summary.json", "result.json", "transcript.jsonl"):
        (r / f).unlink(missing_ok=True)
    for f in ("result.json", "pid", "started"):
        (s / f).unlink(missing_ok=True)
    b = sh([sys.executable, str(RERUN / "tools" / TASKS[task]["builder"]), str(build_dir(run_id, task)), "--cap", str(CAP), "--tag", f"{run_id}/{task}", spec_of(task, label)])
    if b.returncode != 0:
        sys.exit(b.stderr)
    shutil.copy(build_dir(run_id, task) / "manifest.json", run_dir(run_id) / task / "manifest.json")
    print(f"{task}/{label}: retried, pid {start(run_id, task, label)}; attempt 1 kept in {keep}")
    return 0


def status(run_id):
    for task, label in every():
        st = state(run_id, task, label)
        extra = ""
        sm = rec(run_id, task, label) / "summary.json"
        if sm.exists():
            j = json.loads(sm.read_text())
            main_t = tables(task, label)[0]
            c = j["scores"].get(main_t, {})
            extra = (f"{main_t[:-5]} {c.get('held')}/{c.get('total')}  turns {j['num_turns']}  ${j['cost_usd']:.2f}  think {j['thinking_tokens']}"
                     f"  own {j['own_instance']}  leaks {len(j['leaks'])}" + (f"  bypass {len(j['edits_outside_apply'])}" if j["arm"] == "KC" else ""))
        print(f"{task}/{label:<10} {st:<22} {extra}")
    return 0


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, run_id, rest = argv[0], argv[1], argv[2:]
    if not re.fullmatch(r"[0-9a-z-]+", run_id):
        sys.exit("run id: lowercase letters, digits, and dashes")
    return {"preflight": preflight, "build": build, "launch": launch, "wait": wait, "collect": collect, "retry": retry, "status": status}[cmd](run_id, *rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
