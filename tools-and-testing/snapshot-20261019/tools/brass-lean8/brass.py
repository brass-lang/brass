#!/usr/bin/env python3
"""brass proxy: `check` (structure, level 1), `info`, `propagate`, `changes`, `run`, `show` over a Brass project, from its text.

No proofs are run. Tier labels follow the declared form. Every invocation is appended to a log
outside the project so reads through the tool can be measured.

  brass info                         the system map: entry points, grants, limits, modules
  brass info --names                 every module with its declaration names, one line per module
  brass info --holds                 every entry point with the accesses it holds
  brass info <module>                a module's interface (tiers once, as a legend)
  brass info <module> --names        that module's imports, declaration names and kinds
  brass info <module>.<name>         one declaration: text, holds, used_by, body references
  brass info <m>.<n> --if-changed    add the transitive impact set, grouped by module
  brass info <m>.<n> --established-by  each caller, the call line, and the enclosing `if` tests on its path
  brass info <m>.<n> --at <line>     facts in scope at a body line: bindings, narrowings, holds, what a call there needs
  brass info <m>.<n> --effects       an entry point's effects in body order, each with the tests guarding it
  brass info --if "<module>.<name> = <new declaration text>"
                                     static what-if: everything that references the declaration, with
                                     every where/before/after clause to re-check, marked "names it
                                     directly" or "through field <f>" (no proof is run)
  brass propagate <module>           after editing a module's interface: every import
                                     line that follows, every call and record literal that now lacks a
                                     value, each with a @@hole of the needed type. --write applies it.
  brass changes                      what changed against the baseline tree, and the places to inspect
  brass review <module>              what a human should read about this module's edit: authority first,
                                     then contracts, types, bodies last; holes remaining
  brass info --forms                 the language forms this project uses, one example each, from the source
  brass verify <query id>            re-run a cited query and say whether its answer still holds
  brass run <m>.<fn> <arg> ...       evaluate a total fn on literal arguments (Brass syntax, one shell word
                                     each); reports the result, its return type, and each after clause
  brass check                        level 1, structure: names, pairing, call arity, `?` only under Outcome, holes, typed lets;
                                     when clean, a summary of each entry point in check order: refusals, calls, states
  brass check --examples             evaluate every `example` clause in the interfaces
  brass check --scenarios            run scenarios/*.json: an entry point against a scripted host; compare result and call trace
  brass check --scenario <file> …    the same for the named scenario files
  brass show <module>                the whole source file, numbered
  brass show <module>:<a>-<b>        lines a to b of that file
  brass show <module>.<name>         one declaration's interface lines and body, numbered
  brass show system                  system.brass
  brass help

Several targets may be given in one call: brass info tickets.refund control.refund_ticket
<module> may be written `park.tickets` or `tickets`.
Project: the directory above bin/, or $BRASS_PROJECT when set.
"""
import os
import re
import sys
import time
sys.dont_write_bytecode = True
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = Path(os.environ["BRASS_PROJECT"]).resolve() if os.environ.get("BRASS_PROJECT") else HERE.parents[1]
def _src_dir():
    """The system's source directory: $BRASS_SRC, else the one directory under src/ holding .brass files."""
    # Known gap: one source folder only. A project whose modules span folders (examples/refund: src/payments and
    # src/support) reports every name imported from the other folder as undeclared. Every trial tree has one folder;
    # REL and the module-name prefixing below assume it, so lifting this touches about 40 sites.
    if os.environ.get("BRASS_SRC"):
        return ROOT / "src" / os.environ["BRASS_SRC"]
    dirs = sorted(d for d in (ROOT / "src").iterdir() if d.is_dir()) if (ROOT / "src").is_dir() else []
    with_keel = [d for d in dirs if any(d.glob("*.brass")) or any(d.glob("*.keel"))]
    return (with_keel or dirs or [ROOT / "src" / "park"])[0]


SRC = _src_dir()
MODS_BY_NAME = {}                        # filled by World; lets a refinement resolve in its own module
REL = f"src/{SRC.name}"
SYSTEM = ROOT / "src" / "system.brass"
if not SYSTEM.exists() and (ROOT / "src" / "system.keel").exists():
    SYSTEM = ROOT / "src" / "system.keel"   # the frozen trial trees keep the old extension
LOG = ROOT.parent / "brass-logs" / (ROOT.name + ".log")
BANNER = "brass (proxy: static rendering from source, no proofs run; tiers follow the declared form)"

KEYWORDS = {"module", "import", "as", "interface", "private", "body", "type", "fn",
            "unbounded", "before", "after", "where", "in", "to", "and", "or", "it", "access",
            "allow", "machine", "states", "initial", "enters", "projects", "const", "let", "if",
            "then", "else", "for", "loop", "break", "not", "is", "example", "any", "all"}              # system-file words are names in a module (C10(d))
BUILTINS = {"Int", "Int8", "Int16", "Int32", "Int64", "Text", "Bool", "Done", "Ok", "Err", "Outcome", "Maybe", "None",
            "Array", "Set", "FailureCode", "true", "false", "result", "length", "attempt"}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
DECL_START = re.compile(r"^  (?:partial )?(type|const|data|machine|access|fn) ([A-Za-z_][A-Za-z0-9_]*)")   # `partial` and `data` read only to reject them (C25, C32)
BODY_FN = re.compile(r"^  fn ([A-Za-z_][A-Za-z0-9_]*)\(")
ALLOW = re.compile(r"^    allow ([A-Za-z_][A-Za-z0-9_]*)\(")
PARAM = re.compile(r"([a-z_][A-Za-z0-9_]*):\s*([A-Za-z_][A-Za-z0-9_.]*)")
FIELD = re.compile(r"([a-z_][A-Za-z0-9_]*):\s*([A-Za-z_][A-Za-z0-9_.]*)")


class Decl:
    def __init__(self, module, name, kind, section):
        self.module, self.name, self.kind, self.section = module, name, kind, section
        self.lines = []          # (lineno, text) interface text
        self.body = []           # (lineno, text)
        self.params = {}
        self.refs = set()
        self.fields = {}         # record types: field name -> type text
        self.conditional = {}    # `when` fields (C34): name -> (controlling field, [states], type text)
        self.wrote_partial = False
        self.wrote_data = False

    @property
    def key(self):
        return (self.module, self.name)

    @property
    def fails(self):
        """A fn that can fail: it returns Outcome (C25: the return type is the only mark)."""
        return self.kind == "fn" and signature(self).split("->", 1)[-1].strip().startswith("Outcome<")

    @property
    def short(self):
        return f"{self.module.split('.')[-1]}.{self.name}"


class Module:
    def __init__(self, path):
        self.path = path
        self.text = path.read_text().splitlines()
        self.name = next(l.split()[1] for l in self.text if l.startswith("module "))
        self.version = ""  # v0.2: modules carry no version (review E40)
        self.old_private = None
        self.imports = [(l.split()[1], "", l.split()[3]) for l in self.text if l.startswith("import ")]  # v0.2: import <name> as <alias>
        self.aliases = {a: m for m, _, a in self.imports}
        idx = {}
        for i, l in enumerate(self.text):
            s = l.strip()
            if s == "private interface":                 # the form before C31: still read, rejected by check
                s, self.old_private = "private", i + 1
            if s in ("interface", "private", "body") and s not in idx:
                idx[s] = i
        self.i_iface, self.i_priv, self.i_body = idx["interface"], idx.get("private"), idx["body"]
        iface_end = self.i_priv if self.i_priv is not None else self.i_body
        self.interface = list(enumerate(self.text[self.i_iface + 1:iface_end], start=self.i_iface + 2))
        self.private = list(enumerate(self.text[self.i_priv + 1:self.i_body], start=self.i_priv + 2)) if self.i_priv is not None else []
        self.body_lines = list(enumerate(self.text[self.i_body + 1:], start=self.i_body + 2))
        self.decls = {}
        self._parse(self.interface, "interface")
        self._parse(self.private, "private")
        self._parse_bodies()

    def _parse(self, lines, section):
        cur = cur_access = None
        depth = 0
        for no, l in lines:
            m = DECL_START.match(l)
            if m:
                cur = Decl(self.name, m.group(2), "data" if m.group(1) == "const" else m.group(1), section)   # one internal kind for a constant
                cur.wrote_data = m.group(1) == "data"
                self.decls[cur.name] = cur
                cur.lines.append((no, l))
                cur.wrote_partial = l.startswith("  partial ")
                cur_access = cur if cur.kind == "access" else None
                if cur.kind == "fn":
                    cur.params = dict(PARAM.findall(l.split("->")[0]))
                depth = paren_depth(l)
                continue
            am = ALLOW.match(l)
            if am and cur_access is not None:
                sub = Decl(self.name, f"{cur_access.name}.{am.group(1)}", "allow", section)
                sub.params = dict(PARAM.findall(l.split("->")[0]))
                self.decls[sub.name] = sub
                sub.lines.append((no, l))
                cur_access.lines.append((no, l))
                cur = sub
                depth = paren_depth(l)
                continue
            if cur is not None:
                cur.lines.append((no, l))
                if cur.kind == "allow" and cur_access is not None:
                    cur_access.lines.append((no, l))
                if cur.kind in ("fn", "allow") and depth > 0:      # the signature is still open (C28)
                    cur.params.update(dict(PARAM.findall(l.split("->")[0])))
                    depth += paren_depth(l)
        for d in self.decls.values():
            if d.kind == "type":
                text = " ".join(strip_comment(l) for _, l in d.lines)
                rhs = text.split("=", 1)[1].strip() if "=" in text else ""
                if rhs.startswith("{"):
                    for part in record_parts(rhs):
                        fm = re.match(r"\s*([a-z_]\w*)\s*:\s*(.+?)\s*$", part)
                        if not fm:
                            continue
                        wm = re.match(r"(.+?)\s+when\s+(.+)$", fm.group(2))
                        if wm:
                            cm = re.match(r"it\.(\w+)\s+in\s+\{([^}]*)\}\s*$", wm.group(2).strip())
                            d.conditional[fm.group(1)] = (cm.group(1) if cm else None, [x.strip() for x in cm.group(2).split(",")] if cm else [],
                                                          wm.group(1).strip())
                        else:
                            tm = re.match(r"([A-Za-z_][\w.]*)", fm.group(2))
                            if tm:
                                d.fields[fm.group(1)] = tm.group(1)
                elif "{" in text:
                    inner = text.split("{", 1)[1].split("}", 1)[0]
                    d.fields = dict(FIELD.findall(inner))

    def _parse_bodies(self):
        cur = None
        for no, l in self.body_lines:
            m = BODY_FN.match(l)
            if m:
                cur = self.decls.get(m.group(1))
                if cur is None:
                    cur = Decl(self.name, m.group(1), "fn", "body")
                    self.decls[m.group(1)] = cur
                cur.body.append((no, l))
                continue
            if cur is not None:
                cur.body.append((no, l))


def record_parts(rhs):
    """The top-level comma-separated parts inside a record type's outer braces."""
    depth, parts, cur = 0, [], ""
    for ch in rhs:
        if ch in "{([":
            depth += 1
            if depth == 1 and ch == "{":
                continue
        elif ch in "})]":
            depth -= 1
            if depth == 0:
                break
        if ch == "," and depth == 1:
            parts.append(cur); cur = ""
        else:
            cur += ch
    return parts + [cur]


def strip_comment(l):
    """The line up to its first `#` outside a text literal."""
    quoted = False
    for i, ch in enumerate(l):
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            return l[:i]
    return l


def paren_depth(l):
    """Open minus closed parentheses on a line, comments and text literals ignored."""
    s = strip_strings(strip_comment(l))
    return s.count("(") - s.count(")")


def resolve(mod, all_decls, token, params):
    parts = token.split(".")
    head = parts[0]
    found = set()
    if head in KEYWORDS or head in BUILTINS:
        return found
    if head in mod.aliases and len(parts) > 1:
        m = mod.aliases[head]
        if (m, parts[1]) in all_decls:
            found.add((m, parts[1]))
            if len(parts) > 2 and (m, f"{parts[1]}.{parts[2]}") in all_decls:
                found.add((m, f"{parts[1]}.{parts[2]}"))
        return found
    if head in mod.decls:
        found.add((mod.name, head))
        if len(parts) > 1 and (mod.name, f"{head}.{parts[1]}") in all_decls:
            found.add((mod.name, f"{head}.{parts[1]}"))
        return found
    if head in params and len(parts) > 1:
        ak = access_key(mod, all_decls, params[head])
        if ak is not None:
            m, acc = ak
            found.add((m, acc))
            if (m, f"{acc}.{parts[1]}") in all_decls:
                found.add((m, f"{acc}.{parts[1]}"))
    return found


def access_key(mod, all_decls, text):
    """The access a parameter type holds: the access itself, or one a refinement narrows (`type P = a.Pay where …`)."""
    k = type_key(mod, all_decls, text)
    for _ in range(4):
        if k is None or all_decls[k].kind == "access":
            return k
        d = all_decls[k]
        rm = re.match(r"\s*type\s+\w+\s*=\s*([A-Za-z_][\w.]*)\s+where\b", strip_comment(d.lines[0][1])) if d.kind == "type" else None
        if rm is None:
            return None
        k = type_key(MODS_BY_NAME.get(d.module, mod), all_decls, rm.group(1))
    return None


def type_key(mod, all_decls, text):
    """Resolve a type name as written in `mod` to a declaration key, or None."""
    parts = text.split(".")
    if len(parts) == 2 and parts[0] in mod.aliases:
        k = (mod.aliases[parts[0]], parts[1])
    else:
        k = (mod.name, parts[0])
    return k if k in all_decls else None


STRING = re.compile(r'"[^"]*"')


def strip_strings(l):
    return STRING.sub('""', l)


def scopes_of(d):
    """For each body line, the locally bound names in scope there: parameters everywhere; a `let` on later
    lines of its block; a loop variable inside its loop. A binding ends when a line appears at a shallower
    indentation (or, for a loop variable, at the loop's own indentation)."""
    scope = {}
    stack = []                                   # (indent, name); the binding hides the name on lines with indent >= its own
    for no, l in d.body:
        st = strip_comment(l)
        if not st.strip():
            continue
        ind = len(st) - len(st.lstrip())
        stack = [(i, n) for i, n in stack if i <= ind]
        scope[no] = set(d.params) | {n for _, n in stack}
        m = re.search(r"\blet\s+([a-z_][A-Za-z0-9_]*)\s*:", st)
        if m:
            stack.append((ind, m.group(1)))
        m = re.search(r"\bfor\s+([a-z_][A-Za-z0-9_]*)\s+in\b", st)
        if m:
            stack.append((ind + 1, m.group(1)))
    return scope


BINDING = re.compile(r"\b(?:let\s+([a-z_][A-Za-z0-9_]*)\s*:|for\s+([a-z_][A-Za-z0-9_]*)\s+in\b)")


def tokens_resolving(mod, all_decls, d, line, hidden):
    """(token, position, keys) for each identifier on the line that names a declaration.
    The name a `let` or `for` binds is a declaration of a local, not a use; its initializer still resolves."""
    out = []
    clean = strip_comment(strip_strings(line))
    bound_at = {m.start(1) if m.group(1) else m.start(2) for m in BINDING.finditer(clean)}
    for m in IDENT.finditer(clean):
        tok = m.group(0)
        head = tok.split(".")[0]
        if m.start() in bound_at:
            continue
        if head in hidden and not (head in d.params and "." in tok):
            continue
        keys = resolve(mod, all_decls, tok, d.params)
        if keys:
            out.append((tok, m.start(), keys))
    return out


STD = {"std.text": {"of"}}     # the standard library's decided names (spec 8.1, C4); anything else in std is not declared


def unresolved_in(mod, line):
    """Qualified names whose alias is an import but whose name that module does not declare."""
    out = []
    for m in IDENT.finditer(strip_comment(strip_strings(line))):
        parts = m.group(0).split(".")
        if len(parts) > 1 and parts[0] in mod.aliases and parts[1] not in STD.get(mod.aliases[parts[0]], ()):
            out.append((mod.aliases[parts[0]], parts[1], m.group(0)))
    return out


def relationship(user, line, tok, pos, is_body, target_name):
    """How this line uses the target, from the line's shape. By text, not by proof."""
    s = strip_comment(strip_strings(line))
    st = s.strip()
    extra = tok.split(".")[-1] != target_name.split(".")[-1]   # e.g. FeedingStatus.Delivered names a constructor of the target
    if is_body:
        after = s[pos + len(tok):]
        if re.search(r"\b(in|is)\s+$", s[:pos]):
            return "body test"
        if after.startswith("("):
            return "call"
        if re.search(r"\blet\s+\w+\s*:\s*$", s[:pos]):
            return "let type"
        if extra:
            return "constructor"
        return "unclassified"
    if user.kind in ("fn", "allow") and not st.startswith(("before", "after")):
        arrow = s.find("->")
        return "return type" if arrow != -1 and pos > arrow else "parameter type"
    if st.startswith(("before", "after")):
        return "contract"
    if st.startswith("type "):
        if re.match(r"type\s+\w+\s*=\s*" + re.escape(tok) + r"\b", st) and not extra:
            return "refinement base"
        rec = re.match(r"\s*type\s+\w+\s*=\s*\{", s)
        if rec and pos > rec.end() - 1 and (s.find("}") == -1 or pos < s.find("}")):
            return "record field type"
        return "refinement condition"
    if st.startswith("data "):
        return "data type"
    if st.startswith("access "):
        return "bound type"
    if st.startswith("where ") or st.startswith("projects "):
        return "refinement condition" if st.startswith("where ") else "projection target"
    return "declaration"


def use_sites(w, target):
    """Every line in src/park that names the target declaration: (user decl, relationship, lineno, text)."""
    sites = []
    tname = target.name
    for uk in sorted(w.used_by[target.key]):
        u = w.decls[uk]
        um = w.mods[u.module]
        scope = scopes_of(u)
        for is_body, lines in ((False, u.lines), (True, u.body)):
            for no, l in lines:
                if u.kind == "access" and strip_comment(l).strip().startswith("allow "):
                    continue          # listed under the allow itself
                rels = []
                for tok, pos, keys in tokens_resolving(um, w.decls, u, l, scope.get(no, set(u.params))):
                    if target.key in keys:
                        r = relationship(u, l, tok, pos, is_body, tname)
                        if r not in rels:
                            rels.append(r)
                if rels:
                    sites.append((u, "; ".join(rels), no, l.strip(), is_body))
    return sites


GUIDED_FULL = bool(os.environ.get("BRASS_GUIDED"))   # fixed at start: guided answers print every use
EXCERPT_BUDGET = 1600      # characters of source excerpts per `info` answer; the rest are named, not printed

RELATION_ORDER = ["parameter type", "return type", "let type", "record field type", "refinement base",
                  "refinement condition", "contract", "body test", "call", "constructor", "data type", "bound type",
                  "unclassified"]


def expansion_lines(w, u, no, is_body):
    """One level down from a use site: for a body site, the enclosing declaration and the tests on its path;
    for a signature site, the user's contract lines. Short, so the reader need not ask again."""
    out = []
    if is_body:
        if u.kind == "fn" and u.lines:
            sig = []
            for _, l in u.lines:
                sig.append(strip_comment(l).strip())
                if "->" in l:
                    break
            out.append("        in       " + " ".join(sig))
        idx = next((i for i, (n, _) in enumerate(u.body) if n == no), None)
        if idx is not None:
            tests = path_tests(u.body, idx)
            out.append("        on path  " + ("  |  ".join(t for _, t in tests) if tests else "no enclosing test"))
    else:
        for _, l in u.lines[1:]:
            st = strip_comment(l).strip()
            if st.startswith(("before", "after")):
                out.append(f"        {st}")
            if len(out) >= 2:
                break
    return out


def direct_uses_lines(w, d, in_module=None):
    """Direct uses grouped by relationship, with source lines until the budget is spent.
    `in_module` restricts the answer to one module and prints every line there."""
    sites = use_sites(w, d)
    if in_module:
        want = in_module if in_module.startswith(SRC.name + ".") else SRC.name + "." + in_module
        sites = [x for x in sites if x[0].module == want]
    if not sites:
        where = f"in {in_module}" if in_module else f"in {REL}/"
        return [f"direct uses  none {where}"]
    n = len({u.key for u, *_ in sites})
    head = f"direct uses  {n} declaration{'s' if n != 1 else ''}, {len(sites)} line{'s' if len(sites) != 1 else ''}"
    L = [head + (f", in {in_module}" if in_module else "")]
    groups = defaultdict(list)
    for u, rel, no, text, is_body in sites:
        groups[rel.split("; ")[0]].append((u, rel, no, text, is_body))
    order = [r for r in RELATION_ORDER if r in groups] + sorted(r for r in groups if r not in RELATION_ORDER)
    spent = 0
    omitted = defaultdict(int)
    for rel in order:
        rows = groups[rel]
        users = []
        for u, _, _, _, _ in rows:
            tag = u.short + (" (private)" if u.section == "private" else "")
            if tag not in users:
                users.append(tag)
        L.append(f"  {rel:<20} {', '.join(users)}")
        for u, full, no, text, is_body in rows:
            also = f"   [also {full.split('; ', 1)[1]}]" if "; " in full else ""
            line = f"      {w.mods[u.module].path.name}:{no:<5} {text}{also}"
            extra = expansion_lines(w, u, no, is_body)
            cost = len(text) + sum(len(x) for x in extra)
            if in_module or GUIDED_FULL or spent + cost <= EXCERPT_BUDGET:   # guided: the answer is complete, never a pointer to another call
                L.append(line)
                L.extend(extra)
                spent += cost
            else:
                omitted[u.module] += 1
    if omitted:
        parts = [f"{c} in {m.split('.')[-1]} (info {d.short} --in {m.split('.')[-1]})" for m, c in sorted(omitted.items())]
        L.append("  source omitted  " + "; ".join(parts))
    return L


