# Using `brass`

`bin/brass` checks a Brass program's structure, runs its examples and answers questions about the code. It reads the project's `src/` folder: the directory above `bin/`, or `$BRASS_PROJECT` when set. The full checker adds proofs of every `before` and `after`; until then every answer says what it covered and what it did not.

Every answer ends with a `query` id. Cite it; `brass verify <id>` re-runs the query and says whether the answer still holds after an edit.

## Check

```
bin/brass check                     level 1, structure. Rejects: an import or qualified name that does not
                                    resolve; a body with no declaration or a declaration with no body; a body
                                    whose parameter names differ from its declaration; a call with the wrong
                                    number of arguments; `?` in a function that does not return `Outcome<…>`;
                                    `partial`, gone since C25; an unfilled `@@hole`; an untyped `let`;
                                    a removed form (`return`, `while`, `match`, `Some(…)`); a `grants` line
                                    naming no function or not exactly its access parameters.
                                    Each rejection names file and line and gives a fix.
                                    When clean, it prints the program summary (below).
bin/brass check --examples          evaluate every `example f(x) == y` line under a total fn
bin/brass check --scenarios         run every scenarios/*.json: an entry point against a scripted host, comparing the
                                    result and the trace of host calls with what the scenario expects
bin/brass check --scenario <file> … the same for the named files
```

**A scenario** is one JSON file. It names the entry point, gives its arguments as Brass literals by parameter name (access parameters are left out and bound to the scripted host), scripts the host's replies per operation in the order the calls come, and states what to expect: the result, and the trace of host calls.

```json
{"entry": "desk.refund",
 "args": {"payment_id": "\"p1\"", "amount": "400", "reason": "\"customer asked\"", "idempotency_key": "\"k-1\"", "badge": "\"b1\""},
 "replies": {"store.staff": ["Ok({ badge: \"b1\", role: ids.Role.Support, on_shift: true })"],
             "store.payment": ["Ok({ id: \"p1\", merchant_id: \"m1\", amount: 1000, refunded_amount: 0, status: records.PaymentStatus.Captured })"],
             "store.merchant": ["Ok({ id: \"m1\", refund_limit: 5000, active: true })"],
             "processor.refund": ["Err(FailureCode.Unavailable, \"down\")", "Err(FailureCode.Unavailable, \"down\")", "Ok(\"ref-1\")"],
             "store.save_payment": ["Ok(Done)"], "store.append_audit": ["Ok(Done)"]},
 "expect": {"result": "Ok({ reference: \"ref-1\", amount: 400 })",
            "trace": ["store.staff", "store.payment", "store.merchant",
                      "processor.refund(\"p1\", 400, \"k-1\")", "processor.refund(\"p1\", 400, \"k-1\")", "processor.refund(\"p1\", 400, \"k-1\")",
                      "store.save_payment", "store.append_audit"]}}
```

- A failure is compared by its code, a success by its value. A trace entry names an operation, or an operation with the exact arguments; the first step that differs is reported. An operation with no reply left answers `Err(FailureCode.Unavailable)`.
- It is a test, not a proof: one input, one script, the bodies as written. Contracts are not checked. It answers the questions a body review asks of an effectful entry point: what is called before what, how often, with which arguments, and what comes back.

**The program summary.** After a clean check, each granted entry point is listed: the refusals, host calls, state changes, and results found in its source, in source order, each with the conditions enclosing it. It is read from the text, not executed, so it is a reading aid for comparing a program with its requirements, not an account of execution.

```
desk.refund  holds processor, store
      boundary  reason: records.Reason   checked before the body runs; a failing argument is refused as InvalidInput
    28  call     store.staff(badge)   failure passes up
    30  refuse   Unauthorized   "requester must be an on-shift support agent or supervisor"   when not (requester.on_shift and …)
        within requester.on_shift and requester.role in {ids.Role.Support, ids.Role.Supervisor}
    32    call     store.payment(payment_id)   failure passes up
    35    refuse   Conflict       "merchant is not active"   when not m.active
          within p.status in {records.PaymentStatus.Captured, records.PaymentStatus.PartlyRefunded}
    47      call     processor.refund(payment_id, amount, key)   failure kept as a value   repeated: for … in 1 to 3
    50      refuse   Unavailable    "processor did not refund after three attempts"   when last is Err
            within not last is Err
              within full
    57          state    enters Refunded
              within not full
    61          state    enters PartlyRefunded
    62        call     store.save_payment(updated)   failure passes up
    65        succeed  Ok({ reference: reference, amount: amount })
```

- `refuse` is an `Err(FailureCode.X, …)` the body returns, with the condition that decides it (`when`). A refusal written in an `else` is placed at the `if` that decides it.
- `within c` opens a group: everything indented under it happens only when `c` holds; `within not c` is the else-branch. An inline `if c then a else b` and the same thing written as a block report alike (tested).
- `stores` is an `Err` bound by a `let` and never reassigned: an error value whose fate depends on later lines. A `let last: Outcome<…> = Err(…)` that is reassigned in a loop is a seeded value and is not listed.
- `call` is a use of a held access. `failure passes up` means the call ends in `?`; `kept as a value` means the result is bound and tested; `its result is the branch's value` means the call is the last thing in its branch, failure included. Then `reply checked by <after>` or `reply taken on trust`: whether the `allow` promises anything about what comes back.
- `repeated` names the enclosing `for` bound. `state` is an `enters`. `via` follows a helper one level and lists what it does. `boundary` is a parameter whose type is a refinement, checked by the runtime before the body runs.
- It is built from the text. Use it to compare a program with its requirements; it proves nothing.

