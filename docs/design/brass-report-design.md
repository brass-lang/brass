# Brass Info Report

Models and reviewers need to see what a function requires, what it can affect and what depends on it. This document defines how `brass` presents those facts: its commands, its answers, its tiers and its error lines.

The [specification](../brass-core-spec.md) defines what those facts mean and wins if the two disagree. The examples below are real output from the prototype in [`tools-and-testing/brass/`](../../tools-and-testing/brass/BRASS.md), run on the [feeding example](../../examples/feeding/README.md). The prototype reads text and proves nothing. Where the full `brass` should print more than the prototype does, the section says so.

## 1. Rules for every answer

- **Facts, never advice.** An answer is a pure function of the question, the source tree, `lock`, the checker build and any setting that can change it (spec §12). Same inputs, same bytes. No clock.
- **An error says what is wrong and what to change.** Every rejection ends with a `fix:` line. The checker never rewrites code.
- **Labels are keywords or plain words.** `before`, `after`, `holds`, `used_by`. No coined terms, nothing that needs the spec to decode (principle 2.10).
- **Each answer says what it covered.** A search names the files it read and how it matched. A summary read from text says it proves nothing.
- **Sized to the next step.** A model pays per call, not per line. One call should answer what it will ask next: several names in one question, a declaration together with its users, a whole check in one run. A clean check says `done` and nothing else.
- **Long answers stop at a boundary.** An answer too long for one read stops at a module boundary and names what it left out.

## 2. Commands

| Command | Answers |
|---|---|
| `brass check` | Is the program whole? Every rule, every `example`, every scenario, in one call. |
| `brass info` | What is true about this system, module or declaration? |
| `brass show` | What does the source say? |
| `brass apply` | Write this patch, if the result passes the check. |
| `brass propagate` | After an interface edit, put a hole wherever a value is now missing. |
| `brass changes` | What changed against the baseline, and what depends on it? |
| `brass run` | What does this total function return on these inputs? |

`info` and `show` are different questions, so they are different verbs. `info` projects facts the checker holds. `show` returns the file's own bytes.

## 3. `brass info`

### The system

A bare `brass info` is the map for a system the reader has not seen. It says what the system may touch, how big it is, and how its modules connect.

```
$ brass info
system      park
size        4 modules  106 lines including system.brass

grants and limits   (src/system.brass)
  system park
    grants park.control.deliver_feeding: registry = Registry { paddocks: {1, 2, 3, 4, 5} }
    limit  cpu_ms 5000
    limit  memory_bytes 268435456                       # 256 MiB
    limit  transcript_bytes 67108864, drop oldest       # 64 MiB
    limit  impact_modules 4

entry points        (`brass info --holds` for what each holds)
  deliver_feeding      park.control

modules
  module            ver   iface  priv  body  imports            used_by
  park.control               11     4     9  ids staff feeding  -
  park.feeding               28     0    10  ids staff          control
  park.ids                    7     0     0  -                  control feeding staff
  park.staff                  3     0     0  ids                control feeding
```

- **`grants and limits`** is the `system` file as written. It is the whole of the system's authority.
- **`modules`** gives sizes and the full import graph. Line counts are non-blank, non-comment lines: public interface, `private`, and body, none counting another.
- **Not yet in the prototype:** a `requires` row naming each dependency release outside the tree (spec §10.1), and a `differs from lock` row listing modules `changed`, `added` or `removed` since `lock` was written, or `none`.

`brass info --holds` lists each entry point with the accesses it holds and its grant. `brass info --names` lists every module's declarations, one line each.

### A module

`brass info <module>` prints the module's size, imports, importers, the tier legend and its interface. The body is not shown. It must be smaller than the module. `--names` prints declaration names and kinds only.

**Not yet in the prototype:** the tier on each declaration's line (§4).

### A declaration

`brass info <module>.<name>` is the default way in. It prints the declaration as written, what it holds, and every direct use with its line.

```
$ brass info park.control.deliver_feeding
declaration fn deliver_feeding   park.control    interface   src/park/control.brass:16
  fn deliver_feeding(registry: Registry, who: staff.Staff, paddock: ids.PaddockId) -> Outcome<feeding.DeliveredFeeding>
    after result.paddock == paddock and result.delivered_by == who.badge
holds       registry: Registry
grants      entry point; system.brass gives: registry = Registry { paddocks: {1, 2, 3, 4, 5} }
direct uses  none in src/park/
searched     src/park/*.brass (4 modules, declarations and bodies), matched by name; 0 qualified names unresolved
body        4 lines   references: control.deliver_as  feeding.Deliverer
```