def searched_line(w):
    parts = []
    ni = len(w.unresolved_imports)
    if ni:
        parts.append(f"{ni} import{'s' if ni != 1 else ''} unresolved: " + "  ".join(f"{m.split('.')[-1]}: {imp}" for m, imp in w.unresolved_imports[:3]) + (" …" if ni > 3 else ""))
    n = len(w.unresolved)
    parts.append("0 qualified names unresolved" if not n else (
        f"{n} qualified name{'s' if n != 1 else ''} unresolved: " + "  ".join(f"{m.split('.')[-1]}: {t}" for m, t in w.unresolved[:3]) + (" …" if n > 3 else "")))
    return f"searched     {REL}/*.brass ({len(w.mods)} modules, declarations and bodies), matched by name; " + "; ".join(parts)


def runtime_tier(d):
    """Tier line only where it differs from the default (proven by brass before run)."""
    text = [strip_comment(l) for _, l in d.lines]
    if d.kind == "allow":
        return "enforced by runtime on every reply" if any(l.strip().startswith("after") for l in text) else None
    if d.kind == "access" and "{" in text[0]:
        return "bounds enforced by runtime on every call; values set in system.brass"
    return None


LEGEND = ("tiers       before/after: proven by brass before run.  type where: checked at each `in` test.  "
          "machine edges: proven.  access bounds, allow after: enforced by runtime.")


class World:
    def __init__(self):
        self.mods, self.parse_errors = {}, []
        for p in sorted(list(SRC.glob("*.brass")) + list(SRC.glob("*.keel"))):
            try:
                m = Module(p)
                self.mods[m.name] = m
                MODS_BY_NAME[m.name] = m
            except (KeyError, StopIteration, IndexError) as e:
                self.parse_errors.append((p, e))
        self.decls = {d.key: d for m in self.mods.values() for d in m.decls.values()}
        self.unresolved = []                     # (module, token) for alias.Name where Name is not declared there
        self.unresolved_imports = sorted({(m.name, imp) for m in self.mods.values() for imp, _, _ in m.imports if imp not in self.mods and not imp.startswith("std.")})
        for m in self.mods.values():
            for d in m.decls.values():
                scope = scopes_of(d)
                for no, l in d.lines + d.body:
                    for _, _, keys in tokens_resolving(m, self.decls, d, l, scope.get(no, set(d.params))):
                        for key in keys:
                            if key != d.key and not (d.kind == "allow" and key == (d.module, d.name.split(".")[0])):
                                d.refs.add(key)
                    for tm, tn, tok in unresolved_in(m, l):
                        if (tm, tn) not in self.decls and (m.name, tok) not in self.unresolved:
                            self.unresolved.append((m.name, tok))
        self.used_by = defaultdict(set)
        for d in self.decls.values():
            for k in d.refs:
                self.used_by[k].add(d.key)
        for d in self.decls.values():
            if d.kind == "allow":
                self.used_by[(d.module, d.name.split(".")[0])] |= self.used_by[d.key]
        self.module_used_by = defaultdict(set)
        for m in self.mods.values():
            for imp, _, _ in m.imports:
                self.module_used_by[imp].add(m.name)
        # field name -> set of type keys that field carries, across every record type
        self.field_types = defaultdict(set)
        for m in self.mods.values():
            for d in m.decls.values():
                for f, t in d.fields.items():
                    k = type_key(m, self.decls, t)
                    if k is not None:
                        self.field_types[f].add(k)
        # data constant -> the type key it is declared with
        self.data_types = {}
        for m in self.mods.values():
            for d in m.decls.values():
                if d.kind == "data":
                    dm = re.match(r"\s*data\s+\w+\s*:\s*([A-Za-z_][A-Za-z0-9_.]*)", d.lines[0][1])
                    k = type_key(m, self.decls, dm.group(1)) if dm else None
                    if k is not None:
                        self.data_types[d.key] = k
        self.system = SYSTEM.read_text().splitlines()
        self.grants = {}
        cur = None
        for l in self.system:
            mm = re.match(r"\s*grants\s+([\w.]+):\s*(.*)", l)
            if mm:
                cur = mm.group(1).split(".")[-1]      # v0.2 grants are module-qualified; keyed by function name
                self.grants[cur] = mm.group(2).strip()
            elif cur is not None and l.strip() and not l.strip().startswith(("limit", "system")):
                self.grants[cur] += " " + l.strip()
            else:
                cur = None

    def entry(self, name):
        for m in self.mods.values():
            d = m.decls.get(name)
            if d is not None and d.kind == "fn" and d.section == "interface":
                return m, d
        return None, None

    def closure(self, key):
        seen, stack = set(), list(self.used_by[key])
        while stack:
            k = stack.pop()
            if k in seen or k == key:
                continue
            seen.add(k)
            stack.extend(self.used_by[k])
        return seen

    def module(self, name):
        if not name.startswith(SRC.name + "."):
            name = SRC.name + "." + name
        return self.mods.get(name)

    def find(self, dotted):
        parts = dotted.split(".")
        if parts[0] == SRC.name:
            parts = parts[1:]
        if len(parts) == 1:                       # a bare name: accepted when exactly one module declares it
            hits = [(m, m.decls[parts[0]]) for m in self.mods.values() if parts[0] in m.decls]
            return hits[0] if len(hits) == 1 else (None, None)
        if len(parts) < 2:
            return None, None
        m = self.module(parts[0])
        if m is None:
            return None, None
        name = ".".join(parts[1:])
        return m, m.decls.get(name)


def if_changed_lines(w, d, ic):
    """Full transitive impact set, grouped by module, one line per module."""
    if not ic:
        return [f"reaches     nothing else in {REL}/"]
    mods = sorted({w.decls[k].module for k in ic})
    out = [f"reaches     {len(ic)} declarations in {len(mods)} modules: everything that names this or names a user of it, transitively. References, not required edits; by name, not by proof."]
    by_mod = defaultdict(list)
    for k in ic:
        by_mod[w.decls[k].module].append(w.decls[k].name)
    for m in sorted(by_mod):
        out.append(f"              {m.split('.')[-1]:<11} {'  '.join(sorted(by_mod[m]))}")
    return out


def fmt(keys, w):
    return "  ".join(sorted(w.decls[k].short for k in keys)) if keys else "none"


def info_system(w):
    L = [BANNER, f"system      {next((l.split()[1] for l in w.system if l.startswith('system ')), '?')}",
         f"size        {len(w.mods)} modules  {sum(len(m.text) for m in w.mods.values()) + len(w.system)} lines including system.brass", ""]
    L.append("grants and limits   (src/system.brass)")
    L.extend("  " + l for l in w.system[1:])
    L.append("")
    L.append("entry points        (`brass info --holds` for what each holds)")
    for ep in w.grants:
        m, _ = w.entry(ep)
        L.append(f"  {ep:<20} {m.name if m else '?'}")
    L.append("")
    rows = []
    for m in w.mods.values():
        imps = " ".join(i.split(".")[-1] for i, _, _ in m.imports) or "-"
        ub = " ".join(sorted(u.split(".")[-1] for u in w.module_used_by[m.name])) or "-"
        rows.append((m, imps, ub))
    wd = max((len(r[1]) for r in rows), default=4) + 2
    L.append("modules")
    L.append(f"  {'module':<18}{'ver':<5}{'iface':>6}{'priv':>6}{'body':>6}  {'imports':<{wd}}used_by")
    for m, imps, ub in rows:
        L.append(f"  {m.name:<18}{m.version:<5}{len(m.interface):>6}{len(m.private):>6}{len(m.body_lines):>6}  {imps:<{wd}}{ub}")
    return L


def module_header(w, m):
    return [f"module      {m.name} {m.version}   {REL}/{m.path.name}  {len(m.text)} lines  interface {len(m.interface)}  private {len(m.private)}  body {len(m.body_lines)}",
            "imports     " + ("  ".join(f"{i} {v} as {a}" for i, v, a in m.imports) if m.imports else "none"),
            "used_by     " + ("  ".join(sorted(w.module_used_by[m.name])) if w.module_used_by[m.name] else "none")]


def info_module(w, m):
    L = module_header(w, m) + [LEGEND, "", "interface"]
    for no, l in m.interface:
        L.append(l)
    while L and L[-1].strip() == "":
        L.pop()
    L.append("")
    if m.private:
        names = [d.name for d in m.decls.values() if d.section == "private"]
        L.append(f"private             {len(m.private)} lines, names only: {'  '.join(names)}")
    L.append(f"body                {len(m.body_lines)} lines, not shown")
    return L


def holds_of(w, m, d):
    held = []
    for p, t in d.params.items():
        if access_key(m, w.decls, t) is not None:
            held.append(f"{p}: {t}")
    return held


def info_decl(w, m, d, want_ic, in_module=None):
    L = [f"declaration {d.kind} {d.name}   {m.name} {m.version}   {d.section}   {REL}/{m.path.name}:{d.lines[0][0]}"]
    for _, l in d.lines:
        L.append(l)
    while L and L[-1].strip() == "":
        L.pop()
    t = runtime_tier(d)
    if t:
        L.append(f"tier        {t}")
    if d.kind == "fn":
        held = holds_of(w, m, d)
        grant = w.grants.get(d.name)
        L.append("holds       " + ("  ".join(held) if held else "no access; cannot reach outside"))
        if grant is not None:
            L.append(f"grants      entry point; system.brass gives: {grant}")
    L.extend(direct_uses_lines(w, d, in_module))
    if want_ic:
        L.extend(if_changed_lines(w, d, w.closure(d.key)))
    L.append(searched_line(w))
    if d.body:
        body_refs = set()
        for _, l in d.body:
            for tok in IDENT.findall(strip_comment(l)):
                body_refs |= resolve(m, w.decls, tok, d.params)
        body_refs.discard(d.key)
        L.append(f"body        {len(d.body)} lines   references: {fmt(body_refs, w)}")
    return L


def names_all(w):
    L = []
    for m in w.mods.values():
        names = [d.name for d in m.decls.values() if d.section == "interface" and d.kind != "allow"]
        L.append(f"{m.name.split('.')[-1]:<11} {'  '.join(names)}")
    return L


def names_module(w, m):
    L = module_header(w, m) + [""]
    for d in m.decls.values():
        if d.section == "body":
            continue
        L.append(f"  {d.kind:<13}{d.name:<28}{d.section}")
    return L


def holds_all(w):
    L = []
    for ep, grant in w.grants.items():
        m, d = w.entry(ep)
        held = holds_of(w, m, d) if d is not None else []
        L.append(f"{ep:<20} {m.name if m else '?':<14} holds  {'  '.join(held) if held else 'no access'}")
        L.append(f"{'':<20} grant  {grant}")
    L.append("")
    L.append("An entry point can reach outside only through the accesses it holds; none can be created in a body.")
    return L


def established_by(w, m, d):
    L = [f"declaration {d.kind} {d.name}   {m.name}"]
    reqs = [strip_comment(l).strip() for _, l in d.lines if strip_comment(l).strip().startswith("before")]
    ptypes = [f"{p}: {t}" for p, t in d.params.items()]
    L.append("requires    " + ("; ".join(reqs) if reqs else "no before clause") + (f"   parameter types: {', '.join(ptypes)}" if ptypes else ""))
    callers = [k for k in w.used_by[d.key] if w.decls[k].kind == "fn"]
    if not callers:
        L.append("callers     none")
    for k in sorted(callers):
        c = w.decls[k]
        cm = w.mods[c.module]
        alias = next((a for a, mod in cm.aliases.items() if mod == m.name), None)
        pat = (alias + "." if alias and c.module != m.name else "") + d.name + "("
        L.append(f"caller      {c.short}")
        for i, (no, l) in enumerate(c.body):
            if pat in strip_comment(l):
                L.append(f"  call      {no}: {l.strip()}")
                tests = path_tests(c.body, i)
                if tests:
                    L.append("  on path   " + "  |  ".join(f"{n}: {t}" for n, t in tests))
                else:
                    L.append("  on path   no enclosing test; established by the argument's type or a data fact")
    L.append("Static reading of the enclosing tests; whether they discharge the requirement is the checker's call.")
    return L


def path_tests(body, i):
    """The `if` tests enclosing body line i (outermost first), by indentation."""
    indent = len(body[i][1]) - len(body[i][1].lstrip())
    tests = []
    for pno, pl in reversed(body[:i]):
        pind = len(pl) - len(pl.lstrip())
        st = strip_comment(pl).strip()
        if pind < indent and (st.startswith("if ") or st.startswith("else if ")):
            tests.append((pno, st))
            indent = pind
        elif pind < indent and st.startswith("else"):
            indent = pind
    return list(reversed(tests))


def narrowings(tests):
    """`x is T` facts (and `x in T`, for copies before C13) from enclosing tests: {name: [types]}; `and` splits, `or` does not."""
    out = defaultdict(list)
    for _, t in tests:
        cond = re.sub(r"^(else\s+)?if\s+", "", t).rstrip()
        cond = re.sub(r"\s+then$", "", cond)
        if " or " in cond:
            continue
        for part in cond.split(" and "):
            mm = re.match(r"^\s*([a-z_][A-Za-z0-9_]*)\s+(?:in|is)\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$", part)
            if mm and not mm.group(2).startswith("{"):
                out[mm.group(1)].append(mm.group(2))
    return out


def scope_at(d, idx):
    """Bindings visible at body index idx: [(name, type, note)], plus the enclosing tests."""
    text = d.body[idx][1]
    indent = len(text) - len(text.lstrip())
    lets = []
    for pno, pl in d.body[:idx]:
        pind = len(pl) - len(pl.lstrip())
        lm = re.match(r"\s*let\s+([a-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_.<>]*)", pl)
        if lm and pind <= indent:
            lets.append((lm.group(1), lm.group(2), pno))
    tests = path_tests(d.body, idx)
    narrow = narrowings(tests)
    out = []
    for p, t in d.params.items():
        n = narrow.get(p)
        out.append((p, n[-1] if n else t, f"narrowed from {t} (test on path)" if n else "parameter"))
    for name, t, pno in lets:
        n = narrow.get(name)
        out.append((name, n[-1] if n else t, f"narrowed from {t} (test on path)" if n else f"let at {pno}"))
    return out, tests


def at_line(w, m, d, line):
    """Facts a checker knows at a body line: bindings, narrowings, holds, and what a call there needs."""
    idx = next((i for i, (no, _) in enumerate(d.body) if no == line), None)
    if idx is None:
        return [f"{d.short}: line {line} is not in its body ({d.body[0][0]} to {d.body[-1][0]})" if d.body else f"{d.short}: no body"]
    no, text = d.body[idx]
    L = [f"declaration {d.kind} {d.name}   {m.name}   at {no}: {text.strip()}"]
    scope, tests = scope_at(d, idx)
    narrow = narrowings(tests)
    lets = [(n, t, 0) for n, t, note in scope if note.startswith("let") or (note.startswith("narrowed") and n not in d.params)]
    L.append("in scope")
    for name, t, note in scope:
        L.append(f"  {name}: {t}   ({note})")
    held = holds_of(w, m, d)
    L.append("holds       " + ("  ".join(held) if held else "none"))
    if tests:
        L.append("on path     " + "  |  ".join(f"{pn}: {t}" for pn, t in tests))
    else:
        L.append("on path     no enclosing test")
    # what the calls on this line require
    known = {p: t for p, t in d.params.items()}
    known.update({n: t for n, t, _ in lets})
    for name, tys in narrow.items():
        known[name] = tys[-1]
    calls = []
    for tok in IDENT.findall(strip_comment(text)):
        for k in resolve(m, w.decls, tok, d.params):
            cd = w.decls[k]
            if cd.kind in ("fn", "allow") and cd.params and cd.key != d.key:
                calls.append((tok, cd))
    for tok, cd in calls:
        L.append(f"call        {tok}: needs " + ", ".join(f"{p}: {t}" for p, t in cd.params.items()))
        reqs = [strip_comment(l).strip() for _, l in cd.lines if strip_comment(l).strip().startswith("before")]
        for r in reqs:
            L.append(f"            {r}")
        am = re.search(re.escape(tok) + r"\(([^()]*)\)", strip_comment(text))
        if am:
            args = [a.strip() for a in am.group(1).split(",") if a.strip()]
            for (p, t), a in zip(cd.params.items(), args):
                have = known.get(a)
                short_t = t.split(".")[-1]
                if have is None:
                    L.append(f"            {p} <- {a}: not a name in scope (expression); type not tracked here")
                elif have == t or have.split(".")[-1] == short_t:
                    L.append(f"            {p} <- {a}: {have}   fits")
                else:
                    L.append(f"            {p} <- {a}: {have}   needs {t}; not established on this path")
    L += quantifier_lines(w, m, d, text, known)
    L.append("Static reading; the checker decides what these facts prove.")
    return L


QUANT = re.compile(r"\b(any|all)\s+([a-z_]\w*)\s+in\s+([a-z_][\w.]*)\s+where\s+(.+)$")


def quantifier_lines(w, m, d, text, known):
    """Context inside `any`/`all` on this line (C16): the bound name, narrowing, and what the condition may not do."""
    qm = QUANT.search(strip_comment(text).rstrip())
    if not qm:
        return []
    kind, name, src, cond = qm.groups()
    while cond.count(")") > cond.count("("):
        cond = cond[:cond.rindex(")")].rstrip()
    sig = " ".join(strip_comment(l).strip() for _, l in d.lines)
    sm = re.search(r"\b" + re.escape(src) + r"\s*:\s*Array<([^>]+)>(\s+where\s+it\.length\s+in\s+\d+\s+to\s+(\d+))?", sig)
    elem = sm and sm.group(1).strip()
    bound = sm and sm.group(3)
    L = [f"{kind:<11} {kind} {name} in {src} where {cond}",
         f"  value     Bool; {'false' if kind == 'any' else 'TRUE'} when {src} is empty",
         f"  {name}: {elem or '?'}   (one element of {src}; exists only in this expression)",
         f"  bounded   " + (f"by {src}: length at most {bound}" if bound else f"not shown: {src}'s type must bound length")]
    facts = narrowings([(0, "if " + cond + " then")]).get(name)
    if facts:
        L.append(f"  narrowed  right of `and`, {name}: {facts[-1]}")
    holds = {h.split(":")[0] for h in holds_of(w, m, d)}
    bad = []
    if "?" in cond:
        bad.append("`?` propagates a failure")
    for am in re.finditer(r"\b([a-z_]\w*)\.([a-z_]\w*)\(", cond):
        if am.group(1) in holds:
            bad.append(f"{am.group(1)}.{am.group(2)} is an access call")
    for tok in IDENT.findall(cond):
        for k in resolve(m, w.decls, tok, d.params):
            if w.decls[k].fails:
                bad.append(f"{tok} returns Outcome")
    L.append("  effects   none allowed: no `?`, no access call, no call to a fn returning Outcome" + ("; found: " + "; ".join(bad) if bad else ""))
    return L


def effects(w, m, d):
    """What an entry point does to the world, in body order, with the tests guarding each step."""
    if not d.body:
        return [f"{d.short}: no body"]
    L = [f"declaration {d.kind} {d.name}   {m.name}"]
    held = holds_of(w, m, d)
    L.append("holds       " + ("  ".join(held) if held else "none; no effects possible"))
    access_params = {p for p in d.params if any(h.startswith(p + ":") for h in held)}
    rows = []
    for i, (no, l) in enumerate(d.body):
        s = strip_comment(l)
        found = []
        for am in re.finditer(r"\b([a-z_][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)\(", s):
            if am.group(1) in access_params:
                found.append(f"{am.group(1)}.{am.group(2)}")
        for tok in IDENT.findall(s):
            for k in resolve(m, w.decls, tok, d.params):
                cd = w.decls[k]
                if cd.kind == "fn" and cd.key != d.key:
                    passed = [p for p in access_params if re.search(r"\b" + p + r"\b", s.split(tok, 1)[1] if tok in s else "")]
                    if passed:
                        found.append(f"{tok}(..) with {', '.join(passed)}")
        if found:
            rows.append((no, found, path_tests(d.body, i)))
    if not rows:
        L.append("effects     none in this body")
        return L
    L.append("effects     in body order; guard is every `if` test enclosing the line")
    prev = None
    for n, (no, found, tests) in enumerate(rows, start=1):
        guard = "  |  ".join(t for _, t in tests) if tests else "unconditional"
        g = "same" if guard == prev else guard
        prev = guard
        L.append(f"  {n:<3}{no:>4}  {'  '.join(found):<44} {g}")
    return L


HOLE = "@@"


def baseline_text(m):
    """The module's text before the edit: $BRASS_BASELINE/<same relative path>, else git HEAD."""
    rel = m.path.relative_to(ROOT)
    base = os.environ.get("BRASS_BASELINE")
    if base:
        p = Path(base) / rel
        return p.read_text().splitlines() if p.exists() else None
    import subprocess
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:./{rel}"], capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else None


def norm(lines):
    return " ".join(strip_comment(l).strip() for _, l in lines if strip_comment(l).strip())


def close_paren(s, start):
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def literal_spans(body):
    """Record literals in a body: (first index, last index, field names, text) for each `{ ... }`."""
    spans = []
    i = 0
    while i < len(body):
        s = strip_comment(body[i][1])
        if "{" in s and ":" in s.split("{", 1)[1]:
            j, depth, text = i, 0, ""
            while j < len(body):
                t = strip_comment(body[j][1])
                text += t + "\n"
                depth += t.count("{") - t.count("}")
                if depth <= 0:
                    break
                j += 1
            inner = text.split("{", 1)[1].rsplit("}", 1)[0]
            names = re.findall(r"([a-z_][A-Za-z0-9_]*)\s*:", inner)
            spans.append((i, j, set(names)))
            i = j + 1
        else:
            i += 1
    return spans


def qualify(m, t):
    """A type as a reader outside `m` would write it: module-qualified when `m` declares it, bare otherwise."""
    head = t.split("<")[0].split(".")[0]
    if "." in t or head in BUILTINS or head in ("Maybe", "Float", "Bytes") or head not in m.decls:
        return t
    return f"{m.name.split('.')[-1]}.{t}"


