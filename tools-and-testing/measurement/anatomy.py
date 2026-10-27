#!/usr/bin/env python3
"""Token anatomy of trial sessions, by request id, from the harness transcripts.

usage: anatomy.py <tasks-dir> LABEL=agentId [LABEL=agentId ...] [--first-baseline N]

Per session: first-call context, final context, own text (non-thinking output), thinking,
tool results in context (final - first - own text), attributable (tool + own + thinking),
model calls, cumulative context processed, fresh (uncached) share, tool-result bytes,
final answer characters. One request counted once; the last logged line of a request carries
its full output figure. The harness summary undercounts; this counts each request once from the log.
"""
import json
import sys
from collections import OrderedDict
from pathlib import Path


def anatomy(path):
    reqs = OrderedDict()
    toolbytes = 0
    last_text = ""
    for line in open(path):
        o = json.loads(line)
        m = o.get("message") or {}
        if o.get("type") == "assistant" and m.get("usage"):
            reqs[o.get("requestId")] = m["usage"]
            for c in m.get("content", []):
                if isinstance(c, dict) and c.get("type") == "text":
                    last_text = c["text"]
        elif o.get("type") == "user" and not isinstance(m.get("content"), str):
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    cont = c.get("content")
                    toolbytes += len(cont) if isinstance(cont, str) else sum(len(x.get("text", "")) for x in cont if isinstance(x, dict))
    us = list(reqs.values())
    ctx = [u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in us]
    out = sum(u.get("output_tokens", 0) for u in us)
    think = sum((u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0 for u in us)
    fresh = sum(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) for u in us)
    own = out - think
    tool = ctx[-1] - ctx[0] - own
    return dict(first=ctx[0], final=ctx[-1], own=own, think=think, tool=tool, attributable=tool + own + think,
                calls=len(us), cumulative=sum(ctx), fresh=fresh, toolbytes=toolbytes, answer_chars=len(last_text),
                answer_words=len(last_text.split()))


def main(argv):
    tasks = Path(argv[0])
    pairs = [a.split("=", 1) for a in argv[1:] if "=" in a]
    rows = [(label, anatomy(tasks / f"{aid}.output")) for label, aid in pairs]
    cols = ["first", "final", "tool", "own", "think", "attributable", "calls", "cumulative", "fresh", "toolbytes", "answer_words"]
    print(f"{'session':10}" + "".join(f"{c:>13}" for c in cols))
    for label, r in rows:
        print(f"{label:10}" + "".join(f"{r[c]:>13}" for c in cols))


if __name__ == "__main__":
    main(sys.argv[1:])
