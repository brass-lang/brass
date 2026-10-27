#!/usr/bin/env python3
"""Respell a Keel tree from before C25 into current Brass. Spelling only; no behavior changes.

usage: respell.py <old-tree> <new-tree>      copies <old-tree> to <new-tree>, respelling every .keel file to .brass

The five changes, each a decided entry in brass-changes.md:
  C25  `partial fn` -> `fn`                    `-> Outcome<T>` alone marks a function that can fail
  C31  `private interface` -> `private`
  C33  a bare field name in a type's `where` -> `it.field`   (body `any`/`all ... where` is untouched)
  C34  `<type line> }` + `where <cond> has <f>: <T>` -> `<type line>,` + `<f>: <T> when <cond> }`
  C41  `.keel` -> `.brass` in file names and in comments that name a file
Any other old form is reported, not guessed: the script exits 1 and names the line.
"""
import re
import shutil
import sys
from pathlib import Path

KEYWORDS = {"and", "or", "not", "in", "is", "to", "it", "true", "false", "None", "length_"}
IDENT = re.compile(r"(?<![\w.])([a-z_][a-z0-9_]*)(?![\w(])")
QUALIFIED = re.compile(r"(?<![\w.])[a-z_][a-z0-9_]*\.[a-z_]")   # a module-qualified name outside a set literal: not a field
OLD_FORMS = [(re.compile(r"\bpartial\b"), "partial"), (re.compile(r"\bprivate interface\b"), "private interface"),
             (re.compile(r"\bhas\s+[a-z_]+\s*:"), "has"), (re.compile(r"^\s*data\s"), "data"),
             (re.compile(r"\bSome\("), "Some"), (re.compile(r"\bfrom\s+\""), "data from")]


class Unsupported(Exception):
    pass


def it_fields(cond: str) -> str:
    """Prefix every bare field name in a refinement condition with `it.`; set literals {...} are left alone.
    A qualified name outside a set literal (`limits.ceiling`) is ambiguous between a constant and a field path and is
    refused; the verified inputs hold none."""
    out, depth, i = [], 0, 0
    for part in re.split(r"([{}])", cond):
        if part == "{":
            depth += 1
        elif part == "}":
            depth -= 1
        elif depth == 0:
            if QUALIFIED.search(part):
                raise Unsupported(f"qualified name in a type condition: {cond.strip()}")
            part = IDENT.sub(lambda m: m.group(1) if m.group(1) in KEYWORDS else "it." + m.group(1), part)
        out.append(part)
    return "".join(out)


def where_spans(code: str) -> str:
    """Respell every `where` in a line of a type declaration. Inside braces a condition ends at its field's `,` or `}`."""
    out, i = [], 0
    for m in re.finditer(r"\bwhere\b ", code):
        if m.start() < i:
            continue
        depth = code[: m.start()].count("{") - code[: m.start()].count("}")
        j, d = m.end(), 0
        if depth > 0:
            while j < len(code) and not (d == 0 and code[j] in ",}"):
                d += {"{": 1, "}": -1}.get(code[j], 0)
                j += 1
        else:
            j = len(code)
        out.append(code[i:m.end()] + it_fields(code[m.end():j]))
        i = j
    return "".join(out) + code[i:]


def type_where(line: str, in_type: bool) -> str:
    """Respell a type declaration line, a `where` continuation line, or a line inside a type's open braces."""
    code, hash_, comment = line.partition("  #")
    s = code.lstrip()
    if not (in_type or s.startswith("type ") or s.startswith("where ")) or re.search(r"\b(any|all)\b[^#]*\bwhere\b", code):
        return line
    return where_spans(code) + (hash_ + comment if hash_ else "")


def respell(text: str, name: str, problems: list) -> str:
    lines = text.split("\n")
    out, open_type = [], 0
    for n, line in enumerate(lines):
        line = re.sub(r"\bpartial fn\b", "fn", line)
        line = re.sub(r"\bprivate interface\b", "private", line)
        line = re.sub(r"(\w)\.keel\b", r"\1.brass", line)
        m = re.match(r"^(\s*)where (.+?) has ([a-z_]+): (.+?)\s*$", line)
        if m and out and out[-1].rstrip().endswith("}"):
            indent, cond, field, ftype = m.groups()
            prev = out[-1].rstrip()
            try:
                out[-1] = prev[:-1].rstrip() + ","
                out.append(f"{indent}  {field}: {ftype} when {it_fields(cond)} }}")
            except Unsupported as e:
                problems.append(f"{name}:{n + 1}: {e}")
                out[-1] = prev
                out.append(line)
            continue
        in_type = open_type > 0
        code = line.split("#", 1)[0]
        if code.lstrip().startswith("type ") or in_type:
            open_type = max(0, open_type + code.count("{") - code.count("}"))
        try:
            out.append(type_where(line, in_type) if re.search(r"\bwhere\b", code) else line)
        except Unsupported as e:
            problems.append(f"{name}:{n + 1}: {e}")
            out.append(line)
    for n, line in enumerate(out, 1):
        code = line.split("#", 1)[0]
        for pat, label in OLD_FORMS:
            if pat.search(code):
                problems.append(f"{name}:{n}: old form `{label}` left: {line.strip()}")
    return "\n".join(out)


def main(src: str, dst: str) -> int:
    src_p, dst_p = Path(src), Path(dst)
    if dst_p.exists():
        sys.exit(f"{dst} exists; respell writes a fresh tree")
    problems = []
    for f in sorted(src_p.rglob("*")):
        rel = f.relative_to(src_p)
        target = dst_p / (str(rel)[: -len(".keel")] + ".brass" if f.suffix == ".keel" else rel)
        if f.is_dir():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix == ".keel":
            target.write_text(respell(f.read_text(), str(rel), problems))
        else:
            shutil.copy2(f, target)
    for p in problems:
        print(p)
    print(f"{dst}: {sum(1 for _ in dst_p.rglob('*.brass'))} files respelled, {len(problems)} old forms left")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
