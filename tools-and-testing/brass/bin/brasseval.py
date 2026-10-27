"""Evaluator for the pure fragment of Brass, used by `brass run` and `brass check --examples`.

Handles what the park sources use: ints, text, bools, records, arrays, machine states, `enters`,
`in` over sets, ranges and types (refinement conditions are evaluated), if/else, let and reassignment,
for over arrays and ranges, break, calls to total fns with bodies, Ok/Err and `!`.
No effects: an access call is a failure, by design.
"""
import re

TOKEN = re.compile(r"\s*(?:(\d+)|\"([^\"]*)\"|([A-Za-z_][A-Za-z0-9_]*)|(\+\+|==|!=|<=|>=|->|[-+*/%<>(){}\[\],:=.!|?]))")
STEP_BUDGET = 1_000_000                         # per example or run; spec 6, C15
KW = {"if", "then", "else", "let", "for", "in", "to", "and", "or", "not", "enters", "break", "true", "false", "is", "any", "all", "where", "with"}


class BrassError(Exception):
    pass


class Break(Exception):
    pass


INT_MAX = 2 ** 63 - 1
INT_MIN = -(2 ** 63)


def check_int(v):
    """Spec 2.1: 64-bit arithmetic that overflows aborts; the evaluator reports it as a fault."""
    if isinstance(v, int) and not isinstance(v, bool) and not INT_MIN <= v <= INT_MAX:
        raise BrassError(f"integer overflow: {v} does not fit Int64")
    return v