def propagate(w, dry):
    """The mechanical consequences of the interface edits since the baseline, written into the tree with a
    typed hole wherever a value is the author's to supply. Then the `changes` report on the result."""
    base = baseline_world(w)
    if not base and not baseline_set():
        return ["propagate   no baseline: set BRASS_BASELINE or run inside a git checkout"]
    edits, holes, summary = [], [], []
    cur = {}                                          # (path, lineno) -> the line as edits so far have left it

    def now(path, no, orig):
        return cur.get((path, no), orig)

    def put(path, no, orig, new, why):
        edits.append((path, no, now(path, no, orig), new, why))
        cur[(path, no)] = new

    for k in sorted(set(base) & set(w.decls)):
        od, nd = base[k], w.decls[k]
        what = [x for x in describe_change(od, nd) if not x.startswith("body changed")]
        if not what:
            continue
        summary.append(f"  {nd.short:<30} " + "; ".join(what))
        m = w.mods[nd.module]
        if nd.kind == "fn":
            added = [(p, t) for p, t in nd.params.items() if p not in od.params]
            removed = [p for p in od.params if p not in nd.params]
            if not (added or removed):
                continue
            if nd.body:
                no, l0 = nd.body[0]
                l = now(f"{REL}/{m.path.name}", no, l0)
                bm = re.match(r"(\s*fn\s+" + re.escape(nd.name) + r"\()([^)]*)(\).*)$", l)
                if bm:
                    names = [a.strip() for a in bm.group(2).split(",") if a.strip()]
                    if len(names) == len(od.params):
                        names = [a for pn, a in zip(od.params, names) if pn not in removed] + [pn for pn, _ in added]
                        s2 = bm.group(1) + ", ".join(names) + bm.group(3)
                        put(f"{REL}/{m.path.name}", no, l0, s2, f"body of {nd.short}: parameter list follows the declaration")
            for ck in sorted(w.used_by[nd.key]):
                c = w.decls[ck]
                if c.kind != "fn":
                    continue
                cm = w.mods[c.module]
                alias = next((a for a, mod in cm.aliases.items() if mod == m.name), None)
                pat = (alias + "." if alias and c.module != m.name else "") + nd.name + "("
                for i, (no, l0) in enumerate(c.body):
                    l = now(f"{REL}/{cm.path.name}", no, l0)
                    s2 = l
                    pos = s2.find(pat)
                    while pos != -1:
                        op = pos + len(pat) - 1
                        cp = close_paren(s2, op)
                        if cp == -1:
                            break
                        args = [a.strip() for a in s2[op + 1:cp].split(",") if a.strip()]
                        if len(args) != len(od.params):
                            pos = s2.find(pat, op + 1)
                            continue                       # already updated, or not this call shape
                        kept = [a for pn, a in zip(od.params, args) if pn not in removed]
                        for pn, t in added:
                            kept.append(HOLE + pn)
                            scope, tests = scope_at(c, i)
                            tq = qualify(m, t)
                            holes.append((HOLE + pn, tq, f"{REL}/{cm.path.name}", no, scope, tests, f"argument to {nd.short}"))
                        s2 = s2[:op + 1] + ", ".join(kept) + s2[cp:]
                        pos = s2.find(pat, op + 1)
                    if s2 != l:
                        put(f"{REL}/{cm.path.name}", no, l0, s2, f"call to {nd.short} in {c.short}")
        elif nd.kind == "type":
            oh, nh = has_fields(od), has_fields(nd)
            for f, (mf, sts, t) in nh.items():
                if f in oh:
                    continue
                pat = re.compile(r"\benters\s+(?:\w+\.)*(" + "|".join(re.escape(x.split(".")[-1]) for x in sts) + r")\b")
                for dd in w.decls.values():
                    dm = w.mods[dd.module]
                    for i, (no, l0) in enumerate(dd.body):
                        l = now(f"{REL}/{dm.path.name}", no, l0)
                        st = strip_comment(l)
                        if not pat.search(st) or "with" not in st or re.search(r"\b" + f + r"\s*:", st):
                            continue
                        k2 = l.rfind("}")
                        if k2 == -1:
                            continue
                        s2 = l[:k2].rstrip() + f", {f}: {HOLE}{f} " + l[k2:]
                        put(f"{REL}/{dm.path.name}", no, l0, s2, f"enters {', '.join(sts)} in {dd.short}: {f} must be supplied")
                        scope, tests = scope_at(dd, i)
                        tq = qualify(m, t)
                        holes.append((HOLE + f, tq, f"{REL}/{dm.path.name}", no, scope, tests, f"field {f} of {nd.short}"))
            new_f = [(f, t) for f, t in nd.fields.items() if f not in od.fields]
            if new_f:
                for dm in w.mods.values():
                    for dd in dm.decls.values():
                        for a, b, names in literal_spans(dd.body):
                            if names == set(od.fields):
                                no, l0 = dd.body[b]
                                l = now(f"{REL}/{dm.path.name}", no, l0)
                                k2 = l.rfind("}")
                                ins = ", ".join(f"{f}: {HOLE}{f}" for f, _ in new_f)
                                s2 = l[:k2].rstrip() + ", " + ins + " " + l[k2:]
                                put(f"{REL}/{dm.path.name}", no, l0, s2, f"literal of {nd.short} in {dd.short}")
                                for f, t in new_f:
                                    scope, tests = scope_at(dd, b)
                                    tq = qualify(m, t)
                                    holes.append((HOLE + f, tq, f"{REL}/{dm.path.name}", no, scope, tests, f"field {f} of {nd.short}"))
    src = "$BRASS_BASELINE" if os.environ.get("BRASS_BASELINE") else "git HEAD"
    if not summary:
        return [f"propagate   no interface change against {src}; nothing to do"]
    L = [f"propagate   against {src}", "interface changes"] + summary
    if not edits:
        L.append("mechanical  nothing: no call, literal, or state entry has to change for these edits")
    else:
        written = 0
        if not dry:
            by_path = defaultdict(list)
            for path, no, o, n, _ in edits:
                by_path[path].append((no, o, n))
            for path, es in by_path.items():
                pth = ROOT / path
                lines = pth.read_text().splitlines()
                for no, o, n in es:
                    if lines[no - 1] == o:
                        lines[no - 1] = n
                        written += 1
                    else:
                        L.append(f"skipped     {path}:{no} changed since the baseline was read")
                pth.write_text("\n".join(lines) + "\n")
        L.append(f"{'planned' if dry else 'written'}     {len(edits)} edit{'s' if len(edits) != 1 else ''}" + ("" if dry else f", {written} applied"))
        for path, no, o, n, why in edits:
            L.append(f"  {path}:{no}   {why}")
            L.append(f"    - {o.strip()}")
            L.append(f"    + {n.strip()}")
    if holes:
        L.append(f"holes       {len(holes)}   a program with a hole is rejected; fill each with a value of the type shown")
        for h, t, path, no, scope, tests, why in holes:
            L.append(f"  {h} : {t}   {path}:{no}   ({why})")
            L.append("    in scope  " + ("  ".join(f"{n}: {ty}" for n, ty, _ in scope) or "nothing bound before this line"))
            if tests:
                L.append("    on path   " + "  |  ".join(t2 for _, t2 in tests))
    if not dry:
        L.append("")
        L.extend(changes(World()))
    else:
        L.append("dry run     nothing written; run without --dry to apply")
    return L


FORMS = [
    ("module header", r"^module \S+ v\d+"),
    ("import with alias", r"^import \S+ v\d+ as \w+"),
    ("interface section", r"^interface$"),
    ("private section", r"^private$"),
    ("body section", r"^body$"),
    ("type alias", r"^  type \w+\s*=\s*[A-Za-z_.]+\s*$"),
    ("type refinement (where)", r"^  type \w+\s*=\s*[A-Za-z_.]+\s+where\s"),
    ("refinement over it (numeric range)", r"where it in \d+ to \d+"),
    ("record type", r"^  type \w+\s*=\s*\{"),
    ("record refinement on a field", r"^  type \w+\s*=\s*\w+\s+where\s+\w+ in \{"),
    ("constant", r"^  const \w+\s*:\s*\S+\s*=\s*"),
    ("machine", r"^  machine \w+"),
    ("machine states", r"^    states\s"),
    ("machine initial", r"^    initial\s"),
    ("machine edge", r"^    \w+ enters \w+"),
    ("access", r"^  access \w+"),
    ("access with bounds", r"^  access \w+\s*\{"),
    ("allow", r"^    allow \w+\("),
    ("fn signature", r"^  fn \w+\(.*\)\s*->"),
    ("fn that can fail", r"^  fn \w+\(.*->\s*Outcome<"),
    ("before clause", r"^\s+before\s"),
    ("after clause", r"^\s+after\s"),
    ("array with length bound", r"Array<[^>]+>\s+where it\.length in"),
    ("fn body", r"^  fn \w+\([^:]*\)\s*=\s*$|^  fn \w+\([^:]*\)\s*=\s*\S"),
    ("typed let", r"^\s+let \w+\s*:\s*\S+\s*="),
    ("reassign a let", r"^\s+\w+ = \w+ [+-] "),
    ("if / then", r"^\s+if .* then$"),
    ("else", r"^\s+else"),
    ("type test (x is T)", r"\bif \w+ (?:is [A-Za-z_][\w.]*|in (?:[a-z_]\w*\.)*[A-Z]\w*)\b"),
    ("set membership (x in {..})", r"\w+ in \{"),
    ("enters in an expression", r"\w+\.status enters \w+\.\w+"),
    ("call with ? (Outcome unwrap)", r"\)\?"),
    ("Ok / Err", r"\b(Ok|Err)\("),
    ("record literal", r"\{ *\w+:"),
    ("for over a collection", r"^\s+for \w+ in \w+$"),
    ("for over a range", r"^\s+for \w+ in \d+ to \d+"),
    ("break", r"^\s+break\b"),
    ("and / or", r"\b(and|or)\b"),
    ("qualified name (alias.Name)", r"\b[a-z]+\.[A-Z]\w+"),
    ("comment", r"#"),
]


def forms(w):
    """The forms this project uses, one example each, drawn from the source."""
    L = ["forms       one example per form, from this project; a form absent here is not used by this code"]
    seen = []
    for name, rx in FORMS:
        r = re.compile(rx)
        hit = None
        for m in w.mods.values():
            for i, l in enumerate(m.text, start=1):
                if r.search(l):
                    hit = (m.path.name, i, l.strip())
                    break
            if hit:
                break
        if hit:
            seen.append((name, hit))
        else:
            L.append(f"  {name:<36} not used")
    for name, (f, i, l) in seen:
        L.append(f"  {name:<36} {f}:{i:<4} {l[:90]}")
    return L


def review(w, m):
    """What a human should read about this module's edit, authority first, bodies last."""
    old_lines = baseline_text(m)
    if old_lines is None:
        return [f"review      {m.name}: no baseline (set BRASS_BASELINE or commit the project)"]
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"brass-baseline-{m.path.name}"
    tmp.write_text("\n".join(old_lines) + "\n")
    old = Module(tmp)
    tmp.unlink()
    L = [f"review      {m.name}   read in this order"]
    authority, contracts, types, bodies = [], [], [], []
    for name, nd in m.decls.items():
        od = old.decls.get(name)
        if nd.kind in ("access", "allow"):
            if od is None:
                authority.append(f"ADDED   {nd.kind} {name}: " + norm(nd.lines)[:100])
            elif norm(od.lines) != norm(nd.lines):
                authority.append(f"CHANGED {nd.kind} {name}: " + norm(nd.lines)[:100])
        elif nd.kind == "fn" and nd.section != "body":
            oc = set(strip_comment(l).strip() for _, l in od.lines if strip_comment(l).strip().startswith(("before", "after"))) if od else set()
            nc = set(strip_comment(l).strip() for _, l in nd.lines if strip_comment(l).strip().startswith(("before", "after")))
            sig_o = norm(od.lines[:1]) if od else ""
            sig_n = norm(nd.lines[:1])
            if od is None:
                contracts.append(f"ADDED   {nd.kind} {name}: {sig_n}")
            else:
                if sig_o != sig_n:
                    contracts.append(f"SIGNATURE {name}: {sig_o}  ->  {sig_n}")
                for c in sorted(nc - oc):
                    contracts.append(f"ADDED clause  {name}: {c}   (stronger promise or new requirement; callers re-checked)")
                for c in sorted(oc - nc):
                    contracts.append(f"REMOVED clause {name}: {c}   (weaker; anything relying on it must be found)")
            if od is not None and norm(od.body) != norm(nd.body) and nd.body:
                bodies.append(f"{name}: body changed, {len(nd.body)} lines (was {len(od.body)})")
            elif od is None and nd.body:
                bodies.append(f"{name}: new body, {len(nd.body)} lines")
        elif nd.kind in ("type", "data", "machine"):
            if od is None:
                types.append(f"ADDED   {nd.kind} {name}: " + norm(nd.lines)[:100])
            elif norm(od.lines) != norm(nd.lines):
                if nd.kind == "type" and nd.fields and od.fields:
                    parts = []
                    for f, t in nd.fields.items():
                        if f not in od.fields:
                            parts.append(f"+{f}: {t}")
                        elif od.fields[f] != t:
                            parts.append(f"{f}: {od.fields[f]} -> {t}")
                    parts += [f"-{f}" for f in od.fields if f not in nd.fields]
                    types.append(f"CHANGED type {name}: fields " + ", ".join(parts) if parts else f"CHANGED type {name}: condition changed")
                else:
                    types.append(f"CHANGED {nd.kind} {name}: " + norm(od.lines)[:80] + "  ->  " + norm(nd.lines)[:80])
    for name, od in old.decls.items():
        if name not in m.decls and od.section != "body":
            (authority if od.kind in ("access", "allow") else contracts if od.kind == "fn" else types).append(f"REMOVED {od.kind} {name}")
    holes = sum(l.count(HOLE) for l in m.text)
    if holes:
        L.append(f"0  holes    {holes} {HOLE} remain in this file; the program is rejected until they are filled")
    L.append("1  authority   " + ("widened or changed authority needs a human" if authority else "no access or allow changed"))
    L.extend("     " + a for a in authority)
    L.append("2  contracts   " + ("" if contracts else "no signature or clause changed"))
    L.extend("     " + c for c in contracts)
    L.append("3  types       " + ("" if types else "no type, data, or machine changed"))
    L.extend("     " + t for t in types)
    L.append("4  bodies      " + ("read only if the contract does not capture the behavior (R7)" if bodies else "no body changed"))
    L.extend("     " + b for b in bodies)
    imps = [im.name for im in w.mods.values() if any(l.startswith(f"import {m.name} ") for l in im.text)]
    L.append(f"importers   {'  '.join(imps) if imps else 'none'}   (brass propagate {m.name.split('.')[-1]} lists what moves)")
    return L


def run_fn(w, target, arg_texts):
    """Evaluate a total fn on literal arguments; then check its return type and after clauses on the result."""
    sys.path.insert(0, str(HERE.parent))
    import brasseval as ke
    m, d = w.find(target)
    if d is None:
        return [f"unknown: {target}"]
    ev = ke.Evaluator(w, strip_comment)
    L = [f"run         {d.short}({', '.join(arg_texts)})"]
    try:
        args = [ev.eval(ke.parse_expr(a), m, {}) for a in arg_texts]
        for (pname, ptype), a in zip(d.params.items(), args):
            base = ptype.split(" where")[0]
            if base in ("Int", "Text", "Bool") or base.startswith(("Array", "Outcome", "Set")):
                continue
            t, _ = ev.lookup_qualified(m, base.split("."), {})
            if isinstance(t, tuple) and t[0] == "type" and not ev.satisfies(a, t[1], t[2]):
                return L + [f"rejected    argument {pname} does not satisfy {ptype}; a checker would refuse this call, not run it"]
        result = ev.call(m, d, args)
    except ke.BrassError as e:
        return L + [f"fault       {e}"]
    except (KeyError, TypeError, IndexError, AttributeError) as e:
        return L + [f"fault       cannot evaluate: {type(e).__name__} {e}"]
    sig = " ".join(strip_comment(l).strip() for _, l in d.lines if strip_comment(l).strip())
    ret = sig.split("->", 1)[1].split(" before")[0].split(" after")[0].strip() if "->" in sig else "?"
    L.append(f"result      {ke.show(result)} : {ret}")
    # return type condition
    try:
        base = ret.split(" where")[0].strip()
        if base not in ("Int", "Text", "Bool") and not base.startswith(("Array", "Outcome", "Set")):
            t, _ = ev.lookup_qualified(m, base.split("."), {})
            if isinstance(t, tuple) and t[0] == "type":
                ok = ev.satisfies(result, t[1], t[2])
                L.append(f"type        {base}: {'holds' if ok else 'VIOLATED'} on this result")
    except ke.BrassError as e:
        L.append(f"type        {ret}: not checked ({e})")
    names = [x.strip() for x in strip_comment(d.body[0][1]).split("(", 1)[1].rsplit(")", 1)[0].split(",") if x.strip()]
    env = dict(zip(names, args))
    env["result"] = result
    for _, l in d.lines:
        s = strip_comment(l).strip()
        if s.startswith("after"):
            try:
                ok = ev.truth(ev.eval(ke.parse_expr(s[5:]), m, env))
                L.append(f"after       {s[5:].strip()}   {'holds' if ok else 'FAILS'}")
            except ke.BrassError as e:
                L.append(f"after       {s[5:].strip()}   not evaluated ({e})")
    L.append("One input, evaluated; not a proof. `example` clauses make an input part of the interface.")
    return L


def check_examples(w):
    """Evaluate every `example` clause in every interface."""
    sys.path.insert(0, str(HERE.parent))
    import brasseval as ke
    ev = ke.Evaluator(w, strip_comment)
    L, n, bad = [], 0, 0
    for m in w.mods.values():
        for d in m.decls.values():
            for no, l in d.lines:
                s = strip_comment(l).strip()
                if s.startswith("example "):
                    n += 1
                    ev.steps = 0
                    try:
                        ok = ev.truth(ev.eval(ke.parse_expr(s[8:]), m, {}))
                    except ke.BrassError as e:
                        ok = False
                        L.append(f"  fault    {d.short}   {REL}/{m.path.name}:{no}   {s[8:]}   ({e})")
                        bad += 1
                        continue
                    if not ok:
                        bad += 1
                    L.append(f"  {'holds' if ok else 'FAILS':<8} {d.short}   {REL}/{m.path.name}:{no}   {s[8:]}")
    return [f"examples    {n} found, {n - bad} hold, {bad} fail" + ("" if n else "; write `example f(x) == y` under a fn's signature")] + L


RETIRED_FORMS = re.compile(r"^\s*(?:else\s+)?(return|while|match|loop|unbounded)\b|\bSome\(|^\s*(?:data|const)\s[^=]*\b(from)\s")   # forms, not names: `max` is a legal name
CALL = re.compile(r"(?<![\w.@])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\(")


def top_args(s):
    """Arguments of a call, split at top-level commas; s is the text between the parentheses."""
    if not s.strip():
        return []
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    return out + [cur]


def signature(d):
    """A declaration's header text, up to its first contract or example line."""
    head = []
    for _, l in d.lines:
        st = strip_comment(l).strip()
        if head and re.match(r"(before|after|example)\b", st):
            break
        head.append(st)
    return " ".join(head)


WHERE_KW = {"it", "not", "and", "or", "true", "false", "None", "result", "in", "is", "to", "if", "then", "else"}


def bare_where_names(st):
    """Names that open a conjunct of a `where` condition without `it.`; `any`/`all` conditions name their own element."""
    if re.search(r"\b(any|all)\s+[a-z_]\w*\s+in\b", st):
        return []
    out = []
    for cond in re.split(r"\bwhere\b", st)[1:]:
        depth, end = 0, len(cond)
        for j, ch in enumerate(cond):
            if ch in "({[": depth += 1
            elif ch in ")}]":
                if depth == 0: end = j; break
                depth -= 1
            elif ch == "," and depth == 0: end = j; break
        hm = re.search(r"\b(has|when)\b", cond[:end])
        cond = cond[:hm.start() if hm else end]
        for mm in re.finditer(r"(?:^\s*|\band\s+|\bor\s+|\bnot\s+|\(\s*)([a-z_]\w*)\b(?!\s*[(.:])", cond):
            if mm.group(1) not in WHERE_KW:
                out.append(mm.group(1))
    return out


def record_fields(w, m, d, depth=0):
    """The field names of the record a type refines: its own braces, or its base's, followed through refinements."""
    rhs = " ".join(strip_comment(l) for _, l in d.lines).split("=", 1)[1].strip() if "=" in " ".join(l for _, l in d.lines) else ""
    if rhs.startswith("{") or depth > 6:
        return d.fields
    base = rhs.split(" where ", 1)[0].strip()
    k = type_key(MODS_BY_NAME.get(d.module, m), w.decls, base)
    return record_fields(w, MODS_BY_NAME.get(k[0], m), w.decls[k], depth + 1) if k and w.decls[k].kind == "type" else {}


def machine_states(d):
    text = " ".join(strip_comment(l) for _, l in d.lines)
    sm = re.search(r"\bstates\s+(.+?)(?:\s+initial\b|$)", text)
    return [x.strip() for x in sm.group(1).split(",")] if sm else []


def machine_of_type(w, m, text):
    """The machine a type name written in module m denotes, or None."""
    k = type_key(m, w.decls, text.strip())
    return k if k is not None and w.decls[k].kind == "machine" else None


def state_literal(w, m, tok):
    """`Alias.Machine.State` or `Machine.State`, as written in m: (machine key, state), or None."""
    parts = tok.strip().split(".")
    if len(parts) == 3 and parts[0] in m.aliases:
        k = (m.aliases[parts[0]], parts[1])
    elif len(parts) == 2:
        k = (m.name, parts[0])
    else:
        return None
    if k in w.decls and w.decls[k].kind == "machine" and parts[-1] in machine_states(w.decls[k]):
        return k, parts[-1]
    return None