## Reading

```
bin/brass info                                 system map: grants, limits, entry points, modules
bin/brass info --names                         every module with its declaration names, one line each
bin/brass info --holds                         every entry point with the accesses it holds
bin/brass info <module>                        a module's imports, importers, and interface
bin/brass info <module> --names                imports plus declaration names and kinds only
bin/brass info <module>.<name>                 one declaration: text, holds, direct uses grouped by how they use it,
                                               each with its source line; long answers name the `--in` call that prints the rest
bin/brass info <module>.<name> --in <module>   every use line in one module
bin/brass info <module>.<name> --if-changed    adds the transitive impact set, grouped by module
bin/brass info <module>.<name> --established-by   each caller, its call line, and the `if` tests on the path
bin/brass info <module>.<name> --at <line>     facts in scope at a body line: bindings, narrowings, holds, what a
                                               call there needs; inside `any`/`all`, the bound name and its type
bin/brass info <module>.<name> --effects       an entry point's access calls in body order, each with its guards
bin/brass info --forms                         the language forms this project uses, one example each
bin/brass show <module>.<name>                 one declaration's interface lines and body, numbered
bin/brass show <module>                        a whole source file;  <module>:<a>-<b> for lines a to b
bin/brass show system                          system.brass
```

Several names in one call: `bin/brass info records.Payment desk.refund`. A module may be named `tickets` or `park.tickets`.

## Editing

```
bin/brass propagate                 after editing declarations: writes the mechanical consequences into the tree.
                                    A new parameter becomes `@@name` at every call; a new `when` field becomes
                                    `@@name` at every expression entering its state; each hole is printed with its
                                    type and what is in scope. Then prints `changes`. Idempotent. `--dry` prints only.
bin/brass changes                   what changed against the baseline tree ($BRASS_BASELINE, else git HEAD):
                                    each changed declaration, each dependent site with the reason it is listed,
                                    marked edited or unchanged
bin/brass run <module>.<fn> <arg> …  evaluate a total fn on literal arguments (Brass syntax, one shell word each):
                                    the result, its type, and whether each `after` holds on that input
bin/brass review <module>           what a human should read about an edit: holes, authority, contracts, types, bodies
bin/brass verify <query id>         re-run a cited query
```

A `@@name` in source is a typed hole: the program is rejected until it is filled.

## Which command answers which question

| Question | Command |
|---|---|
| Is the program structurally whole, and what does each entry point do? | `check` |
| Does an entry point call the host in the required order, retry as required, and stop when it should? | `check --scenarios`, one scenario per case |
| What must be true before `f` is called, and what does it promise? | `info <m>.f` |
| Who uses this declaration, and how? | `info <m>.f`; `info <m>.f --in <module>` for one module in full |
| What is known at this line; does this call fit? | `info <m>.f --at <line>` |
| What does `f` compute on one input? | `run <m>.f <args>`; `check --examples` for the inputs written under it |
| After my edit, what else must change? | `propagate`, then fill the holes; `changes` after later edits |
| What does entry point `e` do to the world, and under what tests? | `check` (the summary), or `info <m>.e --effects` |

## A field that holds a state of one of several machines

Brass has no type for "a state of either of these machines". When one field must record a state from more than one machine, declare a shared vocabulary of state names and one converter per machine into it. Keep the record's other fields as they are.

```brass
# desk/audit.brass — the pattern
type Step = Draft | Submitted | Approved | Rejected | ChangesRequested | Paid | Requested | Settled

fn of_report(s: reports.ReportStatus) -> Step
  example of_report(reports.ReportStatus.Paid) == Step.Paid
fn of_advance(s: advances.AdvanceStatus) -> Step
  example of_advance(advances.AdvanceStatus.Settled) == Step.Settled
```

A field that held one machine's state now holds a `Step`. Callers convert at the call site: `audit.of_report(reports.ReportStatus.Approved)`. Do not widen the field to `Text`, and do not add a host operation. When `converters.txt` sits at the project root (one `module.fn` per line), `check` confirms each listed converter covers every state of its machine.

## Lean mode

`BRASS_LEAN=8` is the mode the trials used and the mode to use. It makes the tool answer in the shape that costs a model the fewest steps:

- one `check` runs structure, every `example` and every scenario, and ends with `done` or what to fix;
- bare `show` prints an index, one line per module; `show a b c` prints several modules' declarations in one call, and `show --body` prints a file verbatim;
- `brass apply` takes a patch of any number of blocks and files, matches every block first, checks the result in a copy, and writes only when nothing is rejected. `apply --dry` is the dry run;
- a type loosened to a builtin, such as a state field widened to `Text`, gets a ⚠ line.

The lower levels exist so earlier runs can be reproduced; each keeps the one below. Unset, the tool answers in full, with a `query` id on every answer.
