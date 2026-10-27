#!/usr/bin/env python3
"""A Python stand-in for the three keelc commands lean sessions use: `show`, `show --body`, and `apply`.

usage: pytool show                      every module's declarations: the source without function bodies, numbered
       pytool show --body <m> [<m> …]   the whole files of several modules, numbered
       pytool apply <<'PATCH' … PATCH   every edit, across files, in one call; all or nothing; then compiles what changed

The project root is PYTOOL_PROJECT (default: the parent of bin/); modules are src/desk/*.py. No check beyond compiling:
the session can already run python3.
"""
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PYTOOL_PROJECT", Path(__file__).resolve().parents[1]))
SRC = ROOT / "src" / "desk"


def modules():
    return sorted(p for p in SRC.glob("*.py") if p.name != "__init__.py")


def hidden_lines(text):
    """Line numbers inside function bodies, docstrings kept; a one-line body (`...`) stays."""
    hide = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            if body and body[0].lineno > node.lineno:
                hide.update(range(body[0].lineno, node.end_lineno + 1))
    return hide


def numbered(lines, keep):
    return [f"{n:4}  {l}" for n, l in enumerate(lines, 1) if n in keep]


def show(body_mods):
    out = []
    if body_mods:
        for m in body_mods:
            p = SRC / f"{m}.py"
            if not p.is_file():
                out.append(f"show        ✗ no module {m} (modules: {' '.join(q.stem for q in modules())})"); continue
            lines = p.read_text().split("\n")
            out += [f"file        src/desk/{p.name}   {len(lines)} lines"] + numbered(lines, range(1, len(lines) + 1)) + [""]
        return out
    for p in modules():
        text = p.read_text(); lines = text.split("\n")
        try:
            hide = hidden_lines(text)
        except SyntaxError as e:
            out += [f"file        src/desk/{p.name}   does not parse: line {e.lineno}: {e.msg}", ""]; continue
        keep = [n for n in range(1, len(lines) + 1) if n not in hide and lines[n - 1].strip()]
        out += [f"file        src/desk/{p.name}   declarations, {len(keep)} of {len(lines)} lines   (`show --body {p.stem}` for the whole file)"]
        out += numbered(lines, set(keep)) + [""]
    return out


def parse_patch(text):
    blocks, lines, i = [], text.split("\n"), 0
    def take_until(marker):
        nonlocal i
        out = []
        while i < len(lines) and lines[i].strip() != marker:
            out.append(lines[i]); i += 1
        if i >= len(lines):
            raise ValueError(f"block not closed: expected {marker}")
        return "\n".join(out)
    while i < len(lines):
        l = lines[i].strip()
        if not l:
            i += 1; continue
        m = re.match(r"@@@\s+(edit|new)\s+(\S+)$", l)
        if not m:
            raise ValueError(f"patch line {i + 1}: expected `@@@ edit <file>` or `@@@ new <file>`, got: {l[:60]}")
        kind, path = m.group(1), m.group(2); i += 1
        if kind == "new":
            content = take_until("@@@ end"); i += 1
            blocks.append(("new", path, content)); continue
        if i >= len(lines) or lines[i].strip() != "@@@ find":
            raise ValueError(f"patch line {i + 1}: `@@@ edit {path}` must be followed by `@@@ find`")
        i += 1
        find = take_until("@@@ replace"); i += 1
        repl = take_until("@@@ end"); i += 1
        blocks.append(("edit", path, find, repl))
    if not blocks:
        raise ValueError("the patch has no blocks")
    return blocks


def apply(text):
    try:
        blocks = parse_patch(text)
    except ValueError as e:
        return [f"apply       ✗ cannot read the patch: {e}", "nothing was written. The format:",
                "  @@@ edit <file>      then @@@ find, the exact text (once in the file), @@@ replace, the new text, @@@ end",
                "  @@@ new <file>       then the whole file, then @@@ end"]
    state, out, bad = {}, [], 0
    for n, b in enumerate(blocks, 1):
        path = (ROOT / b[1]).resolve()
        if ROOT.resolve() not in path.parents:
            out.append(f"  block {n:<3} ✗ {b[1]}: outside the project"); bad += 1; continue
        if b[0] == "new":
            if path.exists() or b[1] in state:
                out.append(f"  block {n:<3} ✗ new {b[1]}: the file exists; use `@@@ edit`"); bad += 1; continue
            state[b[1]] = b[2].rstrip("\n") + "\n"
            out.append(f"  block {n:<3} ✓ new {b[1]}  ({b[2].count(chr(10)) + 1} lines)"); continue
        cur = state[b[1]] if b[1] in state else (path.read_text() if path.is_file() else None)
        if cur is None:
            out.append(f"  block {n:<3} ✗ edit {b[1]}: no such file"); bad += 1; continue
        k = cur.count(b[2]) if b[2] else 0
        if k != 1:
            first = next((x.strip() for x in b[2].split("\n") if x.strip()), "")
            hits = [str(i) for i, x in enumerate(cur.split("\n"), 1) if first and first in x][:5]
            out.append(f"  block {n:<3} ✗ edit {b[1]}: the find text occurs {k} times, not once"
                       + (f"; its first line appears at line {', '.join(hits)}" if hits else "; its first line appears nowhere")); bad += 1
            continue
        line = cur[:cur.index(b[2])].count("\n") + 1
        state[b[1]] = cur.replace(b[2], b[3], 1)
        out.append(f"  block {n:<3} ✓ edit {b[1]}:{line}  ({b[2].count(chr(10)) + 1} lines → {b[3].count(chr(10)) + 1})")
    if bad:
        return [f"apply       ✗ {bad} of {len(blocks)} blocks do not match; nothing was written"] + out \
               + ["next        fix the blocks marked ✗ (copy the find text from the file exactly) and run `pytool apply` again"]
    for rel, content in state.items():
        p = ROOT / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    errs = []
    for rel in state:
        if rel.endswith(".py"):
            try:
                compile(state[rel], rel, "exec")
            except SyntaxError as e:
                errs.append(f"  ✗ {rel}:{e.lineno}: {e.msg}")
    head = [f"apply       ✓ {len(blocks)} blocks written to {len(state)} files"] + out + [""]
    if errs:
        return head + [f"compile     ✗ {len(errs)} file(s) do not compile"] + errs
    return head + [f"compile     ✓ {len(state)} files compile"]


def main(argv):
    if argv[:1] == ["show"]:
        rest = argv[1:]
        return show([a for a in rest if a != "--body"] if "--body" in rest else [])
    if argv[:1] == ["apply"]:
        return apply(sys.stdin.read())
    return [__doc__.split("\n\n")[1]]


if __name__ == "__main__":
    print("\n".join(main(sys.argv[1:])))