def arg_machine(w, m, d, arg):
    """The machine an argument carries when the argument is plain enough to read: a state literal, a parameter of a
    machine type, or a parameter's field of a machine type. None for anything else; the real checker types the rest."""
    a = arg.strip()
    if not re.fullmatch(r"[A-Za-z_][\w.]*", a):
        return None
    lit = state_literal(w, m, a)
    if lit:
        return lit[0]
    parts = a.split(".")
    if parts[0] in d.params:
        pt = d.params[parts[0]]
        if len(parts) == 1:
            return machine_of_type(w, m, pt)
        rk = type_key(m, w.decls, pt)
        if len(parts) == 2 and rk is not None and w.decls[rk].kind == "type":
            rd = w.decls[rk]
            ft = rd.fields.get(parts[1]) or (rd.conditional.get(parts[1]) or (None, None, None))[2]
            if ft:
                return machine_of_type(w, MODS_BY_NAME.get(rd.module, m), ft)
    return None


def call_args_at(w, m, d, body, idx, st, cm):
    """The resolved callee and the argument texts of a call found at body index idx, or None when the call does not
    resolve or its parentheses do not close in the body."""
    tok = cm.group(1)
    if idx == 0 and tok == d.name:
        return None
    keys = [k for k in resolve(m, w.decls, tok, d.params) if w.decls[k].kind in ("fn", "allow")]
    if not keys:
        return None
    cd = w.decls[max(keys, key=lambda k: len(k[1]))]
    text, j = st, idx
    close = close_paren(text, cm.end() - 1)
    while close < 0 and j + 1 < len(body):
        j += 1; text += " " + body[j][1]; close = close_paren(text, cm.end() - 1)
    if close < 0:
        return None
    return cd, top_args(text[cm.end():close])


BUILTIN_LOOSE = {"Text", "Int", "Bool"}


def loosened_types(w):
    """Lean 8: a record field or a function parameter that had a declared type in the baseline and is a builtin now
    (`Text`, `Int`, `Bool`). Legal, and a weakening the cases cannot see: the checker no longer knows which values it
    holds. Brass's rule is that a repair keeps its types. A warning with the line."""
    base = baseline_world(w)
    if not base:
        return []
    def declared(mod_name, t, decls):
        m = MODS_BY_NAME.get(mod_name)
        return m is not None and type_key(m, decls, t) is not None
    warns = []
    for k, nd in w.decls.items():
        od = base.get(k)
        if od is None:
            continue
        pairs = []
        if nd.kind == "type":
            pairs = [("field", f, od.fields.get(f), nd.fields.get(f)) for f in nd.fields if f in od.fields]
        elif nd.kind in ("fn", "allow"):
            pairs = [("parameter", p_, od.params.get(p_), nd.params.get(p_)) for p_ in nd.params if p_ in od.params]
        for what, name, ot, nt in pairs:
            if ot and nt and nt in BUILTIN_LOOSE and ot.split(".")[-1] not in BUILTINS:      # any non-builtin name is a declared type
                m = w.mods[k[0]]
                no = next((n for n, l in nd.lines if re.search(rf"\b{re.escape(name)}\s*:", l)), nd.lines[0][0])
                warns.append(f"  {m.path.name}:{no}  {what} `{name}` of {nd.short} was {ot} at the start and is {nt} now: the checker can no longer "
                             "tell which values it holds. Keep the type; a field for several machines takes a shared vocabulary and a converter per machine (C22)")
    return warns


def machine_mix(w):
    """Lean 4: a function that enters states of one machine and hands a state of another to a call. Legal, and the
    shape of the defect every trial recorded: an advance audited under a report's states. A warning with its lines."""
    found = {}
    for m in w.mods.values():
        for d in m.decls.values():
            if d.kind != "fn" or not d.body:
                continue
            body = [(no, strip_comment(strip_strings(l))) for no, l in d.body]
            entered = set()
            for no, st in body:
                for em in re.finditer(r"\benters\s+([A-Za-z_][\w.]*)", st):
                    lit = state_literal(w, m, em.group(1))
                    if lit:
                        entered.add(lit[0])
            if not entered:
                continue
            for idx, (no, st) in enumerate(body):
                for cm in CALL.finditer(st):
                    got = call_args_at(w, m, d, body, idx, st, cm)
                    if got is None:
                        continue
                    for arg in got[1]:
                        lit = state_literal(w, m, arg)
                        if lit and lit[0] not in entered:
                            found.setdefault((m, d, cm.group(1), lit[0], tuple(sorted(entered))), []).append(no)
    warns = []
    for (m, d, tok, mk, entered), nos in found.items():
        lines = ", ".join(str(n) for n in sorted(set(nos)))
        warns.append(f"  {m.path.name}:{lines}  {d.name} enters states of {', '.join(w.decls[k].short for k in entered)} and passes a state of "
                     f"{w.decls[mk].short} to {tok}(…): is {w.decls[mk].short} the machine this call describes? A field that must hold a state of "
                     "either machine needs a shared vocabulary type and a converter per machine (C22)")
    return warns


def check_structure(w):
    """Level 1 of the checker: structure only. Every finding is a rejection with a fix line."""
    rej = []
    def reject(m, no, what, fix):
        rej.append((f"{m.path.name}:{no}", what, fix))
    for path, e in w.parse_errors:
        missing = {"'interface'": "`interface`", "'body'": "`body`"}.get(str(e))
        what = f"no {missing} section" if missing else ("no `module` line" if isinstance(e, StopIteration) else "cannot be read as a module")
        rej.append((f"{path.name}:1", what, "a module is `module <name>`, imports, `interface`, optional `private`, then `body`"))
    for m in w.mods.values():
        for no, l in m.interface + m.private:
            for name in bare_where_names(strip_comment(strip_strings(l))):
                if name == "length" or not resolve(m, w.decls, name, {}):
                    reject(m, no, f"`{name}` in a `where` names a field of the value; write `it.{name}` (C33)", f"write `it.{name}`")
        for d in m.decls.values():                    # a field named anywhere else in a type's own condition
            if d.kind != "type" or " where " not in " ".join(strip_comment(l) for _, l in d.lines):
                continue
            fields = set(record_fields(w, m, d))
            for no, l in d.lines:
                st = strip_comment(strip_strings(l))
                if "where" not in st or re.search(r"\b(any|all)\s+[a-z_]\w*\s+in\b", st):
                    continue
                cond = re.split(r"\bwhere\b", st, maxsplit=1)[1]
                cond = re.split(r"\b(?:has|when)\b", cond)[0]
                for mm in re.finditer(r"(?<![.\w])([a-z_]\w*)\b(?!\s*[:.(])", cond):
                    if mm.group(1) in fields and mm.group(1) not in bare_where_names(st):
                        reject(m, no, f"`{mm.group(1)}` in a `where` names a field of the value; write `it.{mm.group(1)}` (C33)", f"write `it.{mm.group(1)}`")
        for d in m.decls.values():
            for no, l in d.lines:
                if HAS.search(strip_comment(l).strip()):
                    reject(m, no, "`where … has` is now a field with `when` (C34)", "move the field into the braces: `name: Type when it.<field> in {States}`")
            for f, (ctrl, sts, ftype) in d.conditional.items():
                no = next((n for n, l in d.lines if re.search(rf"\b{f}\s*:", l)), d.lines[0][0])
                if ctrl is None:
                    reject(m, no, f"`{f}`'s `when` is not a state test on another field", "write `when it.<machine field> in {State, …}`")
                elif not sts or any("." not in s for s in sts):
                    reject(m, no, f"`{f}`'s `when` names a state without its machine", "write every state as `Machine.State`, as outside a machine declaration")
                elif ctrl not in d.fields:
                    reject(m, no, f"`{f}` is present only when `{ctrl}` is in a state, but `{ctrl}` is itself conditional or not a field", f"`{ctrl}` must be an unconditional field of this record")
                if " where " in f" {ftype} ":
                    reject(m, no, f"`{f}` has a presence condition and an unnamed refined type", f"declare the refined type with `type`, then write `{f}: <Name> when …`")
            if d.wrote_data:
                reject(m, d.lines[0][0], f"`data {d.name}` is now `const {d.name}` (C32)", "write `const`")
        if m.old_private:
            reject(m, m.old_private, "`private interface` is now `private` (C31)", "write `private`")
    for imp_mod, imp in w.unresolved_imports:
        m = w.mods[imp_mod]
        no = next((i + 1 for i, l in enumerate(m.text) if l.startswith(f"import {imp} ")), 1)
        reject(m, no, f"import {imp}: no such module in the tree", "import a module that exists, or add it")
    for mod_name, tok in w.unresolved:
        m = w.mods[mod_name]
        no = next((i + 1 for i, l in enumerate(m.text) if tok in strip_comment(strip_strings(l))), 1)
        reject(m, no, f"{tok}: {tok.split('.')[1]} is not declared in {m.aliases[tok.split('.')[0]]}", "name a declaration that exists, or declare it there")
    for m in w.mods.values():
        for i, l in enumerate(m.text, start=1):
            st = strip_comment(strip_strings(l))
            rm = RETIRED_FORMS.search(st)
            if rm:
                word = rm.group(1) or rm.group(2) or "Some"
                reject(m, i, f"`{word}` is not a Brass form", "write a `data` value inline (C26)" if word == "from" else "there is no early exit, `while`, `match`, or `Some`; see the reference's list of forms")
            lm = re.search(r"\blet\s+([a-z_]\w*)\s*=", st)
            if lm:
                reject(m, i, f"let {lm.group(1)} has no type", f"write `let {lm.group(1)}: <Type> = …`")
            for hm in re.finditer(r"@@([a-z_]\w*)", st):
                reject(m, i, f"hole @@{hm.group(1)} is unfilled", "replace the hole with a value of its type")
        for d in m.decls.values():
            if d.kind != "fn":
                continue
            if d.section == "body":
                reject(m, d.body[0][0], f"fn {d.name} has a body and no declaration", f"declare `fn {d.name}(…) -> …` in `interface` or `private`")
                continue
            if not d.body:
                reject(m, d.lines[0][0], f"fn {d.name} is declared and has no body", f"write `fn {d.name}(…) = …` under `body`")
                continue
            ret = signature(d).split("->", 1)[1].strip() if "->" in signature(d) else ""
            is_outcome = ret.startswith("Outcome<")
            if d.wrote_partial:
                reject(m, d.lines[0][0], f"`partial` on fn {d.name}: Brass has no `partial` (C25); `Outcome<…>` alone marks a fn that can fail",
                       "delete `partial`")
            head = strip_comment(d.body[0][1])
            bm = re.match(r"\s*fn\s+\w+\(([^)]*)\)", head)
            names = [x.strip() for x in bm.group(1).split(",") if x.strip()] if bm else []
            if names != list(d.params):
                reject(m, d.body[0][0], f"fn {d.name}'s body names ({', '.join(names)}); its declaration has ({', '.join(d.params)})",
                       f"write `fn {d.name}({', '.join(d.params)}) =`")
            body = [(no, strip_comment(strip_strings(l))) for no, l in d.body]
            for no, st in body:
                expr = st.split("=", 1)[1] if re.match(r"\s*let\s", st) else st
                flat = expr
                while re.search(r"\([^()]*\)", flat):
                    flat = re.sub(r"\([^()]*\)", " x ", flat)
                if re.search(r"\band\b", flat) and re.search(r"\bor\b", flat):
                    reject(m, no, "`and` and `or` mixed at one level", "add parentheses so each level uses one of them")
                for seg in re.split(r"\b(?:and|or|if|then|else)\b|,", flat):
                    if len(re.findall(r"==|!=|<=|>=|(?<![-<\w])<(?![A-Z<])|(?<![->\w])>(?![>\w])", seg)) > 1:
                        reject(m, no, "a chained comparison", "write `a < b and b < c`")
                        break
            for idx, (no, st) in enumerate(body):
                if not is_outcome and re.search(r"[\w)\]]\?", st):
                    reject(m, no, f"`?` in fn {d.name}, which returns {ret}, not Outcome<…>", "handle the Outcome with `is Ok`, or return `Outcome<…>`")
                for cm in CALL.finditer(st):
                    tok = cm.group(1)
                    if idx == 0 and tok == d.name:
                        continue
                    keys = [k for k in resolve(m, w.decls, tok, d.params) if w.decls[k].kind in ("fn", "allow")]
                    if not keys:
                        parts = tok.split(".")
                        ak = access_key(m, w.decls, d.params[parts[0]]) if len(parts) == 2 and parts[0] in d.params else None
                        if ak is not None and (ak[0], f"{ak[1]}.{parts[1]}") not in w.decls:
                            ops = sorted(k[1].split(".", 1)[1] for k in w.decls if k[0] == ak[0] and k[1].startswith(ak[1] + "."))
                            reject(m, no, f"{tok}: {ak[1]} declares no operation {parts[1]}", f"call one of {', '.join(ops) or 'its declared operations'}")
                        continue
                    cd = w.decls[max(keys, key=lambda k: len(k[1]))]
                    text, j = st, idx
                    close = close_paren(text, cm.end() - 1)
                    while close < 0 and j + 1 < len(body):
                        j += 1; text += " " + body[j][1]; close = close_paren(text, cm.end() - 1)
                    if close < 0:
                        continue
                    args = top_args(text[cm.end():close])
                    n = len(args)
                    if n != len(cd.params):
                        reject(m, no, f"{tok}(…) takes {len(cd.params)} argument{'s' if len(cd.params) != 1 else ''} ({', '.join(cd.params)}); {n} given",
                               f"pass {', '.join(cd.params)}")
                        continue
                    callee_mod = w.mods.get(cd.module, m)
                    for arg, (pn, pt) in zip(args, cd.params.items()):          # a state of the wrong machine
                        pm = machine_of_type(w, callee_mod, pt)
                        if pm is None:
                            continue
                        am = arg_machine(w, m, d, arg)
                        if am is not None and am != pm:
                            reject(m, no, f"{tok}(…): {pn} takes a state of {w.decls[pm].short}; `{arg.strip()}` is a state of {w.decls[am].short}",
                                   f"pass a state of {w.decls[pm].short}. A field that must hold a state of either machine needs a shared vocabulary type and a converter per machine (C22)")
    sysm = type("SystemFile", (), {"path": SYSTEM})
    entries, cur = [], None
    for i, l in enumerate(w.system, start=1):
        gm = re.match(r"\s*grants\s+([\w.]+):\s*(.*)", strip_comment(l))
        if gm:
            cur = [i, gm.group(1), gm.group(2)]
            entries.append(cur)
        elif cur is not None and strip_comment(l).strip() and not strip_comment(l).strip().startswith(("limit", "system", "requires")):
            cur[2] += " " + strip_comment(l)
        else:
            cur = None
    for no, target, text in entries:
        mod_name, _, fn = target.rpartition(".")
        m = w.mods.get(mod_name)
        d = m.decls.get(fn) if m else None
        if d is None or d.kind != "fn":
            reject(sysm, no, f"grants {target}: no such function", "name a declared function as `grants <module>.<fn>:`")
            continue
        flat = re.sub(r"\{[^{}]*\}", "", text)
        given = set() if flat.strip() == "none" else set(re.findall(r"([a-z_]\w*)\s*=", flat))
        wanted = set()
        for pn, pt in d.params.items():
            if access_key(m, w.decls, pt) is not None:
                wanted.add(pn)
        for pn in sorted(wanted - given):
            reject(sysm, no, f"grants {target}: access parameter {pn} is not granted", f"add `{pn} = {d.params[pn].split('.')[-1]}` with its bounds")
        for pn in sorted(given - wanted):
            reject(sysm, no, f"grants {target}: {pn} is not an access parameter of {fn}", f"remove {pn}; a grant lists access parameters only")
    L = [f"check       {REL}/*.brass and src/system.brass: parsed, imports and qualified names resolved, declarations and bodies paired,",
         "            calls match parameters, `?` only in fns returning `Outcome`, no `partial`, no holes, every `let` typed,",
         "            each grant names an entry point and exactly its access parameters",
         "not checked has-field access, state edges, contracts, refinements, argument types, termination, unused lets",
         f"result      {len(rej)} rejection{'s' if len(rej) != 1 else ''}" if rej else "result      no rejections at this level"]
    for where, what, fix in rej:
        L.append(f"  {where:<20} {what}")
        L.append(f"  {'':<20} fix: {fix}")
    if not rej:
        L += [""] + program_summary(w)
    return L


def grant_entries(w):
    """(line, target, module, decl) for every `grants` line naming a declared function."""
    entries, cur = [], None
    for i, l in enumerate(w.system, start=1):
        gm = re.match(r"\s*grants\s+([\w.]+):", strip_comment(l))
        if gm:
            mod_name, _, fn = gm.group(1).rpartition(".")
            m = w.mods.get(mod_name)
            d = m.decls.get(fn) if m else None
            if d is not None and d.kind == "fn":
                entries.append((i, gm.group(1), m, d))
    return entries


def negate(c):
    """The else-branch of `c`: `not c`, with a leading `not` cancelled."""
    c = c.strip()
    inner = re.match(r"not\s*\((.*)\)$", c) or re.match(r"not\s+(\w[\w.]*)$", c)
    if inner and inner.group(1).count("(") == inner.group(1).count(")"):
        return inner.group(1)
    return f"not ({c})" if (" and " in c or " or " in c) else f"not {c}"


def guards_for(body, i, pos, indent):
    """The conditions enclosing position `pos` of body line i, outermost first; an else-branch is `negate(c)`.
    Read from indentation and from an inline `if c then … else …` on the line."""
    out = []
    l = body[i][1]; st = l.strip()
    im = re.match(r"(?:else\s+)?if\s+(.+?)\s+then\b", st)
    if im and pos > l.index("then"):                       # an action on the if line itself
        em = re.search(r"\selse\s", l[l.index("then"):])
        out.append(negate(im.group(1)) if em and pos > l.index("then") + em.start() else im.group(1))
    cur = indent(l)
    if re.match(r"else\s+\S", st) and not im:              # `else <action>` on one line: the else-branch of the if above
        for k in range(i - 1, -1, -1):
            qst = body[k][1].strip()
            if indent(body[k][1]) == cur and re.match(r"(?:else\s+)?if\s", qst):
                out.append(negate(re.sub(r"^(else\s+)?if\s+|\s+then.*$", "", qst)))
                break
    for j in range(i - 1, -1, -1):
        pl = body[j][1]; pst = pl.strip()
        if not pst or indent(pl) >= cur:
            continue
        cur = indent(pl)
        m_if = re.match(r"(?:else\s+)?if\s+(.+?)\s+then\s*$", pst)
        if m_if:
            out.append(m_if.group(1))
        elif re.match(r"else\b", pst):
            for k in range(j - 1, -1, -1):
                qst = body[k][1].strip()
                if indent(body[k][1]) == cur and re.match(r"(?:else\s+)?if\s", qst):
                    out.append(negate(re.sub(r"^(else\s+)?if\s+|\s+then.*$", "", qst)))
                    break
    return list(reversed(out))