```
$ brass info park.feeding.deliver
declaration fn deliver   park.feeding    interface   src/park/feeding.brass:27
  fn deliver(f: PendingFeeding, by: Deliverer) -> DeliveredFeeding
    after result.paddock == f.paddock and result.grams == f.grams and result.delivered_by == by.badge
holds       no access; cannot reach outside
direct uses  1 declaration, 1 line
  call                 control.deliver_as (private)
      control.brass:31    let done: feeding.DeliveredFeeding = feeding.deliver(f, by)
        in       fn deliver_as(registry: Registry, by: feeding.Deliverer, paddock: ids.PaddockId) -> Outcome<feeding.DeliveredFeeding>
        on path  no enclosing test
searched     src/park/*.brass (4 modules, declarations and bodies), matched by name; 0 qualified names unresolved
body        2 lines   references: feeding.FeedingStatus
```

| Row | What it says |
|---|---|
| `declaration` | Kind, name, module, section and source line. Then the declaration as written, with any `#` comment directly above it. |
| `holds` | The access parameters. `no access; cannot reach outside` states purity in one line. |
| `grants` | For an entry point, the grant `system` gives it. |
| `direct uses` | Every use, grouped by how it uses the declaration: `call`, `parameter type`, and so on. Each shows its line, the declaration it sits in, and the `if` tests on its path. |
| `searched` | What was read and how names were matched. |
| `body` | Its length and the names it references. The body itself is `show`'s job. |

An access declaration adds a `tier` row: its bounds are enforced by the runtime, with values set in `system.brass`.

**Flags on a declaration**, each a further question about the same thing:

| Flag | Adds |
|---|---|
| `--in <module>` | Every use in one module, in full. |
| `--if-changed` | The impact set (spec §12.2): every declaration and module an interface change would reach, grouped by module. |
| `--established-by` | Each caller, its call line, and the tests on the path that establish the `before`. |
| `--at <line>` | What is known at one body line: bindings, narrowings, accesses held, what a call there needs. |
| `--effects` | An entry point's access calls in body order, each with its guards. |

Several names fit in one call: `brass info records.Payment desk.refund`.

## 4. Tiers

Every promise prints one of three words. A legend explains them once per report; it does not assign them.

| Word | Meaning |
|---|---|
| `proven` | The checker discharged it before the program runs. |
| `enforced` | The runtime checks it on every call. |
| `assumed` | Nothing checks it. |

A declaration's line prints the weakest tier among its promises. Each promise prints its own on its own row. Which tier each kind of promise gets is fixed by the spec:

| Promise | Tier |
|---|---|
| A `before` or `after` on a function | `proven`, or the program is rejected |
| A clause proven from an `allow`'s `after` | `enforced` (spec §6) |
| An authority check: a `before` on an `allow` that names a bound | `enforced`; rejected at check time when a known value breaks it (spec §8.3) |
| An `allow`'s `after` | `enforced` at the boundary; a bad reply aborts the task |
| `budget_<unit>` and `deadline_ms` | `enforced` over the call (spec §8.2) |
| An argument bound no `before` names | `assumed` |
| An entry point's parameter types and `before` clauses | `enforced` by the generated adapter (spec §8.5) |
| Identity, and a machine state the host supplies | `assumed` |
| An `example` | `tested`, which is not a tier and stands in for no `before` or `after` (spec §6.1) |

Arithmetic on an integer with no range is marked on every such operation, since it aborts on overflow (spec §2.1).

**In the prototype,** tiers follow the declared form, because nothing is proven. Its system report says so in its first line.

## 5. `brass show`

`show` returns source, verbatim. A segment copied from it matches the file exactly, so it can go straight into a patch.

```
$ brass show
index       4 modules under src/park/: length, declarations, imports
  control        33 lines   Registry  deliver_feeding   ← ids staff feeding
  feeding        45 lines   FeedingStatus  Feeding  PendingFeeding  DeliveredFeeding  Deliverer  plan  deliver  skip  signer   ← ids staff
  ids            12 lines   PaddockId  BadgeId  Day  Count  Grams  Species
  staff           9 lines   Role  Staff   ← ids
next        brass show --body <every module you will change or copy, in one call>    or  brass show --for <module.Declaration …>  for declarations with everything that uses them
```

| Form | Returns |
|---|---|
| `show` | The index above: one line per module, with its length, declaration names and imports. |
| `show a b c` | The declarations of several modules, with their contracts. |
| `show --body a b` | Whole files. |
| `show --for m.D` | A declaration with its body, then every declaration that uses it, with theirs. |
| `show m:a-b` | Lines `a` to `b` of one file. |
| `show system` | `system.brass`. |

There is no line-number gutter on source. Line ranges are given in the header instead.

## 6. `brass check`

One call runs everything: structure, every `example`, every scenario under `scenarios/`, and the prototype's extra checks. What passed fits on one line. Only rejections and warnings print in full. The last line is `done`, or the next step.