def tokenize(s):
    out, pos = [], 0
    quoted = False
    for i, ch in enumerate(s):
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            s = s[:i]; break
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m or m.end() == pos:
            if s[pos:].strip() == "":
                break
            raise BrassError(f"cannot read: {s[pos:pos+20]!r}")
        pos = m.end()
        if m.group(1) is not None:
            if int(m.group(1)) > INT_MAX:
                raise BrassError(f"literal {m.group(1)} does not fit Int64")
            out.append(("num", int(m.group(1))))
        elif m.group(2) is not None:
            out.append(("str", m.group(2)))
        elif m.group(3) is not None:
            w = m.group(3)
            out.append(("kw", w) if w in KW else ("id", w))
        else:
            out.append(("op", m.group(4)))
    return out


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        tk = self.peek()
        if kind and tk[0] != kind or val and tk[1] != val:
            raise BrassError(f"expected {val or kind}, got {tk[1]!r}")
        self.i += 1
        return tk

    def at(self, kind, val=None):
        tk = self.peek()
        return tk[0] == kind and (val is None or tk[1] == val)

    def done(self):
        return self.i >= len(self.t)

    # precedence climbing
    def expr(self):
        return self.p_or()

    def p_or(self):
        saved = getattr(self, "_and_seen", False)        # parentheses start a fresh level (p_atom calls expr)
        self._and_seen = False
        e = self.p_and()
        mixed = self._and_seen
        while self.at("kw", "or"):
            self.take()
            self._and_seen = False
            r = self.p_and()
            mixed = mixed or self._and_seen
            if mixed:
                raise BrassError("`and` and `or` mixed at one level; add parentheses")
            e = ("or", e, r)
        self._and_seen = saved
        return e

    def p_and(self):
        e = self.p_not()
        while self.at("kw", "and"):
            self.take()
            self._and_seen = True
            e = ("and", e, self.p_not())
        return e

    def p_not(self):
        if self.at("kw", "not"):
            self.take()
            return ("not", self.p_not())
        return self.p_cmp()

    CMP_OPS = ("==", "!=", "<", ">", "<=", ">=")

    def p_cmp(self):
        e = self.p_add()
        seen = False
        while True:
            if (self.at("op") and self.peek()[1] in self.CMP_OPS) or self.at("kw", "in") or self.at("kw", "is"):
                if seen:
                    raise BrassError("a chained comparison; write `a < b and b < c`")
                seen = True
            if self.at("op") and self.peek()[1] in self.CMP_OPS:
                op = self.take()[1]
                e = (op, e, self.p_add())
            elif self.at("kw", "in"):
                self.take()
                if self.at("op", "{"):
                    self.take()
                    items = []
                    while not self.at("op", "}"):
                        items.append(self.expr())
                        if self.at("op", ","):
                            self.take()
                    self.take("op", "}")
                    e = ("in_set", e, items)
                else:
                    r = self.p_add()
                    if self.at("kw", "to"):
                        self.take()
                        e = ("in_range", e, r, self.p_add())
                    else:
                        e = ("in_type", e, r)
            elif self.at("kw", "is"):
                self.take()
                e = ("in_type", e, self.p_add())
            elif self.at("kw", "enters"):
                self.take()
                e = ("enters", e, self.p_add())
            else:
                return e

    def p_add(self):
        e = self.p_mul()
        while self.at("op") and self.peek()[1] in ("+", "-", "++"):
            op = self.take()[1]
            e = (op, e, self.p_mul())
        return e

    def p_mul(self):
        e = self.p_unary()
        while self.at("op") and self.peek()[1] in ("*", "/", "%"):
            op = self.take()[1]
            e = (op, e, self.p_unary())
        return e

    def p_unary(self):
        if self.at("op", "-"):
            self.take()
            return ("neg", self.p_unary())
        return self.p_post()

    def p_post(self):
        e = self.p_atom()
        while True:
            if self.at("op", "."):
                self.take()
                e = ("field", e, self.take("id")[1])
            elif self.at("op", "("):
                self.take()
                args = []
                while not self.at("op", ")"):
                    args.append(self.expr())
                    if self.at("op", ","):
                        self.take()
                self.take("op", ")")
                e = ("call", e, args)
            elif self.at("op", "?") or self.at("op", "!"):     # `?` since C11; `!` read for older trees
                self.take()
                e = ("bang", e)
            elif self.at("kw", "with"):
                self.take(); self.take("op", "{")
                updates = []
                while not self.at("op", "}"):
                    name = self.take("id")[1]
                    if self.at("kw", "enters"):
                        self.take()
                        updates.append((name, ("enters_to", self.p_post())))
                    else:
                        self.take("op", ":")
                        updates.append((name, self.expr()))
                    if self.at("op", ","):
                        self.take()
                self.take("op", "}")
                e = ("with", e, updates)
            else:
                return e

    def p_atom(self):
        k, v = self.peek()
        if k == "num":
            self.take()
            return ("num", v)
        if k == "str":
            self.take()
            return ("str", v)
        if k == "kw" and v in ("true", "false"):
            self.take()
            return ("bool", v == "true")
        if k == "kw" and v in ("any", "all"):
            self.take()
            name = self.take("id")[1]
            self.take("kw", "in")
            src = self.p_add()
            if self.at("kw", "to"):
                self.take()
                src = ("range", src, self.p_add())
            self.take("kw", "where")
            return (v, name, src, self.expr())
        if k == "kw" and v == "if":
            self.take()
            c = self.expr()
            self.take("kw", "then")
            a = self.expr()
            self.take("kw", "else")
            return ("if", c, a, self.expr())
        if k == "id":
            self.take()
            return ("name", v)
        if k == "op" and v == "(":
            self.take()
            e = self.expr()
            self.take("op", ")")
            return e
        if k == "op" and v == "{":
            self.take()
            if not (self.at("id") and self.peek(1) == ("op", ":")):
                items = []
                while not self.at("op", "}"):
                    items.append(self.expr())
                    if self.at("op", ","):
                        self.take()
                self.take("op", "}")
                return ("set", items)
            fields = []
            while not self.at("op", "}"):
                name = self.take("id")[1]
                self.take("op", ":")
                fields.append((name, self.expr()))
                if self.at("op", ","):
                    self.take()
            self.take("op", "}")
            return ("record", fields)
        if k == "op" and v == "[":
            self.take()
            items = []
            while not self.at("op", "]"):
                items.append(self.expr())
                if self.at("op", ","):
                    self.take()
            self.take("op", "]")
            return ("array", items)
        raise BrassError(f"unexpected {v!r}")