def summary_lines(w, m, d, held, depth=0, seen=None):
    """Selected checks and actions found in a body, grouped by the conditions enclosing them, in source order.
    A refusal written in an `else` is placed at the `if` that decides it. Helpers are followed one level."""
    seen = seen or {d.key}
    items, loops = [], []                        # items: (sort key, guards, kind, text, sub-lines)
    body = [(no, strip_comment(l)) for no, l in d.body]
    for idx, (no, l) in enumerate(body):          # a one-line body: read the expression after `=`
        hm_ = re.match(r"(\s*)fn\s+\w+\([^)]*\)\s*=\s*(\S.*)$", l)
        if hm_:
            body[idx] = (no, hm_.group(1) + "  " + hm_.group(2))
    def indent(x):
        return len(x) - len(x.lstrip())
    reassigned = {rm.group(1) for _, x in body for rm in [re.match(r"\s*([a-z_]\w*)\s*=[^=]", x)] if rm}
    for i, (no, l) in enumerate(body):
        if not l.strip():
            continue
        ind = indent(l); st = l.strip()
        loops = [(li, b) for li, b in loops if li < ind]
        fm = re.match(r"for\s+\w+\s+in\s+(.+)$", st)
        if fm:
            loops.append((ind, fm.group(1)))
            continue
        rep = f"   repeated: for … in {loops[-1][1]}" if loops else ""
        for em in re.finditer(r"Err\(FailureCode\.(\w+),\s*", l):
            cp = close_paren(l, em.start() + 3)
            text = l[em.end():cp].strip() if cp > 0 else l[em.end():].strip()
            seeded = re.match(r"let\s+([a-z_]\w*)\s*:[^=]*=\s*Err\(", st)
            if seeded and cp == len(l.rstrip()) - 1:
                if seeded.group(1) in reassigned:
                    continue                    # `let last: Outcome<…> = Err(…)`, reassigned below: a seeded value
                items.append((no, guards_for(body, i, em.start(), indent), "stores", f"{em.group(1):<14} {text}   in {seeded.group(1)}: an error value; whether it is returned depends on later lines", []))
                continue
            key = no
            g = guards_for(body, i, em.start(), indent)
            cm = re.match(r"(?:else\s+)?if\s+(.+?)\s+then\s+Err", st)
            tm = re.search(r"\bif\s+(.+?)\s+then\s+.+\s+else\s+Err", st)
            decided = None
            if cm:
                decided = cm.group(1)
            elif tm:
                decided = negate(tm.group(1))
            elif st.startswith("else") or (i and body[i - 1][1].strip() == "else"):
                at = ind if st.startswith("else") else indent(body[i - 1][1])
                for pno, pl in reversed(body[:i]):
                    pst = pl.strip()
                    if indent(pl) == at and re.match(r"(else\s+)?if\s", pst):
                        decided = negate(re.sub(r"^(else\s+)?if\s+|\s+then.*$", "", pst))
                        key = pno + 0.5
                        break
            elif i and body[i - 1][1].rstrip().endswith("then"):
                decided = re.sub(r"^\s*(else\s+)?if\s+|\s+then\s*$", "", body[i - 1][1])
            if decided is not None and g and g[-1] == decided:
                g = g[:-1]                      # the deciding condition is shown as `when`, not as a group
            when = f"   when {decided}" if decided is not None else ""
            items.append((key, g, "refuse", f"{em.group(1):<14} {text}{when}{rep}", []))
        for cm in re.finditer(r"\b([a-z_]\w*)\.([a-z_]\w*)\(", l):
            if cm.group(1) in held:
                cp = close_paren(l, cm.end() - 1)
                call = l[cm.start():cp + 1] if cp > 0 else cm.group(0) + "…)"
                after = l[cp + 1:] if cp > 0 else ""
                after = re.split(r"\s+else\b", after, maxsplit=1)[0]      # an inline then-branch ends at its else
                before_ = l[:cm.start()]
                if after.startswith("?"):
                    note = "failure passes up"
                elif not after.strip() and "=" not in before_.split("then")[-1].split("else")[-1] and not before_.strip().startswith("let"):
                    note = "its result is the branch's value, failure included"
                else:
                    note = "failure kept as a value"
                keys = [k for k in resolve(m, w.decls, f"{cm.group(1)}.{cm.group(2)}", d.params) if w.decls[k].kind == "allow"]
                afters = clauses(w.decls[keys[0]], "after") if keys else []
                reply = ("reply checked by " + "; ".join(afters)) if afters else "reply taken on trust"
                items.append((no, guards_for(body, i, cm.start(), indent), "call", f"{call}   {note};   {reply}{rep}", []))
        for sm in re.finditer(r"enters\s+([\w.]+)", l):
            items.append((no, guards_for(body, i, sm.start(), indent), "state", f"enters {sm.group(1).split('.')[-1]}", []))
        for tok in IDENT.findall(strip_strings(l)):              # a word inside a string literal is not a call
            for k in resolve(m, w.decls, tok, d.params):
                hd = w.decls[k]
                if hd.kind == "fn" and hd.body and k not in seen and depth < 1:
                    seen.add(k)
                    hm = w.mods[hd.module]
                    sub = summary_lines(w, hm, hd, {h.split(":")[0] for h in holds_of(w, hm, hd)}, depth + 1, seen)
                    if sub:
                        items.append((no, guards_for(body, i, l.index(tok), indent), "via", hd.short, sub))
        om = re.search(r"\bOk\(", l)
        if om and not st.startswith("let "):
            items.append((no + 0.9, guards_for(body, i, om.start(), indent), "succeed", st[st.index("Ok("):][:60], []))
    items.sort(key=lambda t: t[0])
    pad = "  " * depth
    out, cur = [], []
    for key, g, kind, text, sub in items:
        common = 0
        while common < min(len(cur), len(g)) and cur[common] == g[common]:
            common += 1
        for lvl in range(common, len(g)):
            out.append(f"  {pad}      {'  ' * lvl}within {g[lvl]}")
        cur = g
        no = int(key)
        out.append(f"  {pad}{no:>4}  {'  ' * len(g)}{kind:<8} {text}")
        out.extend(f"{'  ' * len(g)}{x}" for x in sub)
    return out


def program_summary(w):
    L = ["summary     each granted entry point: the refusals, host calls, state changes, and results found in its source, in",
         "            source order, each with the conditions enclosing it; a refusal written in an else is placed at the if that",
         "            decides it; helpers are followed one level. Read from the text, not executed; it proves nothing."]
    for _, target, m, d in grant_entries(w):
        held = {h.split(":")[0] for h in holds_of(w, m, d)}
        L.append(f"{d.short:<12} holds {', '.join(sorted(held)) or 'nothing'}")
        sig = signature(d)
        for pn, pt in d.params.items():
            full = re.search(rf"\b{pn}\s*:\s*(.+?)(?=,\s*[a-z_]\w*\s*:|\)\s*->|\)\s*$)", sig)
            full = full.group(1).strip() if full else pt
            k = type_key(m, w.decls, pt)
            refined = " where " in full or (k is not None and w.decls[k].kind == "type" and " where " in " ".join(strip_comment(x) for _, x in w.decls[k].lines))
            if refined and pn not in held:
                L.append(f"      boundary  {pn}: {full}   checked before the body runs; a failing argument is refused as InvalidInput")
        L.extend(summary_lines(w, m, d, held) or ["        (no refusals, calls, or state changes found)"])
    return L


def run_scenarios(w, paths):
    """Run entry points against a scripted host and compare the result and the call trace with what a scenario expects.

    A scenario is a JSON file:
      {"entry": "desk.refund",
       "args": {"payment_id": "\"p1\"", "amount": "100", ...},          Brass literals, by parameter name; access
                                                                          parameters are omitted and bound to the host
       "replies": {"store.staff": ["Ok({ badge: \"b1\", ... })"], ...},  per operation, in the order the calls come;
                                                                          an operation with no reply left answers
                                                                          Err(FailureCode.Unavailable)
       "expect": {"result": "Err(Unauthorized)" | "Ok(<literal>)",         a failure is compared by code, a success by value
                  "trace": ["store.staff", "processor.refund(\"p1\", 100, \"k\")", ...]}}
                                                                          an entry may name only the operation, or the
                                                                          operation with the exact arguments
    A test, not a proof: one scripted host, one input, the bodies as written. Nothing here checks a contract."""
    import json
    sys.path.insert(0, str(HERE.parent))
    import brasseval as ke
    L = ["scenarios   each entry point run against a scripted host; the result and the trace of host calls compared with the scenario.",
         "            a test, not a proof: one input, one script, the bodies as written. Contracts are not checked."]
    held_total = failed = 0
    for path in paths:
        name = Path(path).stem
        try:
            sc = json.loads(Path(path).read_text())
            m, d = w.find(sc["entry"])
            if d is None:
                raise KeyError(f"no such entry point {sc['entry']}")
            ev = ke.Evaluator(w, strip_comment); ev.host_module = m
            host = ke.Host(sc.get("replies", {}))
            acc = {h.split(":")[0] for h in holds_of(w, m, d)}
            args, missing = [], []
            for pn in d.params:
                if pn in acc:
                    args.append(host)
                elif pn in sc.get("args", {}):
                    args.append(ev.eval(ke.parse_expr(sc["args"][pn]), m, {}))
                else:
                    missing.append(pn)
            if missing:
                raise KeyError(f"args missing for {', '.join(missing)}")
            got = ev.call(m, d, args)
        except (ke.BrassError, KeyError, ValueError, json.JSONDecodeError) as e:
            failed += 1
            L.append(f"  FAILS    {name}   could not run: {e}")
            continue
        problems = []
        exp = sc.get("expect", {})
        if "result" in exp:
            er = exp["result"].strip()
            if er.startswith("Err("):
                want_code = er[4:-1].split(",")[0].strip().replace("FailureCode.", "")
                ok = isinstance(got, ke.Outcome) and not got.ok and str(got.value).replace("FailureCode.", "") == want_code
            else:
                try:
                    want = ev.eval(ke.parse_expr(er), m, {})
                    ok = got == want
                except ke.BrassError as e:
                    ok, want = False, f"(unreadable: {e})"
            if not ok:
                problems.append(f"result   expected {er}; got {ke.show_outcome(got)}")
        if "trace" in exp:
            want = exp["trace"]
            got_t = host.trace
            for i, w_ in enumerate(want):
                op = w_.split("(")[0].strip()
                if i >= len(got_t):
                    problems.append(f"trace    step {i + 1}: expected {w_}; the program made no further host call")
                    break
                g_op, g_args = got_t[i]
                if g_op != op:
                    problems.append(f"trace    step {i + 1}: expected {w_}; got {g_op}({', '.join(ke.show(a) for a in g_args)})")
                    break
                if "(" in w_:
                    try:
                        want_args = [ev.eval(ke.parse_expr(a), m, {}) for a in top_args(w_[w_.index("(") + 1:w_.rindex(")")])]
                    except ke.BrassError as e:
                        problems.append(f"trace    step {i + 1}: unreadable arguments in {w_}: {e}"); break
                    if want_args != g_args:
                        problems.append(f"trace    step {i + 1}: expected {w_}; got {g_op}({', '.join(ke.show(a) for a in g_args)})")
                        break
            else:
                if len(got_t) > len(want):
                    extra = got_t[len(want)]
                    problems.append(f"trace    step {len(want) + 1}: expected no further host call; got {extra[0]}({', '.join(ke.show(a) for a in extra[1])})")
        if problems:
            failed += 1
            L.append(f"  FAILS    {name}")
            L.extend(f"           {p}" for p in problems)
        else:
            held_total += 1
            L.append(f"  holds    {name}   {ke.show_outcome(got)}   trace: {' → '.join(op for op, _ in host.trace) or 'no host call'}")
    L.insert(2, f"result      {held_total + failed} scenarios, {held_total} hold, {failed} fail")
    return L


def query_id(args, text):
    import hashlib
    return "q:" + hashlib.sha1((" ".join(args) + "\n" + text).encode()).hexdigest()[:8]


def verify(w, qid):
    """Re-run the logged query behind an id and say whether its answer still holds."""
    try:
        rows = [l.rstrip("\n").split("\t") for l in LOG.open()]
    except OSError:
        return [f"verify      {qid}: no log at {LOG}"]
    hit = next((r for r in reversed(rows) if len(r) >= 4 and r[3] == qid), None)
    if hit is None:
        return [f"verify      {qid}: not in the log; cite ids exactly as printed"]
    args = hit[1].split()
    if args and args[0] in ("apply", "propagate"):
        return [f"verify      {qid}   brass {hit[1]}", f"            refused: `{args[0]}` writes files, so re-running it is not a check; run `brass check` instead"]
    text = render(w, args)
    now = query_id(args, text)
    return [f"verify      {qid}   brass {hit[1]}", "            " + ("holds: the same query gives the same answer" if now == qid else f"changed: the answer is now {now}; re-read it")]


def clause_texts(dd):
    """Every before/after/where clause of a declaration, continuation lines joined."""
    out = []
    for _, l in dd.lines:
        st = strip_comment(l).strip()
        if not st:
            continue
        is_clause = st.startswith(("before", "after", "where")) or (dd.kind == "type" and " where " in strip_comment(l))
        if is_clause:
            out.append(st)
        elif out and not DECL_START.match(l) and not st.startswith(("fn", "type", "const", "machine", "access", "allow")) \
                and (len(l) - len(l.lstrip())) >= 4:
            out[-1] += " " + st
    return out


def clause_marker(w, dd, clause, target, direct):
    """How a clause reaches the changed declaration: by name, or through a field of that type."""
    if direct:
        for tok in IDENT.findall(clause):
            if target in resolve(w.mods[dd.module], w.decls, tok, dd.params):
                return "names it directly"
    through, via_data = set(), set()
    for tok in IDENT.findall(clause):
        last = tok.split(".")[-1]
        if target in w.field_types.get(last, ()):
            through.add(last)
        for k in resolve(w.mods[dd.module], w.decls, tok, dd.params):
            if k in w.data_types and w.data_types[k] == target:
                via_data.add(w.decls[k].name)
    parts = []
    if through:
        parts.append("through field " + ", ".join(sorted(through)))
    if via_data:
        parts.append("through data " + ", ".join(sorted(via_data)))
    return "; ".join(parts)


def what_if(w, spec):
    L = []
    if "=" not in spec:
        return ["usage: brass info --if \"<module>.<name> = <new declaration text>\""]
    target, new = spec.split("=", 1)
    m, d = w.find(target.strip())
    if d is None:
        return [f"unknown: {target.strip()}"]
    L.append(f"declaration {d.kind} {d.name}   {m.name}")
    L.append("today       " + " ".join(strip_comment(l).strip() for _, l in d.lines if strip_comment(l).strip()))
    L.append("proposed    " + new.strip())
    L.append("")
    ub = w.used_by[d.key]
    ic = w.closure(d.key)
    L.append(f"used_by     {fmt(ub, w)}")
    L.extend(if_changed_lines(w, d, ic))
    L.append("")
    L.append("clauses to re-check   (every where/before/after in the impact set; marked by how each reaches the change)")
    n = reach = 0
    for k in sorted(ic, key=lambda k: w.decls[k].short):
        dd = w.decls[k]
        clauses = clause_texts(dd)
        if not clauses:
            continue
        L.append(f"  {dd.short}")
        for c in clauses:
            mark = clause_marker(w, dd, c, d.key, k in ub)
            L.append(f"      {c}" + (f"   ({mark})" if mark else ""))
            n += 1
            reach += bool(mark)
    L.append("")
    L.append(f"{n} clauses listed, {reach} reach the change by name or through a field; the rest are in the set by reference only. This proxy does not decide which fail.")
    return L


VIEW = {"verbatim": False}       # latched when a lean call starts: inner renders run with BRASS_LEAN unset


def verbatim():
    return VIEW["verbatim"] or lean_level() >= 5


def numbered(text, start=1):
    if verbatim():          # lean 5: verbatim, so a find block copied from it matches; the header carries the line range
        return list(text)
    return [f"{i:>4}  {l}" for i, l in enumerate(text, start=start)]


def show_module(w, m, rng=None):
    a, b = (1, len(m.text)) if rng is None else rng
    a, b = max(1, a), min(len(m.text), b)
    return [f"file        {REL}/{m.path.name}   lines {a} to {b} of {len(m.text)}"] + numbered(m.text[a - 1:b], start=a)


def show_decl(w, m, d):
    if verbatim():
        L = [f"file        {REL}/{m.path.name}   lines {d.lines[0][0]} to {d.lines[-1][0]}" + (f", body {d.body[0][0]} to {d.body[-1][0]}" if d.body else "")]
        L += [l for _, l in d.lines]
        if d.body:
            L.append("")
            L += [l for _, l in d.body]
        return L
    L = [f"file        {REL}/{m.path.name}"]
    L += [f"{no:>4}  {l}" for no, l in d.lines]
    if d.body:
        L.append("")
        L += [f"{no:>4}  {l}" for no, l in d.body]
    return L


def show_declarations(w, m):
    """A module's declarations: everything above `body`, numbered. The facts an edit needs, at a fraction of the file."""
    end = m.i_body
    if verbatim():
        return [f"file        {REL}/{m.path.name}   declarations, lines 1 to {end} of {len(m.text)}"] + numbered(m.text[:end], start=1)
    return [f"file        {REL}/{m.path.name}   declarations, lines 1 to {end} of {len(m.text)}   (`show {m.name.split('.')[-1]} --body` for the whole file)"] + numbered(m.text[:end], start=1)


def show_system(w):
    return [f"file        src/system.brass   lines 1 to {len(w.system)}"] + numbered(w.system)


def show_index5(w):
    """Lean 5's index: each module with its length, declaration names, and the modules it imports, so the closure of an
    edit can be chosen here; the last line is the next call, written as one bulk read."""
    L = [f"index       {len(w.mods)} modules under {REL}/: length, declarations, imports"]
    for m in w.mods.values():
        names = [d.name for d in m.decls.values() if d.section == "interface" and d.kind != "allow"]
        imps = [i[0].split(".")[-1] for i in m.imports]
        L.append(f"  {m.name.split('.')[-1]:<13}{len(m.text):>4} lines   {'  '.join(names)}" + (f"   ← {' '.join(imps)}" if imps else ""))
    L.append("next        brass show --body <every module you will change or copy, in one call>    "
             "or  brass show --for <module.Declaration …>  for declarations with everything that uses them")
    return L


def show_index(w):
    """Lean 4's bare `show`: one line per module with its declaration names and length, about a twentieth of every
    declaration. The declarations of the modules an edit needs are one more call; nothing unrelated is read first."""
    L = [f"index       {len(w.mods)} modules under {REL}/   `show a b c` for their declarations with contracts;"
         f" `show --body a b c` for whole files"]
    for m in w.mods.values():
        names = [d.name for d in m.decls.values() if d.section == "interface" and d.kind != "allow"]
        L.append(f"  {m.name.split('.')[-1]:<13}{len(m.text):>4} lines   {'  '.join(names)}")
    return L


def answer_limit():
    try:
        return int(os.environ.get("BRASS_ANSWER_LIMIT") or 26000)
    except ValueError:
        return 26000


def paged(blocks, names, verb_hint):
    """Lean 4: whole blocks up to the answer limit, then the names of what was left out. Claude Code files an answer
    over about 30k characters away behind a 2k preview, which costs a further call to read; a bounded answer is seen
    whole, and the rest is one named call."""
    out, size, left = [], 0, []
    for b, name in zip(blocks, names):
        text = "\n".join(b)
        if out and size + len(text) > answer_limit():
            left.append(name)
            continue
        out.append(text)
        size += len(text) + 2
    if left:
        out.append(f"not shown   {', '.join(left)}: an answer stops near {answer_limit() // 1000}k characters so it is not filed away unseen;"
                   f" run `{verb_hint} {' '.join(left)}` for the rest")
    return "\n\n".join(out) + "\n"


USAGE = __doc__.split("No proofs are run.", 1)[1].split("\n", 2)[2].rstrip()


def baseline_world(w):
    """Declarations as they were at the baseline, keyed like w.decls; None where a module has no baseline."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="brass-changes-"))
    base = {}
    for m in w.mods.values():
        text = baseline_text(m)
        if text is None:
            continue
        p = tmp / m.path.name
        p.write_text("\n".join(text) + "\n")
        try:
            bm = Module(p)
        except Exception:
            continue
        for d in bm.decls.values():
            base[d.key] = d
    return base


def ret_text(d):
    head = " ".join(strip_comment(l).strip() for _, l in d.lines if not strip_comment(l).strip().startswith(("before", "after")))
    return head.split("->", 1)[1].strip() if "->" in head else ""


def clauses(d, word):
    return [strip_comment(l).strip() for _, l in d.lines if strip_comment(l).strip().startswith(word)]


HAS = re.compile(r"where\s+(?:it\.)?(\w+)\s+in\s+\{([^}]*)\}\s+has\s+(.+)$")


def has_fields(d):
    """The `when` fields of a record (C34). A `has` clause is read only to reject it."""
    return {f: (c[0], c[1], c[2]) for f, c in d.conditional.items()}


def conditions(d):
    return [strip_comment(l).strip() for _, l in d.lines if "where" in strip_comment(l) and " has " not in strip_comment(l)]


def describe_change(od, nd):
    """What changed in one declaration, as short phrases; interface first, body last."""
    out = []
    if nd.kind in ("fn", "allow"):
        added = [f"{p}: {t}" for p, t in nd.params.items() if p not in od.params]
        removed = [p for p in od.params if p not in nd.params]
        retyped = [f"{p}: {od.params[p]} -> {t}" for p, t in nd.params.items() if p in od.params and od.params[p] != t]
        if added: out.append("parameter added: " + ", ".join(added))
        if removed: out.append("parameter removed: " + ", ".join(removed))
        if retyped: out.append("parameter retyped: " + ", ".join(retyped))
        if ret_text(od) != ret_text(nd): out.append(f"result: {ret_text(od)} -> {ret_text(nd)}")
        if clauses(od, "before") != clauses(nd, "before"): out.append("before changed")
        if clauses(od, "after") != clauses(nd, "after"): out.append("after changed")
    elif nd.kind == "type":
        fa = [f for f in nd.fields if f not in od.fields]
        fr = [f for f in od.fields if f not in nd.fields]
        ft = [f for f in nd.fields if f in od.fields and od.fields[f] != nd.fields[f]]
        if fa: out.append("field added: " + ", ".join(fa))
        if fr: out.append("field removed: " + ", ".join(fr))
        if ft: out.append("field retyped: " + ", ".join(ft))
        oh, nh = has_fields(od), has_fields(nd)
        for f, (mf, sts, _) in nh.items():
            if f not in oh: out.append(f"when field added: {f} (when {mf} in {', '.join(sts)})")
        for f in oh:
            if f not in nh: out.append(f"when field removed: {f}")
        if conditions(od) != conditions(nd): out.append("condition changed")
    if not out and norm(od.lines) != norm(nd.lines):
        out.append("declaration text changed")
    if norm(od.body) != norm(nd.body):
        out.append("body changed" if out else "body changed only; interface unchanged")
    return out


def site_rows(w, sites, base_lines):
    rows = []
    for u, rel, no, text, *_ in sites:
        mark = "unchanged" if text in base_lines.get(u.module, set()) else "edited"
        rows.append(f"      {w.mods[u.module].path.name}:{no:<5} {text}   [{rel}; {mark}]")
    return rows


def baseline_set():
    """An explicit empty baseline is a baseline: everything in the tree is new."""
    b = os.environ.get("BRASS_BASELINE")
    return bool(b) and Path(b).is_dir()


def changes(w):
    base = baseline_world(w)
    if not base and not baseline_set():
        return ["changes     no baseline: set BRASS_BASELINE or run inside a git checkout"]
    base_lines = defaultdict(set)
    for bd in base.values():
        for _, l in bd.lines + bd.body:
            base_lines[bd.module].add(l.strip())
    observed, inspect = [], []
    keys = sorted(set(base) | set(w.decls))
    for k in keys:
        od, nd = base.get(k), w.decls.get(k)
        if od is not None and nd is not None:
            what = describe_change(od, nd)
            if not what:
                continue
            observed.append(f"  {nd.short:<30} {nd.kind:<11} " + "; ".join(what))
            iface = [x for x in what if not x.startswith("body changed")]
            if not iface:
                continue
            sites = use_sites(w, nd)
            if nd.kind in ("fn", "allow"):
                calls = [x for x in sites if "call" in x[1]]
                inspect.append(f"  {nd.short}: call sites")
                inspect.extend(site_rows(w, calls, base_lines) or [f"      none in {REL}/"])
                if nd.name in w.grants:
                    inspect.append(f"      system.brass   grants {nd.name}: {w.grants[nd.name]}   [entry point; lists access parameters only]")
            elif any(not x.startswith(("when field added", "when field removed")) for x in iface):
                inspect.append(f"  {nd.short}: declarations and lines that use it")
                inspect.extend(site_rows(w, sites, base_lines) or [f"      none in {REL}/"])
            for f, (mf, sts, _) in has_fields(nd).items():
                if f in has_fields(od):
                    continue
                pat = re.compile(r"\benters\s+(?:\w+\.)*(" + "|".join(re.escape(x.split(".")[-1]) for x in sts) + r")\b")
                hits = []
                for dd in w.decls.values():
                    for no, l in dd.body:
                        if pat.search(strip_comment(l)):
                            hits.append((dd, "enters", no, l.strip(), True))
                inspect.append(f"  {nd.short}: expressions entering {', '.join(sts)} (must supply {f})")
                inspect.extend(site_rows(w, hits, base_lines) or [f"      none in {REL}/"])
        elif nd is not None:
            observed.append(f"  {nd.short:<30} {nd.kind:<11} added")
        elif od is not None and od.kind != "allow":
            observed.append(f"  {od.short:<30} {od.kind:<11} removed")
            gone = [(d, "names it", no, l.strip(), True) for d in w.decls.values() for no, l in d.lines + d.body
                    if re.search(r"\b" + re.escape(od.name.split(".")[-1]) + r"\b", strip_comment(l))]
            inspect.append(f"  {od.short}: lines still naming it")
            inspect.extend(site_rows(w, gone, base_lines) or [f"      none in {REL}/"])
    src = "$BRASS_BASELINE" if os.environ.get("BRASS_BASELINE") else "git HEAD"
    if not observed:
        return [f"changes     none against {src}", searched_line(w)]
    L = [f"changes     against {src}", "observed"] + observed
    if inspect:
        L += ["sites to inspect"] + inspect
    L.append(searched_line(w))
    L.append("Sites are places to look, not required edits. Nothing here says behavior is preserved.")
    return L


def unknown(w, t):
    """One line for a name that resolves to nothing, with the nearest declarations."""
    import difflib
    names = sorted({d.short for d in w.decls.values()} | {m.split(".")[-1] for m in w.mods})
    near = difflib.get_close_matches(t.split(".", 1)[-1] if t.startswith(SRC.name + ".") else t, names, n=3, cutoff=0.6)
    hint = f"; nearest: {'  '.join(near)}" if near else ""
    return [f"unknown     {t} names no module or declaration in {REL}/{hint}",
            "usage       brass info <module> | brass info <module>.<name> [--in <module> | --established-by | --if-changed] | brass propagate [--dry] | brass changes"]


def allowed_usage():
    """The usage lines this run permits: every verb and flag a gate would refuse is left out."""
    lines = USAGE.splitlines()
    if not os.environ.get("BRASS_INFO_ONLY"):
        return lines
    verbs = {"info", "changes", "propagate"} | ({"check"} if os.environ.get("BRASS_ALLOW_CHECK") else set())
    blocked = ["--effects", "--forms", "--if "] + ([] if os.environ.get("BRASS_ALLOW_AT") else ["--at"])
    out, keep = [], False
    for l in lines:
        m = re.match(r"\s+brass\s+(\S+)?", l)
        if m:
            verb = (m.group(1) or "")
            keep = verb in verbs and not any(b in l for b in blocked)
        elif not l.strip() or l.startswith(("Several", "<module>", "Project")):
            keep = True
        if keep:
            out.append(l)
    return out


def usage(w, note=None):
    out = [BANNER]
    if note:
        out.append(note)
    out.append("usage:")
    out.extend(allowed_usage())
    out.append("modules: " + "  ".join(n.split(".")[-1] for n in w.mods))
    return out


GUIDED_USAGE = """usage:
  brass info <Name>          before you change a declaration: what uses it, and how
  brass propagate            after you change declarations: writes what must follow, as holes to fill
  brass changes              what changed, and the sites still to inspect
  brass check                when you are done: the completion gate"""


LEAN_USAGE = """usage  (several names per call; one `check` when you are done)
  brass show <module> [<module> ...]       declarations of each module, numbered   (--body adds the bodies)
  brass show <module>.<name> [...]         one declaration with its body
  brass info <module>.<name> [...]         what uses a declaration, and how; `info <module>` for an interface
  brass run <module>.<fn> <arg> ...        evaluate a total fn on literal arguments
  brass propagate                          after changing declarations: writes the holes that must follow
  brass check                              the one completion gate: structure, every example, every scenario
  brass summary                            each entry point's refusals, calls, and state changes, read from the text"""