```
$ brass check
check       ✓ structure · effect order · types kept · machine states
done        nothing else to run
```

```
$ brass check
check       1 rejection
  control.brass:31     hole @@deliverer is unfilled
                       fix: replace the hole with a value of its type
next        fix these, then run `brass check` again
```

`✓` marks what passed, `✗` a rejection and `⚠` a warning. A warning does not block.

### Rejection lines

Each rejection gives its place, what is wrong, then a `fix:` line. The wording below is decided; the prototype prints the subset it can detect.

| What is wrong | Line |
|---|---|
| A call's `before` is not established | `caller must establish: <clause>` |
| A divisor may be zero | `divisor not shown nonzero: <name>` |
| A state change is not allowed | `edge not established: <expr> enters <State>`, with the source states not covered |
| A refinement admits no value | `narrowing has no values: <Type> on <param>` |
| Wrong argument type | `argument type: expected <T>, found <U>` |
| `and` and `or` mixed | `mixed and/or requires parentheses: group the intended condition explicitly` |
| A conditional field read off its path | `field not present on this path: <field> needs status in {<State>}` |
| A missing projection | `<Type> does not project to <Target>: declare it on <Type>, or supply a <Target>` |
| An `after` not established | `after not established: <clause>`, with a counterexample when the checker has one |

**A counterexample and "not proven" are different answers**, because the repair differs. A counterexample shows the body is wrong. "Not proven" means the checker could not decide, and the fix may be a contract on a callee (spec §6, §11).

**A hole** is a rejection with an address. The full `brass` prints `hole <file>:<line> @@<name> : <Type>`, the bindings in scope with their narrowings, and what would have to be established for each candidate (spec §3.2). The prototype prints the hole's name and place only.

**A failed `is` test at the boundary** names the refinement and the failed clause, not the field values.

**Against a baseline,** an interface change is `compatible`, `incompatible` or `not established` (spec §4).

### The program summary

After a clean check, each entry point is listed with its refusals, host calls, state changes and results, in source order, each under the conditions that enclose it. It is read from the text, not run, and says so. [The prototype's guide](../../tools-and-testing/brass/BRASS.md) lists its rows.

### Scenarios

A scenario runs one entry point against a scripted host: arguments, the host's replies in call order, and the expected result and trace of host calls. The check reports the first step that differs. It answers what a body review asks of an effectful function: what is called before what, how often, and with what. It is a test, not a proof.

## 7. Editing

- **`brass apply`** takes a patch of any number of blocks and files. It matches every block, checks the result in a copy, and writes only when nothing is rejected. A rejected patch is held, and the next `apply` amends it. `apply --dry` writes nothing.
- **`brass propagate`** follows an interface edit and writes only what the rules fix. A removed parameter drops its argument at every call. A new parameter, record field or `when` field becomes a hole wherever a value is now missing. It never chooses a value. Everything else the edit reaches is reported, not written. A tree it touches cannot pass `check` until every hole is filled.
- **`brass changes`** lists each changed declaration against the baseline, and each dependent site with the reason it is listed, marked edited or unchanged.

## 8. Citations and hashes

- **A query id is a checkable citation** (spec §12.3). `brass` recomputes the answer from the tree and compares. `check` refuses a repair whose cited answers no longer match. Nothing is stored, so an answer whose tree is gone cannot be rebuilt.
- **Where it prints.** The full form puts `q:<id>` on the first line and `end q:<id>` on the last. The `end` line detects a cut-off answer and nothing more. The lean form the trials used leaves both off, because no trial session ever cited one. A query id belongs in the account a session hands its reviewer.
- **Hashes.** Twelve characters for display. The full hash for identity and in `lock`. A prefix matching two records is rejected with a request for a longer one. `--provenance` prints the full hashes of the interfaces read, the module, `lock` and the checker build.

## 9. Not in a report

Advice and judgment. Timestamps. The environment, which `lock` pins. Recent events, which are in the transcript (spec §10.3). Cyclomatic complexity: with one branch form and one loop form, it tracks body length, already shown. Anything the checker did not compute.

## 10. Open

- **The flag set.** Which flags exist, which add facts and which change the question (principle 2.11).
- **The impact set's count.** Its baseline, body-only edits, and what "needing re-check" means (spec §12.2).
- **Protection moved.** One line when an edit loosens an obligation, such as a field widened to `Text`. The prototype's `⚠` for a type loosened to a builtin is a first form.
- **Transitions performed.** A row for the state a function moves a value into, beside the state it requires.
- **A `when` field** on a type's own report.
- **Who asserted an enforced value**, as a detail on the row.
- **Whether reports beat reading source.** The trials measured how much a model read, not whether its edits were more correct.