def parse_expr(s):
    p = Parser(tokenize(s))
    e = p.expr()
    if not p.done():
        raise BrassError(f"trailing text after expression: {p.peek()[1]!r}")
    return e


class State:
    __slots__ = ("machine", "name")

    def __init__(self, machine, name):
        self.machine, self.name = machine, name

    def __eq__(self, o):
        return isinstance(o, State) and o.machine == self.machine and o.name == self.name

    def __hash__(self):
        return hash((self.machine, self.name))

    def __repr__(self):
        return f"{self.machine[1]}.{self.name}"


class Outcome:
    __slots__ = ("ok", "value")

    def __init__(self, ok, value):
        self.ok, self.value = ok, value

    def __eq__(self, o):
        return isinstance(o, Outcome) and o.ok == self.ok and o.value == self.value

    def __repr__(self):
        return f"{'Ok' if self.ok else 'Err'}({show(self.value)})"


class Code:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __eq__(self, o):
        return isinstance(o, Code) and o.name == self.name

    def __repr__(self):
        return f"FailureCode.{self.name}"


def show_outcome(o):
    if not isinstance(o, Outcome):
        return show(o)
    return f"Ok({show(o.value)})" if o.ok else f"Err({o.value})"


def show(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k}: {show(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(show(x) for x in v) + "]"
    return repr(v)


class Evaluator:
    """Evaluates in the context of a World (from brass) and a module."""

    def __init__(self, w, strip_comment):
        self.w = w
        self.strip = strip_comment
        self.steps = 0
        self.host_module = None                 # set while a scenario runs: replies are read in the entry's module

    def conditional_fields(self):
        """(controlling field, machine names, state names, field) for every `when` field in the tree (C34)."""
        if not hasattr(self, "_cond"):
            self._cond = []
            for d in self.w.decls.values():
                for f, (ctrl, sts, _) in getattr(d, "conditional", {}).items():
                    if ctrl and sts:
                        self._cond.append((ctrl, {s.split(".")[-2] for s in sts if "." in s}, {s.split(".")[-1] for s in sts}, f,
                                           frozenset(d.fields), frozenset(d.conditional)))
        return self._cond

    # ---- resolution ----------------------------------------------------------
    def machine_edges(self, key):
        d = self.w.decls[key]
        edges, states = {}, []
        for _, l in d.lines:
            s = self.strip(l).strip()
            mm = re.match(r"states\s+(.*)", s)
            if mm:
                states = [x.strip() for x in mm.group(1).split(",")]
            mm = re.match(r"(\w+)\s+enters\s+(.*)", s)
            if mm:
                edges[mm.group(1)] = [x.strip() for x in mm.group(2).split("|")]
        return states, edges

    def lookup_qualified(self, m, parts, env):
        """A dotted name that is not a local: alias.decl, alias.Machine.State, decl, Machine.State, FailureCode.X."""
        head = parts[0]
        if head == "FailureCode" and len(parts) == 2:
            return Code(parts[1]), []
        if head == "Done":
            return "Done", parts[1:]
        if head == "None" and len(parts) == 1:
            return None, []
        mod = m
        rest = parts
        if head in m.aliases and len(parts) > 1:
            mod = self.w.mods[m.aliases[head]]
            rest = parts[1:]
        elif head == m.name.split(".")[-1] and len(parts) > 1 and head not in m.decls:
            rest = parts[1:]
        d = mod.decls.get(rest[0])
        if d is None:
            raise BrassError(f"unknown name {'.'.join(parts)}")
        if d.kind == "machine":
            if len(rest) < 2:
                raise BrassError(f"{d.name} is a machine; name a state")
            states, _ = self.machine_edges(d.key)
            if rest[1] not in states:
                raise BrassError(f"{d.name} has no state {rest[1]}")
            return State(d.key, rest[1]), rest[2:]
        if d.kind == "data":
            if getattr(d, "wrote_data", False):
                raise BrassError(f"`data {d.name}` is `const {d.name}` since C32")
            src = " ".join(self.strip(l) for _, l in d.lines)
            expr = src.split("=", 1)[1]
            return self.eval(parse_expr(expr), mod, {}), rest[1:]
        if d.kind == "fn":
            return ("fn", mod, d), rest[1:]
        if d.kind == "type":
            enum = self.enum_states(d)
            if enum is not None and len(rest) >= 2:
                if rest[1] not in enum:
                    raise BrassError(f"{d.name} has no case {rest[1]}")
                return State(d.key, rest[1]), rest[2:]
            return ("type", mod, d), rest[1:]
        raise BrassError(f"{d.kind} {d.name} is not a value")

    def enum_states(self, d):
        """`type T = A | B | C` is an enumeration; its cases are values like machine states."""
        text = " ".join(self.strip(l).strip() for _, l in d.lines)
        rhs = text.split("=", 1)[1].strip() if "=" in text else ""
        if "|" in rhs and "{" not in rhs and " where " not in rhs and "(" not in rhs:
            return [x.strip() for x in rhs.split("|")]
        return None

    # ---- expressions ---------------------------------------------------------
    def eval(self, e, m, env):
        self.steps += 1
        if self.steps > STEP_BUDGET:
            raise BrassError(f"step budget exceeded: {STEP_BUDGET} evaluation steps")
        k = e[0]
        if k in ("num", "str", "bool"):
            return e[1]
        if k == "name":
            if e[1] in env:
                return env[e[1]]
            v, rest = self.lookup_qualified(m, [e[1]], env)
            return v
        if k == "field":
            # try a qualified name first (alias.Machine.State, alias.data)
            chain = self.dotted(e)
            if chain and chain[0] not in env:
                try:
                    v, rest = self.lookup_qualified(m, chain, env)
                    for f in rest:
                        v = self.getfield(v, f)
                    return v
                except BrassError:
                    pass
            v = self.eval(e[1], m, env)
            return self.getfield(v, e[2])
        if k == "call":
            fn = e[1]
            chain = self.dotted(fn)
            if chain == ["Ok"]:
                return Outcome(True, self.eval(e[2][0], m, env))
            if chain == ["Err"]:
                return Outcome(False, self.eval(e[2][0], m, env))
            if chain and len(chain) >= 2 and chain[0] in env:
                if isinstance(env[chain[0]], Host) and len(chain) == 2:
                    args = [self.eval(a, m, env) for a in e[2]]
                    return env[chain[0]].answer(f"{chain[0]}.{chain[1]}", args, self, self.host_module or m)
                raise BrassError(f"{'.'.join(chain)}: a call on a value; accesses have effects and cannot run here")
            if chain and len(chain) == 2 and m.aliases.get(chain[0]) == "std.text" and chain[1] == "of":
                v = self.eval(e[2][0], m, env)                       # spec 8.1, C4: an integer's decimal text
                if not isinstance(v, int) or isinstance(v, bool):
                    raise BrassError("text.of takes an Int")
                return str(v)
            target, rest = self.lookup_qualified(m, chain, env)
            if not (isinstance(target, tuple) and target[0] == "fn"):
                raise BrassError(f"{'.'.join(chain)} is not a function")
            args = [self.eval(a, m, env) for a in e[2]]
            return self.call(target[1], target[2], args)
        if k == "bang":
            v = self.eval(e[1], m, env)
            if isinstance(v, Outcome):
                if v.ok:
                    return v.value
                raise EarlyErr(v)
            raise BrassError("? on a value that is not an Outcome")
        if k == "record":
            return {name: self.eval(x, m, env) for name, x in e[1]}
        if k == "with":
            base = self.eval(e[1], m, env)
            if not isinstance(base, dict):
                raise BrassError("with on a value that is not a record")
            new = dict(base)
            cond = self.conditional_fields()
            cond_names = {f for _, _, _, f, _, _ in cond}
            for name, x in e[2]:
                if name not in base and name not in cond_names:
                    raise BrassError(f"with: no field {name}")
                if x[0] == "enters_to":
                    new[name] = self.eval(("enters", ("name", "__cur__"), x[1]), m, dict(env, __cur__=base[name]))
                else:
                    new[name] = self.eval(x, m, env)
            named = {name for name, _ in e[2]}
            for ctrl, machines, states, f, fields, conds in cond:     # spec 9.4: entering supplies, staying keeps, leaving drops
                if set(base) - conds != fields:                      # only a value shaped like the declaring record
                    continue
                if not isinstance(base.get(ctrl), State) or base[ctrl].machine[1] not in machines:
                    continue
                if not isinstance(new[ctrl], State):
                    raise BrassError(f"with: {ctrl} must hold a state of {base[ctrl].machine[1]}")
                was, now = base[ctrl].name in states, new[ctrl].name in states
                where = f"{ctrl} in {{{', '.join(sorted(states))}}}"
                if now and not was and f not in named:
                    raise BrassError(f"entering {new[ctrl].name} requires {f}: it exists when {where}")
                if was and not now:
                    if f in named:
                        raise BrassError(f"{f} exists only when {where}; this update leaves those states")
                    new.pop(f, None)
                if not was and not now and f in named:
                    raise BrassError(f"{f} exists only when {where}")
            return new
        if k in ("array", "set"):
            return [self.eval(x, m, env) for x in e[1]]
        if k in ("any", "all"):
            src = e[2]
            items = range(self.eval(src[1], m, env), self.eval(src[2], m, env) + 1) if src[0] == "range" else self.eval(src, m, env)
            for x in items:
                if self.truth(self.eval(e[3], m, dict(env, **{e[1]: x}))) == (k == "any"):
                    return k == "any"
            return k == "all"
        if k == "if":
            return self.eval(e[2] if self.truth(self.eval(e[1], m, env)) else e[3], m, env)
        if k == "and":
            return self.truth(self.eval(e[1], m, env)) and self.truth(self.eval(e[2], m, env))
        if k == "or":
            return self.truth(self.eval(e[1], m, env)) or self.truth(self.eval(e[2], m, env))
        if k == "not":
            return not self.truth(self.eval(e[1], m, env))
        if k == "neg":
            return check_int(-self.eval(e[1], m, env))
        if k in ("+", "++", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="):
            a, b = self.eval(e[1], m, env), self.eval(e[2], m, env)
            if k == "++":
                if type(a) is not type(b) or not isinstance(a, (str, list)):
                    raise BrassError("++ joins two texts or two arrays")
                return a + b
            if k == "+":
                if not (isinstance(a, int) and isinstance(b, int)):
                    raise BrassError("+ is arithmetic; ++ joins")
                return check_int(a + b)
            if k == "-":
                return check_int(a - b)
            if k == "*":
                return check_int(a * b)
            if k == "/":
                if b == 0:
                    raise BrassError("division by zero")
                q = abs(a) // abs(b)                    # spec 2.1: truncates toward zero
                return q if (a >= 0) == (b > 0) else -q
            if k == "%":
                if b == 0:
                    raise BrassError("remainder by zero")
                q = abs(a) // abs(b)
                return a - b * (q if (a >= 0) == (b > 0) else -q)   # sign of the dividend
            if k == "==":
                return a == b
            if k == "!=":
                return a != b
            if k == "<":
                return a < b
            if k == ">":
                return a > b
            if k == "<=":
                return a <= b
            return a >= b
        if k == "in_set":
            v = self.eval(e[1], m, env)
            return any(v == self.eval(x, m, env) for x in e[2])
        if k == "in_range":
            v = self.eval(e[1], m, env)
            return self.eval(e[2], m, env) <= v <= self.eval(e[3], m, env)
        if k == "in_type":
            v = self.eval(e[1], m, env)
            chain = self.dotted(e[2])
            if chain in (["Ok"], ["Err"]):
                if not isinstance(v, Outcome):
                    raise BrassError(f"is {chain[0]} on a value that is not an Outcome")
                return v.ok == (chain[0] == "Ok")
            if chain and chain[0] in env:
                coll = self.eval(e[2], m, env)
                return v in coll if isinstance(coll, list) else False
            t, rest = self.lookup_qualified(m, chain, env)
            if isinstance(t, list):
                return v in t
            if not (isinstance(t, tuple) and t[0] == "type"):
                raise BrassError(f"{'.'.join(chain)} is not a type or a set")
            return self.satisfies(v, t[1], t[2])
        if k == "enters":
            v = self.eval(e[1], m, env)
            chain = self.dotted(e[2])
            target, _ = self.lookup_qualified(m, chain, env)
            if not isinstance(v, State) or not isinstance(target, State):
                raise BrassError("enters needs a machine state on both sides")
            _, edges = self.machine_edges(v.machine)
            if target.name not in edges.get(v.name, []):
                raise BrassError(f"enters: {v.machine[1]} has no edge {v.name} -> {target.name}")
            return target
        raise BrassError(f"cannot evaluate {k}")

    def dotted(self, e):
        if e[0] == "name":
            return [e[1]]
        if e[0] == "field":
            inner = self.dotted(e[1])
            return inner + [e[2]] if inner else None
        return None

    def getfield(self, v, f):
        if isinstance(v, dict):
            if f not in v:
                raise BrassError(f"no field {f}")
            return v[f]
        if isinstance(v, (list, str)) and f == "length":
            return len(v)
        raise BrassError(f"field {f} on a value that has no fields")

    def truth(self, v):
        if not isinstance(v, bool):
            raise BrassError("condition is not a Bool")
        return v

    # ---- types ----------------------------------------------------------------
    def satisfies(self, v, m, d):
        """Does v satisfy type d (a refinement chain)?  `it` is the value; its fields and length are `it.field`, `it.length`."""
        text = " ".join(self.strip(l).strip() for _, l in d.lines)
        rhs = text.split("=", 1)[1].strip()
        base, cond = rhs, None
        if "{" not in rhs.split("where")[0] and " where " in rhs:
            base, cond = rhs.split(" where ", 1)
        elif rhs.startswith("{"):
            depth = 0
            for i, ch in enumerate(rhs):
                depth += (ch == "{") - (ch == "}")
                if depth == 0:
                    break
            rest = rhs[i + 1:]
            if " where " in " " + rest:
                base, cond = rhs[:i + 1], rest.split("where", 1)[1]
        base = base.strip()
        if cond is not None and re.search(r"\bhas\b", cond):
            raise BrassError("`where … has` is not Brass since C34; a state-dependent field carries `when` inside the braces")
        if self.enum_states(d) is not None:
            return isinstance(v, State) and v.machine == d.key
        if not base.startswith("{") and base not in ("Int", "Text", "Bool") and not base.startswith("Array") and not base.startswith("Set"):
            bt, _ = self.lookup_qualified(m, base.split("."), {})
            if isinstance(bt, tuple) and bt[0] == "type" and not self.satisfies(v, bt[1], bt[2]):
                return False
        if cond is None:
            return True
        return self.truth(self.eval(parse_expr(cond), m, {"it": v}))      # C33: fields are it.field; the frozen tool scores old trees

    # ---- functions and blocks --------------------------------------------------
    def call(self, m, d, args):
        if d.fails and self.host_module is None:
            raise BrassError(f"{d.short} returns Outcome; it may reach outside and cannot run here (a scenario can run it against a scripted host)")
        if not d.body:
            raise BrassError(f"{d.short} has no body")
        head = self.strip(d.body[0][1])
        sig = head.split("=", 1)[0]                      # the signature never holds "="; the one-line body after it may hold ")"
        names = [x.strip() for x in sig.split("(", 1)[1].rsplit(")", 1)[0].split(",") if x.strip()]
        if len(names) != len(args):
            raise BrassError(f"{d.short} takes {len(names)} arguments, got {len(args)}")
        env = dict(zip(names, args))
        first = head.split("=", 1)[1].strip() if "=" in head else ""
        lines = [(no, l) for no, l in d.body[1:] if self.strip(l).strip()]
        if first:
            lines = [(d.body[0][0], "    " + first)] + lines
        try:
            return self.block(self.tree(lines), m, env)
        except EarlyErr as ee:
            return ee.outcome

    def tree(self, lines):
        """Group physical lines into (text, children) by indentation, joining continuation lines."""
        joined = []
        for no, l in lines:
            s = self.strip(l).rstrip()
            if joined and (depth(joined[-1][1]) > 0):
                joined[-1] = (joined[-1][0], joined[-1][1] + " " + s.strip())
            else:
                joined.append((no, s))
        root = []
        stack = [(-1, root)]
        for no, s in joined:
            ind = len(s) - len(s.lstrip())
            node = [s.strip(), [], no]
            while stack and stack[-1][0] >= ind:
                stack.pop()
            stack[-1][1].append(node)
            stack.append((ind, node[1]))
        return root

    def block(self, nodes, m, env):
        val = None
        i = 0
        while i < len(nodes):
            text, kids, no = nodes[i]
            nxt = nodes[i + 1] if i + 1 < len(nodes) else None
            if text == "break":
                raise Break()
            vm = re.match(r"(?:let\s+(\w+)\s*(?::\s*[^=]+)?|(\w+)\s*)=\s*(if\s.*\bthen)\s*$", text)
            if vm and kids:
                # `x = if c then` / `let x: T = if c then` with block branches: the chain is this node and its `else` siblings
                cut = next((ix for ix, k in enumerate(kids) if k[0].startswith("else")), len(kids))
                chain = [(vm.group(3), kids[:cut])] + [(k[0], k[1]) for k in kids[cut:]]   # `else` indented under the line
                while nxt and nxt[0].startswith("else"):                                     # or level with it
                    chain.append((nxt[0], nxt[1]))
                    i += 1
                    nxt = nodes[i + 1] if i + 1 < len(nodes) else None
                env[vm.group(1) or vm.group(2)] = self.if_chain(chain, m, env)
                val = None
                i += 1
                continue
            if text.startswith("let "):
                mm = re.match(r"let\s+(\w+)\s*(?::\s*[^=]+)?=\s*(.*)", text)
                if mm.group(2).strip():
                    env[mm.group(1)] = self.eval(parse_expr(mm.group(2)), m, env)
                elif kids:
                    env[mm.group(1)] = self.block(kids, m, dict(env))
                else:
                    raise BrassError(f"let {mm.group(1)} has no value")
                val = None
            elif re.match(r"^\w+\s*=[^=]", text):
                name, rhs = text.split("=", 1)
                env[name.strip()] = self.eval(parse_expr(rhs), m, env)
                val = None
            elif text.startswith("for "):
                mm = re.match(r"for\s+(\w+)\s+in\s+(.*)", text)
                rng = re.match(r"(.*)\s+to\s+(.*)", mm.group(2))
                if rng:
                    a, b = self.eval(parse_expr(rng.group(1)), m, env), self.eval(parse_expr(rng.group(2)), m, env)
                    seq = range(a, b + 1)
                else:
                    seq = self.eval(parse_expr(mm.group(2)), m, env)
                    if not isinstance(seq, list):
                        raise BrassError(f"for over a value that is not an array: {mm.group(2)}")
                try:
                    for x in seq:
                        env[mm.group(1)] = x
                        self.block(kids, m, env)
                except Break:
                    pass
                val = None
            elif text.startswith("if ") or text.startswith("else if "):
                # chain: this node, then following else / else if siblings
                chain = [(text, kids)]
                while nxt and nxt[0].startswith("else"):
                    chain.append((nxt[0], nxt[1]))
                    i += 1
                    nxt = nodes[i + 1] if i + 1 < len(nodes) else None
                val = self.if_chain(chain, m, env)
            else:
                val = self.eval(parse_expr(text), m, env)
            i += 1
        return val

    def if_chain(self, chain, m, env):
        first = split_inline_if(chain[0][0]) if not chain[0][1] else None
        if len(chain) > 1 and first and first[2] is not None and not any(kids for _, kids in chain):
            # the first line already has its own `else`, so the next line's `else` continues its last inline `if`
            # (`… else if d == 4 then "4"` / `else if d == 5 …`): one expression across lines, as on one line
            chain = [(" ".join(text for text, _ in chain), [])]
        if len(chain) == 1 and not chain[0][1]:
            parts = split_inline_if(chain[0][0])
            if parts and parts[2] is None:                          # `if c then x = a`: a one-branch step
                return self.inline_or_block(parts[1], [], m, env) if self.truth(self.eval(parse_expr(parts[0]), m, env)) else None
            if parts and any(re.match(r"^\w+\s*=[^=]", x) for x in parts[1:]):   # `if c then x = a else y = b`: a step
                cond, then_, else_ = parts
                return self.inline_or_block(then_ if self.truth(self.eval(parse_expr(cond), m, env)) else else_, [], m, env)
            if parts:
                return self.eval(parse_expr(chain[0][0]), m, env)     # `if c then a else b` on one line: an expression
        for text, kids in chain:
            if text.startswith("else if ") or text.startswith("if "):
                cond_txt = text[len("else if "):] if text.startswith("else if ") else text[3:]
                if " then" not in cond_txt:
                    raise BrassError(f"if without then: {text}")
                cond, rest = cond_txt.rsplit(" then", 1) if cond_txt.endswith(" then") else cond_txt.split(" then ", 1)
                if self.truth(self.eval(parse_expr(cond), m, env)):
                    return self.inline_or_block(rest.strip(), kids, m, env)
            elif text.startswith("else"):
                return self.inline_or_block(text[4:].strip(), kids, m, env)
        return None

    def inline_or_block(self, inline, kids, m, env):
        if inline:
            if re.match(r"^\w+\s*=[^=]", inline):
                name, rhs = inline.split("=", 1)
                env[name.strip()] = self.eval(parse_expr(rhs), m, env)
                return None
            if inline == "break":
                raise Break()
            if inline.startswith("if ") and split_inline_if(inline) and re.search(r"\bthen\s+\w+\s*=[^=]", inline):
                return self.if_chain([(inline, [])], m, env)           # a nested step chain: `… else if d then x = b else x = c`
            return self.eval(parse_expr(inline), m, env)
        return self.block(kids, m, env)


def split_inline_if(text):
    """`if c then a else b` -> (c, a, b), or (c, a, None) for a one-branch step, splitting only at bracket depth 0, so an
    `if … else …` inside parentheses or a record belongs to its own `if`. None when the line is not a one-line `if`."""
    if not text.startswith("if "):
        return None
    body = text[3:]
    d, then_at, else_at = 0, None, None
    for i, ch in enumerate(body):
        d += ch in "([{"; d -= ch in ")]}"
        if d == 0 and then_at is None and body.startswith(" then ", i):
            then_at = i
        elif d == 0 and then_at is not None and else_at is None and body.startswith(" else ", i):
            else_at = i
    if then_at is None:
        return None
    if else_at is None:
        return body[:then_at].strip(), body[then_at + 6:].strip(), None
    return body[:then_at].strip(), body[then_at + 6:else_at].strip(), body[else_at + 6:].strip()


class Host:
    """A scripted stand-in for the host's accesses: replies come from a script, in order, and every call is recorded."""

    def __init__(self, replies):
        self.replies = {op: list(q) for op, q in replies.items()}   # "store.staff" -> [reply literal, ...]
        self.trace = []                                              # (op, args)

    def answer(self, op, args, ev, m):
        self.trace.append((op, args))
        q = self.replies.get(op)
        if not q:
            return Outcome(False, Code("Unavailable"))
        text = q.pop(0)
        return ev.eval(parse_expr(text), m, {})


class EarlyErr(Exception):
    def __init__(self, outcome):
        self.outcome = outcome


def depth(s):
    return s.count("(") - s.count(")") + s.count("{") - s.count("}") + s.count("[") - s.count("]")