LEAN2_USAGE = """usage  (put several names in one call; run `check` once, when you are done)
  brass show                               every module's declarations, numbered: the whole project's interface in one call
  brass show --body review payment queries the whole files of several modules, in one call
  brass show <module>.<name> [...]         declarations with their bodies
  brass info <module>.<name> [...]         what uses each declaration, and how
  brass run <module>.<fn> <arg> ...        evaluate a total fn on literal arguments
  brass propagate                          after changing declarations: writes the holes that must follow
  brass check                              the completion gate: structure, every example, every scenario, effect order,
                                           and what each entry point you touched now does. A clean check ends with `done`."""

WRITE_OPS = re.compile(r"^(save|append|pay|close|write|put|delete|record|send|post|create|insert|update)", re.I)


def access_ops(w, m, d):
    """name of each access parameter -> {op: is_write} for the access type it holds."""
    out = {}
    for pn, pt in d.params.items():
        k = access_key(m, w.decls, pt)
        if k is None:
            continue
        ops = {}
        for (mod, name), ad in w.decls.items():
            if mod == k[0] and ad.kind == "allow" and name.startswith(k[1] + "."):
                op = name.split(".", 1)[1]
                text = " ".join(strip_comment(l) for _, l in ad.lines)
                ops[op] = bool(WRITE_OPS.match(op)) or "Outcome<Done>" in text
        out[pn] = ops
    return out


def effect_order(w):
    """Warnings: a write, then, on the same path, something that can refuse. An Err undoes nothing (spec 5.1), so the
    write stays behind. A function writes if it calls a write operation of an access it holds, or a helper that writes;
    it can refuse if it holds an `Err(...)` or calls a helper that can. Host failures passed up by `?` are not refusals."""
    fns = {d.key: (m, d) for m in w.mods.values() for d in m.decls.values() if d.kind == "fn" and d.body}
    def callee(m, name):
        if "." in name:
            mm = w.mods.get(m.aliases.get(name.split(".")[0], ""))
            return mm.decls.get(name.split(".", 1)[1]) if mm else None
        return m.decls.get(name)
    def calls(m, d):
        return [(no, c) for no, l in d.body for cm in re.finditer(r"\b((?:[a-z_]\w*\.)?[a-z_]\w*)\(", strip_comment(l))
                for c in [callee(m, cm.group(1))] if c is not None and c.key in fns and c.key != d.key]
    writes, refuses = {}, {}
    for k, (m, d) in fns.items():
        acc = access_ops(w, m, d)
        writes[k] = any(mm.group(1) in acc and acc[mm.group(1)].get(mm.group(2))
                        for _, l in d.body for mm in re.finditer(r"\b([a-z_]\w*)\.(\w+)\(", strip_comment(l)))
        refuses[k] = any("Err(FailureCode." in strip_comment(l) for _, l in d.body)
    for _ in range(6):                           # helpers, a few levels deep
        for k, (m, d) in fns.items():
            for _, c in calls(m, d):
                writes[k] = writes[k] or writes[c.key]
                refuses[k] = refuses[k] or (refuses[c.key] and c.fails)
    warns = []
    ind = lambda x: len(x) - len(x.lstrip())
    for k, (m, d) in fns.items():
        acc = access_ops(w, m, d)
        body = [(no, strip_comment(l)) for no, l in d.body if strip_comment(l).strip()]
        def write_in(l):
            for mm in re.finditer(r"\b((?:[a-z_]\w*\.)?[a-z_]\w*)\(", l):
                n = mm.group(1)
                if n.split(".")[0] in acc and "." in n and acc[n.split(".")[0]].get(n.split(".")[1]):
                    return n
                c = callee(m, n)
                if c is not None and c.key in fns and c.key != k and writes[c.key]:
                    return n
            return None
        def refusal_in(l):
            em = re.search(r"Err\(FailureCode\.(\w+)", l)
            if em:
                return f"Err({em.group(1)})"
            for mm in re.finditer(r"\b((?:[a-z_]\w*\.)?[a-z_]\w*)\(", l):
                c = callee(m, mm.group(1))
                if c is not None and c.key in fns and c.key != k and refuses[c.key] and c.fails:
                    return f"{mm.group(1)}(…)"
            return None
        for i, (no, l) in enumerate(body):
            wn = write_in(l)
            if not wn or refusal_in(l):
                continue
            floor, j = ind(l), i + 1
            while j < len(body):
                no2, l2 = body[j]
                if l2.strip().startswith("else") and ind(l2) <= floor:
                    skip = ind(l2)                         # another branch of an `if` the write sits in or under
                    j += 1
                    while j < len(body) and (ind(body[j][1]) > skip or (ind(body[j][1]) == skip and body[j][1].strip().startswith("else"))):
                        j += 1
                    floor = min(floor, skip)
                    continue
                if ind(l2) < floor:
                    floor = ind(l2)
                hit = refusal_in(l2)
                if hit:
                    warns.append(f"  warning   {m.path.name}:{no}  {wn}(…) writes before {hit} at line {no2}, which can refuse; "
                                 f"an Err undoes nothing. Check what can refuse before you act.")
                    break
                j += 1
    return warns


def touched_entries(w):
    """One line per granted entry point that is new or changed since the baseline, or calls something that changed:
    what it refuses, the host calls it makes in order, and the states it enters (read from the text, helpers one level)."""
    base = baseline_world(w)
    if not base and not baseline_set():
        return []
    changed = set()
    for k, d in w.decls.items():
        od = base.get(k)
        if od is None or [l for _, l in od.lines + od.body] != [l for _, l in d.lines + d.body]:
            changed.add(k)
    names = {k[1] for k in changed}
    out = []
    for _, target, m, d in grant_entries(w):
        body_text = " ".join(strip_comment(l) for _, l in d.body)
        via = []
        if lean_level() >= 5:              # resolved callees, helpers one level down, instead of bare names
            if d.key not in changed:
                seen = set()
                for cd in callees(w, m, d):
                    if cd.key in changed and cd.key not in seen:
                        seen.add(cd.key); via.append(cd.short)
                    for cd2 in callees(w, w.mods[cd.module], cd):
                        if cd2.key in changed and cd2.key not in seen:
                            seen.add(cd2.key); via.append(cd2.short)
                if not via:
                    continue
        elif d.key not in changed and not any(re.search(rf"\b{re.escape(n)}\(", body_text) for n in names):
            continue
        held = {h.split(":")[0] for h in holds_of(w, m, d)}
        lines = summary_lines(w, m, d, held) or []
        refuses, calls, states = [], [], []
        for l in lines:
            r = re.search(r"\brefuse\s+(\w+)", l)
            c = re.search(r"\bcall\s+([a-z_]\w*\.\w+)\(", l)
            st = re.search(r"\bstate\s+enters\s+(\w+)", l)
            if r and r.group(1) not in refuses: refuses.append(r.group(1))
            if c and c.group(1) not in calls: calls.append(c.group(1))
            if st and st.group(1) not in states: states.append(st.group(1))
        new = "new" if d.key not in base else ("calls changed " + ", ".join(via) if via else "changed")
        out.append(f"  {d.short:<28} {new:<8} refuses {', '.join(refuses) or 'nothing'} · calls {' → '.join(calls) or 'nothing'}"
                   + (f" · enters {', '.join(states)}" if states else ""))
    return out


def callees(w, m, d):
    """The functions a body calls, resolved to their declarations."""
    out, seen = [], set()
    for _, l in d.body:
        for cm in CALL.finditer(strip_comment(strip_strings(l))):
            for k in resolve(m, w.decls, cm.group(1), d.params):
                cd = w.decls[k]
                if cd.kind == "fn" and cd.key != d.key and cd.key not in seen:
                    seen.add(cd.key); out.append(cd)
    return out


def host_contract():
    """The host operations this project may call, from host-contract.txt at the project root: one `Access.op` per line,
    `#` comments. None when the file is absent (no contract to check against)."""
    f = ROOT / "host-contract.txt"
    if not f.is_file():
        return None
    return {l.split("#", 1)[0].strip() for l in f.read_text().splitlines() if l.split("#", 1)[0].strip()}


def contract_violations(w):
    """Each `allow` in the tree that the host contract does not list. The host implements only what it publishes;
    a program that declares another operation compiles against nothing at run time."""
    ops = host_contract()
    if ops is None:
        return None
    out = []
    for (mod, name), d in sorted(w.decls.items()):
        if d.kind == "allow" and name not in ops:
            m = w.mods[mod]
            out.append(f"  {m.path.name}:{d.lines[0][0]}  allow {name} is not a host operation: host-contract.txt lists what the host "
                       f"implements. Use one of {', '.join(sorted(o for o in ops if o.split('.')[0] == name.split('.')[0])) or 'its operations'}.")
    return out


def lean_level():
    try:
        return int(os.environ.get("BRASS_LEAN") or 0)
    except ValueError:
        return 1


LEAN3_USAGE = """usage  (several names per call; all your edits in one `apply`; it runs `check` for you)
  brass show                               every module's declarations, numbered: the whole interface in one call
  brass show --body review payment queries the whole files of several modules, in one call
  brass show <module>.<name> [...]         declarations with their bodies
  brass info <module>.<name> [...]         what uses each declaration, and how
  brass apply <<'PATCH' … PATCH            every edit, across every file, in one call; then the full check (format below)
  brass apply --dry <<'PATCH' … PATCH      the same, writing nothing: does each block match?
  brass check                              the completion gate on its own: structure, examples, scenarios, host contract,
                                           effect order, what each touched entry point does. Clean ends with `done`.

patch format: one block per change, any number of blocks and files
  @@@ edit src/desk/review.brass            then @@@ find, the exact text to replace (it must occur once in the file),
  @@@ find                                 then @@@ replace, the new text, then @@@ end
  …
  @@@ replace
  …
  @@@ end
  @@@ new src/desk/advances.brass           a whole new file: its text, then @@@ end
  …
  @@@ end
Blocks for one file apply in order. If any block does not match, nothing is written."""

LEAN4_USAGE_HEAD = """usage  (several names per call; all your edits in one `apply`; it runs `check` for you)
  brass show                               the index: every module, its declaration names and length, one line each
  brass show review payment budget         those modules' declarations with their contracts, numbered; several per call
  brass show --body review payment queries the whole files of several modules, in one call
  brass show --for audit.Entry queries.Row what an edit of these needs: each declaration with its body, then every
                                           declaration that uses it, with its body; several per call
  brass show <module>.<name> [...]         declarations with their bodies
  brass info <module>.<name> [...]         what uses each declaration, and how
  brass apply <<'PATCH' … PATCH            every edit, across every file, in one call; then the full check (format below)
  brass apply --dry <<'PATCH' … PATCH      the same, writing nothing: does each block match?
  brass check                              the completion gate on its own: structure, examples, scenarios, host contract,
                                           effect order, machine states, what each touched entry point does. Clean ends with `done`.

patch format: one block per change, any number of blocks and files
  @@@ decl src/desk/payment.brass pay       a declaration by name: `@@@ interface` then its interface lines (contracts
  @@@ interface                            included), and/or `@@@ body` then its body, each replaced whole; then @@@ end.
  …                                        A name the file does not declare is added. No find text to copy.
  @@@ body
  …
  @@@ end
  @@@ edit src/desk/review.brass            then @@@ find, the text to replace (it must occur once in the file; a wrong
  @@@ find                                 indent is forgiven and reported), then @@@ replace, the new text, then @@@ end
  …
  @@@ replace
  …
  @@@ end
  @@@ new src/desk/advances.brass           a whole new file: its text, then @@@ end. On a file that exists it replaces
  …                                        the whole file and says so; to change part of a file, use `@@@ decl` or `@@@ edit`.
  @@@ end
Blocks for one file apply in order. A block that does not match is marked ✗ and skipped; the others are written, the
check runs, and the answer ends with how many declarations changed. Resend only the ✗ blocks.
An answer longer than about 26k characters stops at a module boundary and names what it left out."""
LEAN4_USAGE = LEAN4_USAGE_HEAD
LEAN6_TRY = """  brass try <<'TRY' … TRY                ask the checker instead of reasoning it out; nothing is written. A patch in apply's
                                           format is applied to a copy and fully checked. A fragment (declarations, `body`,
                                           bodies, `example` lines) is checked as a scratch module that imports every module
                                           under its short name, and its examples are evaluated"""
LEAN5_USAGE = (LEAN4_USAGE_HEAD
               .replace("brass show                               the index: every module, its declaration names and length, one line each",
                        "brass show                               the index: every module, its length, declaration names, and imports")
               .replace("brass show --body review payment queries the whole files of several modules, in one call",
                        "brass show --body review payment queries the whole files of several modules, in one call, verbatim:\n"
                        "                                           no line numbers, so a find block copied from it matches"))
LEAN6_USAGE = LEAN5_USAGE.replace("\n\npatch format:", "\n" + LEAN6_TRY + "\n\npatch format:", 1)
LEAN7_USAGE = (LEAN5_USAGE
               .replace("  brass apply <<'PATCH' … PATCH            every edit, across every file, in one call; then the full check (format below)",
                        "  brass apply <<'PATCH' … PATCH            every edit, across every file, in one call. It checks before it writes: a patch\n"
                        "                                           that does not match or that the check rejects writes nothing and is held, and\n"
                        "                                           your next `apply` amends it (format below)")
               .replace("  brass apply --dry <<'PATCH' … PATCH      the same, writing nothing: does each block match?",
                        "  brass apply --dry <<'PATCH' … PATCH      the same, writing nothing and holding nothing\n"
                        "  brass apply --drop                       discard a held patch")
               .replace("Blocks for one file apply in order. A block that does not match is marked ✗ and skipped; the others are written, the\n"
                        "check runs, and the answer ends with how many declarations changed. Resend only the ✗ blocks.",
                        "Blocks for one file apply in order. When a patch is held, send only what changes: a block with the same file and find\n"
                        "text, the same new file, or the same declaration replaces the held one; any other block applies on top of what is held."))
LEAN8_USAGE = LEAN7_USAGE.replace("effect order, machine states, what each touched entry point does",
                                  "effect order, machine states, types kept, what each touched entry point does")


def parse_patch(text):
    """Blocks from the patch text: ("edit", path, find, replace) or ("new", path, content). Raises ValueError with a line."""
    blocks, lines, i = [], text.split("\n"), 0
    def take_until(markers):
        nonlocal i
        out = []
        while i < len(lines) and lines[i].strip() not in markers:
            out.append(lines[i]); i += 1
        if i >= len(lines):
            raise ValueError(f"block not closed: expected {' or '.join(markers)}")
        return "\n".join(out)
    while i < len(lines):
        l = lines[i].strip()
        if not l:
            i += 1; continue
        m = re.match(r"@@@\s+(edit|new|decl)\s+(\S+)(?:\s+(\S+))?$", l)
        if not m:
            raise ValueError(f"patch line {i + 1}: expected `@@@ edit <file>`, `@@@ new <file>`, or `@@@ decl <file> <name>`, got: {l[:60]}")
        kind, path = m.group(1), m.group(2); i += 1
        if kind == "decl":
            name = m.group(3)
            if not name:
                raise ValueError(f"patch line {i}: `@@@ decl <file> <name>` names the declaration")
            iface = body = None
            while i < len(lines) and lines[i].strip() != "@@@ end":
                tag = lines[i].strip()
                if tag == "@@@ interface":
                    i += 1; iface = take_until(["@@@ body", "@@@ end"])
                elif tag == "@@@ body":
                    i += 1; body = take_until(["@@@ end"])
                elif not tag:
                    i += 1
                else:
                    raise ValueError(f"patch line {i + 1}: a `@@@ decl` block holds `@@@ interface` and/or `@@@ body` parts, got: {tag[:40]}")
            if i >= len(lines):
                raise ValueError("block not closed: expected @@@ end")
            i += 1
            if iface is None and body is None:
                raise ValueError(f"@@@ decl {path} {name}: no `@@@ interface` or `@@@ body` part")
            blocks.append(("decl", path, name, iface, body))
            continue
        if kind == "new":
            content = take_until(["@@@ end"]); i += 1
            blocks.append(("new", path, content))
            continue
        if i >= len(lines) or lines[i].strip() != "@@@ find":
            raise ValueError(f"patch line {i + 1}: `@@@ edit {path}` must be followed by `@@@ find`")
        i += 1
        find = take_until(["@@@ replace"]); i += 1
        repl = take_until(["@@@ end"]); i += 1
        blocks.append(("edit", path, find, repl))
    if not blocks:
        raise ValueError("the patch has no blocks")
    return blocks


def nearest(text, find):
    """Line numbers where the find's first non-blank line appears, to say where the block was probably aimed."""
    first = next((x.strip() for x in find.split("\n") if x.strip()), "")
    hits = [n for n, x in enumerate(text.split("\n"), 1) if first and first in x]
    return hits[:5]


def indent_of(l):
    return len(l) - len(l.lstrip(" "))


def loose_match(cur, find, repl):
    """Lean 4: the find text at another indent. Lines are compared without their leading and trailing spaces; when
    exactly one window of the file matches, the replacement is shifted by the same difference as the first line.
    Returns (new text, line number, find lines, replacement lines, shift) or None. Three of the four refused patches
    in the 2026-10-17 rerun were this: the model guessed the indent of text it had read, two spaces off."""
    F = find.split("\n")
    while F and not F[-1].strip():
        F.pop()
    if not F:
        return None
    C = cur.split("\n")
    FS = [l.strip() for l in F]
    hits = [i for i in range(len(C) - len(F) + 1) if [l.strip() for l in C[i:i + len(F)]] == FS]
    if len(hits) != 1:
        return None
    i = hits[0]
    j = next(k for k, l in enumerate(F) if l.strip())
    shift = indent_of(C[i + j]) - indent_of(F[j])
    R = repl.split("\n")
    while R and not R[-1].strip():
        R.pop()
    def shifted(l):
        if not l.strip():
            return l
        return " " * shift + l if shift > 0 else l[min(-shift, indent_of(l)):]
    new = "\n".join(C[:i] + [shifted(l) for l in R] + C[i + len(F):])
    return new, i + 1, len(F), len(R), shift


def replace_decl(cur, path, name, iface, body):
    """A declaration by name: its interface lines and/or its body replaced whole; a name the module does not declare is
    added, interface lines at the end of the interface section and the body at the end of the file. Returns (text, note)."""
    import tempfile
    if "." in name:
        raise ValueError("name one declaration; an access's operations are edited with the access")
    with tempfile.NamedTemporaryFile("w", suffix=path.suffix, delete=False) as tf:
        tf.write(cur)
    try:
        mod = Module(Path(tf.name))
    except Exception as e:
        os.unlink(tf.name)
        raise ValueError(f"the file does not read as a module ({e})")
    os.unlink(tf.name)
    lines = cur.split("\n")
    d = mod.decls.get(name)
    def span(numbered):
        a, b = numbered[0][0], numbered[-1][0]
        while b > a and not lines[b - 1].strip():
            b -= 1
        return a, b
    def parts(text):
        return text.rstrip("\n").split("\n")
    notes = []
    if body is not None:
        if d is not None and d.body:
            a, b = span(d.body)
            lines[a - 1:b] = parts(body)
            notes.append(f"body replaced (lines {a} to {b}, {b - a + 1} → {len(parts(body))})")
        else:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += [""] + parts(body)
            notes.append("body added at the end of the file")
    if iface is not None:
        if d is not None and d.lines:
            a, b = span(d.lines)
            lines[a - 1:b] = parts(iface)
            notes.append(f"interface replaced (lines {a} to {b}, {b - a + 1} → {len(parts(iface))})")
        else:
            at = (mod.i_priv if mod.i_priv is not None else mod.i_body)      # 0-based index of the section keyword line
            while at > 0 and not lines[at - 1].strip():
                at -= 1
            lines[at:at] = parts(iface) + [""]
            notes.append("interface added at the end of the interface section")
    return "\n".join(lines).rstrip("\n") + "\n", ("declared and " if d is None else "") + "; ".join(notes)


def quiet_blocks(out):
    """Lean 5: plain ✓ blocks become one `written` line by file; a ✓ block with a note (a shifted find, a file replaced
    in full, a declaration added) and every ✗ block keep their own line."""
    by_file, keep = {}, []
    for l in out:
        m = re.match(r"^\s+block \d+\s+✓ (edit|new|decl) (\S+)(.*)$", l)
        noted = m and (";" in m.group(3) or "replaced in full" in m.group(3) or "declared and" in m.group(3))
        if m and not noted:
            name = Path(m.group(2)).stem + (" (new)" if m.group(1) == "new" else "")
            by_file[name] = by_file.get(name, 0) + 1
        else:
            keep.append(l)
    if by_file:
        keep.insert(0, "  written   " + ", ".join(f"{k} ×{v}" if v > 1 else k for k, v in by_file.items()))
    return keep


def try_it(w, text):
    """Lean 6: ask the checker instead of reasoning it out. Nothing is written to the project.
    A patch (apply's format) is applied to a copy of the project and fully checked. A fragment (declarations, `body`,
    bodies, `example` lines) becomes a scratch module that imports every module under its short name, is checked at
    level 1, and has its examples evaluated; only findings in the fragment are reported, by fragment line."""
    import shutil, subprocess, tempfile
    me = str(Path(__file__).resolve())
    tmp = Path(tempfile.mkdtemp(prefix="brass-try-"))
    try:
        proj = tmp / ROOT.name
        shutil.copytree(ROOT, proj, ignore=shutil.ignore_patterns("__pycache__", "brass-logs"))
        env = {k: v for k, v in os.environ.items() if k != "BRASS_LEAN"}
        env.update(BRASS_PROJECT=str(proj), BRASS_NO_LOG="1", BRASS_SRC=SRC.name)
        if "\n@@@ " in "\n" + text:
            r = subprocess.run([sys.executable, me, "apply"], input=text, capture_output=True, text=True,
                               env=dict(env, BRASS_LEAN=str(lean_level())))
            out = r.stdout.rstrip("\n").split("\n")
            if out and out[0].startswith("apply"):
                out[0] = ("try" + out[0][5:]).replace(" written to ", " would be written to ").replace(" written,", " would be written,")
            out = [("  would write" + l[len("  written"):]) if l.startswith("  written ") else l for l in out]
            return out + ["try         nothing was written to your project; send the same patch to `brass apply` to write it"]
        prefix = next(iter(w.mods)).rsplit(".", 1)[0] if w.mods else SRC.name
        ours = [f"import {name} as {name.split('.')[-1]}" for name in w.mods]
        frag = [l for l in text.rstrip("\n").split("\n") if not l.startswith(("module ", "import "))]
        if not any(l.strip() == "interface" for l in frag):
            frag = ["interface"] + frag
        if not any(l.strip() == "body" for l in frag):
            frag = frag + ["body"]
        head = ["# scratch module for brass try", f"module {prefix}.try_scratch"] + ours
        off = len(head) + (0 if text.lstrip().startswith("interface") else 1)
        (proj / "src" / SRC.name / "try_scratch.brass").write_text("\n".join(head + frag) + "\n")
        def at(no):
            return f"fragment line {max(1, int(no) - off)}"
        rej, cur = [], None
        for l in subprocess.run([sys.executable, me, "check"], capture_output=True, text=True, env=env).stdout.split("\n"):
            m = re.match(r"^\s+try_scratch\.brass:(\d+)\s+(.*)$", l)
            if m:
                cur = [at(m.group(1)), m.group(2), ""]; rej.append(cur); continue
            fm = re.match(r"^\s+fix: (.*)$", l)
            if fm and cur is not None:
                cur[2] = fm.group(1)
            cur = None if not fm else cur
        exs = []
        for l in subprocess.run([sys.executable, me, "check", "--examples"], capture_output=True, text=True, env=env).stdout.split("\n"):
            m = re.match(r"^\s+(holds|FAILS|fault)\s+\S+\s+\S*try_scratch\.brass:(\d+)\s+(.*)$", l)
            if m:
                exs.append((m.group(1), at(m.group(2)), m.group(3)))
        warns = []
        if lean_level() >= 4:
            for l in subprocess.run([sys.executable, me, "check"], capture_output=True, text=True, env=dict(env, BRASS_LEAN="4")).stdout.split("\n"):
                if "try_scratch.brass" in l and "enters states of" in l:
                    warns.append("  ⚠ " + re.sub(r"try_scratch\.brass:([\d, ]+)", lambda mm: "fragment line " + ", ".join(str(max(1, int(x) - off)) for x in mm.group(1).split(",") if x.strip()), l.strip()))
        bad = [e for e in exs if e[0] != "holds"]
        out = []
        if rej:
            out.append(f"try         ✗ {len(rej)} rejection{'s' if len(rej) != 1 else ''} in the fragment")
            for where, what, fix in rej:
                out.append(f"  {where:<18} {what}")
                if fix:
                    out.append(f"  {'':<18} fix: {fix}")
        else:
            out.append("try         ✓ the fragment passes this checker: names, imports, calls, arity, machine states, holes, typed lets")
        if exs:
            out.append(f"examples    {len(exs) - len(bad)} of {len(exs)} hold" + ("" if not bad else ":"))
            out += [f"  {k:<6} {where}   {e}" for k, where, e in bad]
        out += warns
        out.append("not checked contracts, refinements, argument types beyond machine states; nothing was written to your project")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


PENDING = ROOT / ".brass-pending"


def block_text(b):
    if b[0] == "edit":
        return f"@@@ edit {b[1]}\n@@@ find\n{b[2]}\n@@@ replace\n{b[3]}\n@@@ end\n"
    if b[0] == "new":
        return f"@@@ new {b[1]}\n{b[2]}\n@@@ end\n"
    return (f"@@@ decl {b[1]} {b[2]}\n" + (f"@@@ interface\n{b[3]}\n" if b[3] is not None else "")
            + (f"@@@ body\n{b[4]}\n" if b[4] is not None else "") + "@@@ end\n")


def block_key(b):
    return (b[0], str((ROOT / b[1]).resolve())) + ((b[2],) if b[0] in ("edit", "decl") else ())


def apply7(text, dry, drop):
    """Lean 7: `apply` checks before it writes. The patch, with anything held from before, is matched in memory and
    checked in a copy of the project. It is written only when every block matches and the check finds no rejection and
    no host operation outside the contract; otherwise nothing is written, the blocks that matched are held, and the
    next `apply` amends them: a block with the same file and find text, the same new file, or the same declaration
    replaces the held one, and any other block applies on top. Warnings and failing examples are reported, not blocking."""
    import shutil, subprocess, tempfile
    if drop:
        had = PENDING.exists()
        PENDING.unlink(missing_ok=True)
        return ["apply       held patch discarded" if had else "apply       nothing was held"]
    held = parse_patch(PENDING.read_text()) if PENDING.exists() else []
    try:
        incoming = parse_patch(text) if text.strip() else []
    except ValueError as e:
        return [f"apply       ✗ cannot read the patch: {e}", "nothing was written" + (f"; {len(held)} held blocks are unchanged" if held else ""),
                "next        fix the patch and run `brass apply` again"]
    if not incoming and not held:
        return ["apply       ✗ the patch has no blocks"]
    keys = {block_key(b) for b in incoming}
    kept = [b for b in held if block_key(b) not in keys]
    blocks = kept + incoming
    state, out, bad = match_blocks(blocks)
    bad_idx = {int(m.group(1)) for m in (re.match(r"\s+block (\d+)\s+✗", l) for l in out) if m}
    def findings(lines):
        keys = set()
        for l in lines:
            m = re.match(r"\s+(\S+\.(?:brass|keel)):\d+\s+(.*)$", l)
            if m:
                keys.add((m.group(1), m.group(2).strip()))
            elif "is not a host operation" in l:
                keys.add(("host", re.sub(r":\d+", "", l.strip())))
        return keys
    before_env = dict(os.environ, BRASS_NO_LOG="1", BRASS_LEAN="5")
    before = findings(subprocess.run([sys.executable, str(Path(__file__).resolve()), "check"], capture_output=True, text=True, env=before_env).stdout.split("\n"))
    tmp = Path(tempfile.mkdtemp(prefix="brass-apply-"))
    try:
        proj = tmp / ROOT.name
        shutil.copytree(ROOT, proj, ignore=shutil.ignore_patterns("__pycache__", "brass-logs", ".brass-pending"))
        for rel, content in state.items():
            (proj / rel).parent.mkdir(parents=True, exist_ok=True)
            (proj / rel).write_text(content)
        env = {k: v for k, v in os.environ.items()}
        env.update(BRASS_PROJECT=str(proj), BRASS_NO_LOG="1", BRASS_SRC=SRC.name, BRASS_LEAN="5")
        check = subprocess.run([sys.executable, str(Path(__file__).resolve()), "check"], capture_output=True, text=True, env=env).stdout.rstrip("\n").split("\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rejected, prior, keep_fix = [], 0, False
    for l in check:                                  # only what this patch adds blocks the write; what was already there is reported
        m = re.match(r"\s+(\S+\.(?:brass|keel)):\d+\s+(.*)$", l)
        if m:
            keep_fix = (m.group(1), m.group(2).strip()) not in before
            prior += 0 if keep_fix else 1
            if keep_fix:
                rejected.append(l)
        elif l.strip().startswith("fix:") and keep_fix:
            rejected.append(l)
    host_bad = any("is not a host operation" in l and ("host", re.sub(r":\d+", "", l.strip())) not in before for l in check)
    files = len(state)
    clean = not bad and not rejected and not host_bad
    if clean and not dry:
        for rel, content in state.items():
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / rel).write_text(content)
        PENDING.unlink(missing_ok=True)
        tail = changed_line(World())
        head = f"apply       ✓ checked, then written: {len(blocks)} block{'s' if len(blocks) != 1 else ''} to {files} file{'s' if files != 1 else ''}" + (f", {len(kept)} of them held from before" if kept else "") + (f"; {prior} rejection{'s' if prior != 1 else ''} already in the tree before it, not caused by this patch" if prior else "")
        return [head] + quiet_blocks(out) + [""] + check[:-1] + tail + check[-1:]
    if clean:
        return [f"apply       ✓ dry run: every block matches and the check passes; nothing written"] + quiet_blocks(out) + [""] + check
    reasons = []
    if bad:
        reasons.append(f"{bad} block{'s' if bad != 1 else ''} did not match")
    if rejected:
        reasons.append(f"the check rejects {sum(1 for l in rejected if not l.strip().startswith('fix:'))} line{'s' if len(rejected) > 2 else ''}")
    if host_bad:
        reasons.append("an operation the host does not provide")
    keep = [b for i, b in enumerate(blocks, 1) if i not in bad_idx]
    if not dry:
        if keep:
            PENDING.write_text("".join(block_text(b) for b in keep))
        else:
            PENDING.unlink(missing_ok=True)
    L = [f"apply       ✗ nothing written: {'; '.join(reasons)}"]
    if prior:
        L.append(f"already     {prior} rejection{'s' if prior != 1 else ''} in the tree before this patch; not blocking, `brass check` lists {'them' if prior != 1 else 'it'}")
    L += [l for l in out if "✗" in l]
    if rejected:
        L.append("rejected    in the patched files:")
        for l in rejected:
            L.append(l)
            m = re.match(r"\s+(\S+\.(?:brass|keel)):(\d+)", l)
            if m:
                rel = next((r for r in state if r.endswith("/" + m.group(1)) or r == m.group(1)), None)
                if rel:
                    lines = state[rel].split("\n")
                    n = int(m.group(2))
                    if 0 < n <= len(lines):
                        L.append(f"  {'':<20} line {n}: {lines[n - 1].strip()[:140]}")
    if host_bad:
        L += [l for l in check if "is not a host operation" in l]
    if dry:
        L.append("dry run     nothing held")
    elif keep:
        L.append(f"held        {len(keep)} block{'s' if len(keep) != 1 else ''} that matched, kept for your next `apply`. Send only what changes: the ✗ blocks, and a block for")
        L.append("            each rejected line. Same file and find text, same new file, or same declaration replaces a held block; any other")
        L.append("            block applies on top of what is held, so its find text may come from your held blocks. `brass apply --drop` discards it.")
    return L


def changed_line(w):
    """One line after an apply: how many declarations differ from the baseline, and how many are new."""
    base = baseline_world(w)
    if not base and not baseline_set():
        return []
    def differs(k):
        return k not in base or norm(base[k].lines) != norm(w.decls[k].lines) or norm(base[k].body) != norm(w.decls[k].body)
    changed = [k for k in w.decls if k in base and differs(k)]
    new = [k for k in w.decls if k not in base]
    mods = {k[0] for k in changed + new}
    return [f"changed     {len(changed)} declaration{'s' if len(changed) != 1 else ''} changed and {len(new)} new, in {len(mods)} module{'s' if len(mods) != 1 else ''}, against the baseline"]


def match_blocks(blocks):
    """Each block matched against the current files, in order, in memory: (new file texts by path, block lines, count of ✗)."""
    state, out, bad = {}, [], 0
    for n, b in enumerate(blocks, 1):
        path = (ROOT / b[1]).resolve()
        if ROOT.resolve() not in path.parents:
            out.append(f"  block {n:<3} ✗ {b[1]}: outside the project"); bad += 1; continue
        rel = str(path.relative_to(ROOT.resolve()))
        if b[0] == "decl":
            if lean_level() < 4:
                out.append(f"  block {n:<3} ✗ decl {b[1]}: `@@@ decl` is a lean 4 form; use `@@@ edit`"); bad += 1; continue
            cur = state[rel] if rel in state else (path.read_text() if path.is_file() else None)
            if cur is None:
                out.append(f"  block {n:<3} ✗ decl {b[1]}: no such file"); bad += 1; continue
            try:
                state[rel], note = replace_decl(cur, path, b[2], b[3], b[4])
            except ValueError as e:
                out.append(f"  block {n:<3} ✗ decl {b[1]} {b[2]}: {e}"); bad += 1; continue
            out.append(f"  block {n:<3} ✓ decl {b[1]} {b[2]}: {note}")
            continue
        if b[0] == "new":
            exists = path.exists() or rel in state
            if exists and lean_level() < 4:
                out.append(f"  block {n:<3} ✗ new {b[1]}: the file exists; use `@@@ edit`"); bad += 1; continue
            if exists:
                old = state[rel] if rel in state else path.read_text()
                state[rel] = b[2].rstrip("\n") + "\n"
                out.append(f"  block {n:<3} ✓ new {b[1]}: the file existed and was replaced in full  ({old.count(chr(10))} lines → {b[2].count(chr(10)) + 1});"
                           " to change part of a file, use `@@@ edit`")
                continue
            state[rel] = b[2].rstrip("\n") + "\n"
            out.append(f"  block {n:<3} ✓ new {b[1]}  ({b[2].count(chr(10)) + 1} lines)")
            continue
        cur = state[rel] if rel in state else (path.read_text() if path.is_file() else None)
        if cur is None:
            out.append(f"  block {n:<3} ✗ edit {b[1]}: no such file"); bad += 1; continue
        k = cur.count(b[2]) if b[2] else 0
        if k == 0 and lean_level() >= 4:
            loose = loose_match(cur, b[2], b[3])
            if loose:
                state[rel], line, nf, nr, shift = loose
                how = (f"the find text was indented {abs(shift)} space{'s' if abs(shift) != 1 else ''} {'less' if shift > 0 else 'more'} than the file; the replacement was shifted to match"
                       if shift else "the find text differed from the file only in spacing")
                out.append(f"  block {n:<3} ✓ edit {b[1]}:{line}  ({nf} lines → {nr}); {how}")
                continue
        if k != 1:
            where = nearest(cur, b[2])
            hint = f"; its first line appears at line {', '.join(map(str, where))}" if where else "; its first line appears nowhere"
            out.append(f"  block {n:<3} ✗ edit {b[1]}: the find text occurs {k} times, not once{hint if k == 0 else ''}"
                       + ("" if k == 0 else f" (at lines {', '.join(map(str, nearest(cur, b[2])))})")); bad += 1
            continue
        line = cur[:cur.index(b[2])].count("\n") + 1
        state[rel] = cur.replace(b[2], b[3], 1)
        out.append(f"  block {n:<3} ✓ edit {b[1]}:{line}  ({b[2].count(chr(10)) + 1} lines → {b[3].count(chr(10)) + 1})")
    return state, out, bad


def apply_patch(text, dry):
    """Validate every block against the current files; write all or nothing; then the full lean check."""
    try:
        blocks = parse_patch(text)
    except ValueError as e:
        return [f"apply       ✗ cannot read the patch: {e}", "nothing was written. The format:",
                "  @@@ edit <file>      then @@@ find, the exact text (once in the file), @@@ replace, the new text, @@@ end",
                "  @@@ new <file>       then the whole file, then @@@ end",
                "next        fix the patch and run `brass apply` again"]
    state, out, bad = match_blocks(blocks)
    files = len(state)
    partial = bad > 0 and lean_level() >= 4
    if bad and not partial:
        return ([f"apply       ✗ {bad} of {len(blocks)} block{'s' if len(blocks) != 1 else ''} {'do' if bad != 1 else 'does'} not match; nothing was written"] + out
                + ["next        fix the blocks marked ✗ (copy the find text from the file exactly) and run `brass apply` again"])
    if partial and not state:
        return ([f"apply       ✗ no block matched; nothing was written"] + out
                + ["next        fix the blocks marked ✗ and run `brass apply` again"])
    if dry:
        return ([f"apply       ✓ dry run: all {len(blocks)} blocks match, {files} file{'s' if files != 1 else ''}; nothing written" if not partial
                 else f"apply       ⚠ dry run: {len(blocks) - bad} of {len(blocks)} blocks match; nothing written"] + out)
    for rel, content in state.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    if lean_level() >= 5:
        out = quiet_blocks(out)
    head = (f"apply       ✓ {len(blocks)} block{'s' if len(blocks) != 1 else ''} written to {files} file{'s' if files != 1 else ''}" if not partial
            else f"apply       ⚠ {len(blocks) - bad} of {len(blocks)} blocks written to {files} file{'s' if files != 1 else ''}; {bad} not written, marked ✗: resend only those")
    w2 = World()
    check = lean_check(w2)
    tail = changed_line(w2) if lean_level() >= 4 else []
    if partial:
        tail.append(f"not written {bad} block{'s' if bad != 1 else ''} marked ✗ above; fix and resend only those blocks")
    return [head] + out + [""] + check[:-1] + tail + check[-1:]


def converter_coverage(w):
    """Coverage for the converters a project designates in converters.txt (one `module.fn` per line; outside the language).
    A converter takes one machine-typed parameter. A state is covered only by a direct example, `example f(<that state>) == …`;
    the check reports separately the states with no direct example, the examples that fail, and those it could not evaluate.
    None when the file is absent."""
    f = ROOT / "converters.txt"
    if not f.is_file():
        return None
    names = [l.split("#", 1)[0].strip() for l in f.read_text().splitlines() if l.split("#", 1)[0].strip()]
    results = {}
    for line in check_examples(w):
        mm = re.match(r"\s+(holds|FAILS|fault)\s+\S+\s+(\S+:\d+)", line)
        if mm:
            results[mm.group(2)] = mm.group(1)
    out, bad = [], False
    for name in names:
        m, d = w.find(name)
        if d is None or d.kind != "fn":
            out.append(f"  ✗ {name}: not a total fn in the tree"); bad = True; continue
        if len(d.params) != 1:
            out.append(f"  ✗ {name}: a converter takes exactly one parameter"); bad = True; continue
        k = type_key(m, w.decls, list(d.params.values())[0])
        mach = w.decls.get(k) if k else None
        if mach is None or mach.kind != "machine":
            out.append(f"  ✗ {name}: its parameter is not a machine type"); bad = True; continue
        text = " ".join(strip_comment(l) for _, l in mach.lines)
        sm = re.search(r"\bstates\s+(.+?)(?:\s+initial\b|$)", text)
        states = [x.strip() for x in sm.group(1).split(",")] if sm else []
        covered, failing, unevaluable = set(), [], []
        for no, l in d.lines:
            em = re.match(rf"\s*example\s+{re.escape(d.name)}\(\s*([\w.]+)\s*\)\s*==", strip_comment(l))
            if not em:
                continue
            parts = em.group(1).split(".")
            if len(parts) >= 2 and parts[-2] == mach.name and parts[-1] in states:
                covered.add(parts[-1])
            status = results.get(f"{REL}/{m.path.name}:{no}")
            if status == "FAILS":
                failing.append(f"line {no}")
            elif status != "holds":
                unevaluable.append(f"line {no}")
        missing = [x for x in states if x not in covered]
        if not missing and not failing and not unevaluable:
            out.append(f"  ✓ {name}: a passing direct example for every state of {mach.name} ({len(states)})")
            continue
        bad = True
        parts_ = []
        if missing: parts_.append("no direct example for " + ", ".join(missing))
        if failing: parts_.append(f"{len(failing)} example{'s' if len(failing) != 1 else ''} fail ({', '.join(failing)})")
        if unevaluable: parts_.append(f"{len(unevaluable)} could not be evaluated ({', '.join(unevaluable)})")
        out.append(f"  ✗ {name} ({mach.name}): " + "; ".join(parts_))
    head = "converters  " + ("✗ coverage not established" if bad else "✓ every designated converter covers its machine")
    return [head] + out, bad


def lean_check(w):
    """One call, everything: structure, then every example and every scenario. Short when clean; `done` ends it."""
    full = check_structure(w)
    rejected = [l for l in full if re.match(r"\s+\S+\.(brass|keel):\d+", l) or l.strip().startswith("fix:")]
    if rejected:
        n = sum(1 for l in rejected if not l.strip().startswith("fix:"))
        return [f"check       {n} rejection{'s' if n != 1 else ''}"] + rejected + ["next        fix these, then run `brass check` again"]
    out = ["check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants"]
    failing = False
    ex = check_examples(w)
    head = next((l for l in ex if l.startswith("examples")), "")
    if re.search(r"\b0 found", head):
        out.append("examples    none in the tree")
    else:
        out.append(("✓ " if " 0 fail" in head else "✗ ") + head.split(None, 1)[1] if head else "examples    (no result)")
        out[-1] = "examples    " + out[-1]
        if " 0 fail" not in head:
            failing = True
            out += [l for l in ex if l.strip().startswith("FAILS")]
    scen = sorted(str(p) for p in (ROOT / "scenarios").glob("*.json")) if (ROOT / "scenarios").is_dir() else []
    if scen:
        r = run_scenarios(w, scen)
        held = next((l for l in r if l.startswith("result")), "")
        ok = " 0 fail" in held
        out.append("scenarios   " + ("✓ " if ok else "✗ ") + held.replace("result", "").strip())
        if not ok:
            failing = True
            out += [l for l in r if l.strip().startswith("FAILS") or l.startswith("           ")]
    else:
        out.append("scenarios   none under scenarios/")
    if lean_level() >= 2:
        bad = contract_violations(w)
        if bad is not None:
            out.append("host        " + (f"✗ {len(bad)} operation{'s' if len(bad) != 1 else ''} the host does not provide" if bad else "✓ every host operation is in host-contract.txt"))
            out += bad
            failing = failing or bool(bad)
        cov = converter_coverage(w)
        if cov is not None:
            out += cov[0]
            failing = failing or cov[1]
        warns = effect_order(w)
        out.append("effects     " + (f"✗ {len(warns)} write{'s' if len(warns) != 1 else ''} before a possible refusal" if warns else "✓ no write before a possible refusal"))
        out += warns
        failing = failing or bool(warns)
        touched = touched_entries(w)
        if touched:
            out.append("touched     each entry point you added or changed, as it now reads:")
            out += touched
    warned = False
    if lean_level() >= 8:
        loose = loosened_types(w)
        out.append("types       " + (f"⚠ {len(loose)} declared type{'s' if len(loose) != 1 else ''} loosened to a builtin" if loose
                                     else "✓ no declared type loosened to a builtin"))
        out += loose
        warned = warned or bool(loose)
    if lean_level() >= 4:
        mix = machine_mix(w)
        out.append("machines    " + (f"⚠ {len(mix)} call{'s' if len(mix) != 1 else ''} passing a state of a machine the function does not enter"
                                     if mix else "✓ every state passed to a call belongs to a machine the function enters, or the function enters none"))
        out += mix
        warned = warned or bool(mix)
    out.append("not checked contracts, refinements beyond the boundary, state edges, argument types beyond machine states: the real checker will")
    out.append("next        fix the items marked ✗ above, then run `brass check` again" if failing
               else "done        nothing else to run; read the ⚠ lines above before you finish" if warned else "done        nothing else to run")
    return quiet_check(out) if lean_level() >= 5 else out


QUIET = {"check": "structure", "host": "host contract", "effects": "effect order", "machines": "machine states", "converters": "converters", "types": "types kept"}


def quiet_check(out):
    """Lean 5: everything that passed on one line; ✗ and ⚠ lines, touched, and the last line in full. A row of ✓ lines
    teaches the eye to skip the one that matters."""
    passed, rest = [], []
    for l in out:
        m = re.match(r"^(\w+)\s+✓\s*(.*)$", l)
        if m and m.group(1) in QUIET:
            passed.append(QUIET[m.group(1)])
        elif m and m.group(1) == "examples":
            hm = re.search(r"(\d+) hold", m.group(2))
            passed.append(f"examples ({hm.group(1)} hold)" if hm else "examples")
        elif re.match(r"^(scenarios   none|examples    none|not checked )", l):
            continue
        else:
            rest.append(l)
    return ([f"check       ✓ {' · '.join(passed)}"] if passed else []) + rest


def guided_check(w):
    """`check` as a terminal gate: what passed, what is not checked, and nothing else to run."""
    full = check_structure(w)
    rejected = [l for l in full if re.match(r"\s+\S+\.(brass|keel):\d+", l) or l.strip().startswith("fix:")]
    if rejected:
        n = sum(1 for l in rejected if not l.strip().startswith("fix:"))
        return [f"check       {n} rejection{'s' if n != 1 else ''}"] + rejected + ["next        fix these, then run `brass check` again"]
    out = ["check       ✓ names and imports   ✓ declarations and bodies paired   ✓ calls match parameters   ✓ no holes   ✓ grants",
           "not checked contracts, states, argument types, refinements: the real checker will"]
    scen = sorted(str(p) for p in (ROOT / "scenarios").glob("*.json")) if (ROOT / "scenarios").is_dir() else []
    if scen:
        r = run_scenarios(w, scen)
        held = next((l for l in r if l.startswith("result")), "")
        out.append("scenarios   " + held.replace("result", "").strip())
        out += [l for l in r if l.strip().startswith("FAILS") or l.startswith("           ")]
        if "0 fail" not in held:
            out.append("next        fix the failing scenarios, then run `brass check` again")
            return out
    out.append("done        nothing else to run")
    return out


def guided_next(w, argv, text):
    """The one next step that makes sense after this answer, from the tree's state."""
    verb = argv[0] if argv else ""
    if verb == "info" and len(argv) >= 2:
        m, d = w.find(argv[1])
        if d is None:
            return ""
        users = w.used_by.get(d.key, set())
        mods = {u[0] for u in users}
        if not users:
            return "next        nothing else uses this; change it freely"
        return (f"next        {len(users)} declaration{'s' if len(users) != 1 else ''} in {len(mods)} module{'s' if len(mods) != 1 else ''} use this. "
                "If you change it, run `brass propagate` afterward")
    if verb == "propagate":
        holes = re.search(r"^holes\s+(\d+)", text, re.M)
        if holes:
            return f"next        fill the {holes.group(1)} hole{'s' if holes.group(1) != '1' else ''} above, then run `brass changes`"
        if "no interface change" in text:
            return "next        nothing to propagate; when you are done, run `brass check`"
        return "next        inspect the sites listed above; when they are right, run `brass check`"
    if verb == "changes":
        unchanged = len(re.findall(r"\[[^\]]*; unchanged\]", text))
        if unchanged:
            return f"next        {unchanged} listed site{'s' if unchanged != 1 else ''} still unchanged: inspect each; when they are right, run `brass check`"
        return "next        when you are done, run `brass check`"
    return ""


def render(w, argv):
    """Every block for one invocation, as text without the query id (so ids are stable)."""
    blocks = []
    if os.environ.get("BRASS_GUIDED"):
        verb = argv[0] if argv else ""
        flags = [a for a in argv[1:] if a.startswith("--")]
        if verb not in ("info", "propagate", "changes", "check") or flags or (verb == "info" and len(argv) != 2):
            return GUIDED_USAGE + "\n"
        if verb == "check":
            return "\n".join(guided_check(w)) + "\n"
        os.environ.pop("BRASS_GUIDED")
        try:
            text = render(w, argv)
        finally:
            os.environ["BRASS_GUIDED"] = "1"
        nxt = guided_next(w if verb != "propagate" else World(), argv, text)
        return text + (nxt + "\n" if nxt else "")
    if os.environ.get("BRASS_LEAN"):
        VIEW["verbatim"] = lean_level() >= 5
        verb = argv[0] if argv else ""
        lean_verbs = {"show", "info", "run", "propagate", "changes", "check", "verify"} | ({"summary"} if lean_level() >= 2 else set()) | ({"apply"} if lean_level() >= 3 else set()) | ({"try"} if lean_level() == 6 else set())
        lean_usage = LEAN8_USAGE if lean_level() >= 8 else LEAN7_USAGE if lean_level() >= 7 else LEAN6_USAGE if lean_level() >= 6 else LEAN5_USAGE if lean_level() >= 5 else LEAN4_USAGE if lean_level() >= 4 else LEAN3_USAGE if lean_level() >= 3 else LEAN2_USAGE if lean_level() >= 2 else LEAN_USAGE
        if argv and verb not in lean_verbs and verb not in ("help", "--help", "-h"):
            return f"unknown command: {verb}\n" + lean_usage + "\nmodules: " + "  ".join(n.split(".")[-1] for n in w.mods) + "\n"
        if verb == "apply" and lean_level() >= 7:
            drop = "--drop" in argv
            src = next((x for x in argv[1:] if not x.startswith("--")), None)
            text = "" if drop else (Path(src).read_text() if src and src != "-" and Path(src).is_file() else sys.stdin.read())
            return "\n".join(apply7(text, "--dry" in argv, drop)) + "\n"
        if verb == "try" and lean_level() >= 6:
            src = next((x for x in argv[1:] if not x.startswith("--")), None)
            text = Path(src).read_text() if src and src != "-" and Path(src).is_file() else sys.stdin.read()
            return "\n".join(try_it(w, text)) + "\n"
        if verb == "apply" and lean_level() >= 3:
            src = next((x for x in argv[1:] if not x.startswith("--")), None)
            text = Path(src).read_text() if src and src != "-" and Path(src).is_file() else sys.stdin.read()
            return "\n".join(apply_patch(text, "--dry" in argv)) + "\n"
        if not argv or verb in ("help", "--help", "-h"):
            return lean_usage + "\nmodules: " + "  ".join(n.split(".")[-1] for n in w.mods) + "\n"
        if verb == "check" and len(argv) == 1:
            return "\n".join(lean_check(w)) + "\n"
        if verb == "check":
            return "check takes no flags here: `brass check` runs structure, every example, and every scenario in one call\n"
        if verb == "summary":
            return "\n".join(program_summary(w)) + "\n"
        if verb == "show" and len(argv) == 1 and lean_level() >= 5:
            return "\n".join(show_index5(w)) + "\n"
        if verb == "show" and len(argv) == 1 and lean_level() >= 4:
            return "\n".join(show_index(w)) + "\n"
        if verb == "show" and len(argv) == 1 and lean_level() >= 2:
            return "\n\n".join("\n".join(show_declarations(w, m)) for m in w.mods.values()) + "\n"
        if verb == "show" and len(argv) == 1:
            return lean_usage + "\nmodules: " + "  ".join(n.split(".")[-1] for n in w.mods) + "\n"
        if verb == "show" and len(argv) >= 2:
            missing = [t for t in argv[1:] if t != "system" and not t.startswith("--") and w.module(re.sub(r":\d+-\d+$", "", t)) is None and w.find(t)[1] is None]
            if missing:
                return "\n".join(unknown(w, t)[0] for t in missing) + "\nmodules: " + "  ".join(n.split(".")[-1] for n in w.mods) + "\n"
        if verb == "show" and "--for" in argv and lean_level() >= 4:
            names = [t for t in argv[1:] if not t.startswith("--")]
            blocks, labels, seen = [], [], set()
            for t in names:
                m, d = w.find(t)
                if d is None:
                    blocks.append([unknown(w, t)[0]]); labels.append(t); continue
                users = []
                for u, *_ in use_sites(w, d):
                    if u.key != d.key and all(u.key != x.key for x in users):
                        users.append(u)
                if lean_level() >= 8 and d.kind in ("access", "allow"):     # every entry point holds it: names, not bodies
                    names_ = sorted({u.short for u, *_ in use_sites(w, d) if u.key != d.key})
                    blocks.append([f"for         {d.short}: an access; {len(names_)} declarations use it, named here without bodies "
                                   "(`show --for` one of them, or `info`, for more)", "  " + "  ".join(names_)] + show_decl(w, m, d))
                    labels.append(t); seen.add(d.key)
                    continue
                if d.kind == "type":                      # a record's constructors have callers; an edit of the record reaches them
                    for u in list(users):
                        if u.kind == "fn":
                            for u2, *_ in use_sites(w, u):
                                if u2.key != d.key and all(u2.key != x.key for x in users):
                                    users.append(u2)
                if d.key not in seen:
                    seen.add(d.key)
                    blocks.append([f"for         {d.short}: used by " + (", ".join(u.short for u in users) if users else f"nothing else in {REL}")] + show_decl(w, m, d))
                    labels.append(t)
                for u in users:
                    if u.key in seen:
                        continue
                    seen.add(u.key)
                    blocks.append([f"user        {u.short}"] + show_decl(w, w.mods[u.module], u)); labels.append(u.short)
            return paged(blocks, labels, "show --for")
        if verb == "show" and len(argv) >= 2 and lean_level() >= 4:
            body = "--body" in argv
            names = [t for t in argv[1:] if t != "--body"]
            blocks = []
            for t in names:
                m = w.module(t)
                if m is not None and not body and not re.match(r"^.+:\d+-\d+$", t):
                    blocks.append(show_declarations(w, m))
                    continue
                saved_lean = os.environ.pop("BRASS_LEAN")
                try:
                    blocks.append(render(w, ["show", t]).rstrip("\n").split("\n"))
                finally:
                    os.environ["BRASS_LEAN"] = saved_lean
            return paged(blocks, names, "show --body" if body else "show")
        if verb == "show" and len(argv) >= 2 and "--body" not in argv:
            blocks = []
            for t in argv[1:]:
                m = w.module(t)
                if m is not None and not re.match(r"^.+:\d+-\d+$", t):
                    blocks.append(show_declarations(w, m))
                    continue
                saved_lean = os.environ.pop("BRASS_LEAN")
                try:
                    blocks.append(render(w, ["show", t]).rstrip("\n").split("\n"))
                finally:
                    os.environ["BRASS_LEAN"] = saved_lean
            return "\n\n".join("\n".join(b) for b in blocks) + "\n"
        argv = [a for a in argv if a != "--body"]
    if os.environ.get("BRASS_INFO_ONLY") and argv:
        # Info-only condition: dependency discovery, no verification verbs.
        blocked = ("--effects", "--forms", "--if") if os.environ.get("BRASS_ALLOW_AT") else ("--at", "--effects", "--forms", "--if")
        verbs = ("info", "changes", "propagate", "check") if os.environ.get("BRASS_ALLOW_CHECK") else ("info", "changes", "propagate")
        if argv[0] not in verbs or any(f in argv for f in blocked):
            at = " [--at <line>]" if os.environ.get("BRASS_ALLOW_AT") else ""
            chk = " | brass check" if "check" in verbs else ""
            names = "`brass info`, `brass propagate`, `brass changes`, and `brass check`" if chk else "`brass info`, `brass propagate`, and `brass changes`"
            return (f"not available in this run: only {names}\n"
                    f"usage       brass info <module> | brass info <module>.<name> [--in <module> | --established-by | --if-changed]{at} | brass propagate [--dry] | brass changes{chk}\n")
    if os.environ.get("BRASS_LIMITED") and argv:
        # Run 9 condition Q: only the two question-answering verbs. Everything else is refused, not hidden.
        limited_ok = argv[0] == "info" and not any(f in argv for f in ("--at", "--effects", "--forms"))
        limited_ok = limited_ok or (argv[0] == "check" and "--examples" in argv)
        if not limited_ok:
            return "\n".join(usage(w, "not available in this run: only `brass info <thing>` and `brass check --examples`")) + "\n"
    if not argv or argv[0] in ("help", "--help", "-h"):
        blocks.append(usage(w))
    elif argv[0] == "info":
        rest = argv[1:]
        at = None
        if "--at" in rest:
            i = rest.index("--at")
            if i + 1 < len(rest) and rest[i + 1].isdigit():
                at = int(rest[i + 1])
                rest = rest[:i] + rest[i + 2:]
        in_module = None
        if "--in" in rest:
            i = rest.index("--in")
            if i + 1 < len(rest):
                in_module = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
        flags = {a for a in rest if a.startswith("--")}
        targets = [a for a in rest if not a.startswith("--")]
        if "--if" in flags:
            blocks.append(what_if(w, " ".join(targets)))
        elif "--forms" in flags:
            blocks.append(forms(w))
        elif not targets:
            if "--names" in flags:
                blocks.append(names_all(w))
            elif "--holds" in flags:
                blocks.append(holds_all(w))
            else:
                blocks.append(info_system(w))
        else:
            for t in targets:
                m = w.module(t)
                if m is not None:
                    blocks.append(names_module(w, m) if "--names" in flags else info_module(w, m))
                    continue
                m, d = w.find(t)
                if d is not None:
                    if "--established-by" in flags:
                        blocks.append(established_by(w, m, d))
                    elif "--effects" in flags:
                        blocks.append(effects(w, m, d))
                    elif at is not None:
                        blocks.append(at_line(w, m, d, at))
                    else:
                        blocks.append(info_decl(w, m, d, "--if-changed" in flags, in_module))
                else:
                    blocks.append(unknown(w, t))
    elif argv[0] == "changes":
        blocks.append(changes(w))
    elif argv[0] == "propagate":
        blocks.append(propagate(w, "--dry" in argv))
    elif argv[0] == "review" and len(argv) >= 2:
        m = w.module(argv[1])
        blocks.append(review(w, m) if m is not None else usage(w, f"unknown: {argv[1]}"))
    elif argv[0] == "run" and len(argv) >= 2:
        blocks.append(run_fn(w, argv[1], argv[2:]))
    elif argv[0] == "check" and "--examples" in argv:
        blocks.append(check_examples(w))
    elif argv[0] == "check" and ("--scenario" in argv or "--scenarios" in argv):
        if "--scenario" in argv:
            paths = argv[argv.index("--scenario") + 1:]
        else:
            paths = sorted(str(p) for p in (ROOT / "scenarios").glob("*.json"))
        blocks.append(run_scenarios(w, paths) if paths else ["scenarios   none found; put <name>.json files under scenarios/ or name one with --scenario <file>"])
    elif argv[0] == "check":
        blocks.append(check_structure(w))
    elif argv[0] == "verify" and len(argv) >= 2:
        for q in argv[1:]:
            blocks.append(verify(w, q))
    elif argv[0] == "show" and len(argv) >= 2:
        for t in argv[1:]:
            if t == "system":
                blocks.append(show_system(w))
                continue
            rng = None
            rm = re.match(r"^(.+):(\d+)-(\d+)$", t)
            if rm:
                t, rng = rm.group(1), (int(rm.group(2)), int(rm.group(3)))
            m = w.module(t)
            if m is not None:
                blocks.append(show_module(w, m, rng))
                continue
            m, d = w.find(t)
            if d is not None:
                blocks.append(show_decl(w, m, d))
            else:
                blocks.append(usage(w, f"unknown: {t}"))
    else:
        blocks.append(usage(w))
    out = []
    for i, b in enumerate(blocks):
        if i:
            out.append("")
        out.extend(b)
    return "\n".join(out) + "\n"


def main(argv):
    if argv[:1] == ["monkey"]:      # not a command: not in help, not in BRASS.md, not logged
        print("that funky monkey")
        return
    w = World()
    text = render(w, argv)
    qid = query_id(argv, text)
    if argv and argv[0] != "verify" and not os.environ.get("BRASS_INFO_ONLY") and not os.environ.get("BRASS_GUIDED") and not os.environ.get("BRASS_LEAN"):
        text += f"query       {qid}   cite this id; `brass verify {qid}` re-runs the query and says whether the answer still holds\n"
    sys.stdout.write(text)
    if os.environ.get("BRASS_NO_LOG"):
        return
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(f"{time.time():.0f}\t{' '.join(argv)}\t{len(text)}\t{qid}\n")
    except OSError:
        pass


if __name__ == "__main__":
    main(sys.argv[1:])
