# Brass Checker

A conforming checker must accept the valid cases promised by the language as well as reject programs that break its rules. This document defines those cases, the proof limits and the required diagnostics.

The [specification](../brass-core-spec.md) defines what **proven** means and which programs are legal. This design sets the checker's obligations and identifies the implementation choices that remain open. The full proof checker is not yet implemented.

## 1. The split

The language decides what is true and promised. The checker decides how cheaply and how far it can establish that. Three things the spec keeps: *proven* means the checker discharged the obligation before run; an obligation it cannot discharge is a rejection, never a runtime check; a correct program it cannot prove is reported **not proven**, never **wrong**. Everything about procedure is here (review S1, E27).

## 2. What a proof may use

A proof across a module boundary uses the imported declaration and its contracts only, never the imported body, so each module is proved alone and re-proved only when its own text or an imported interface changes. Inside a module, a helper is proved through its contract when it has one, else through its body. Contracts are optional on every declaration; a caller's clause that needs an absent callee contract is rejected as not proven, naming the callee.

The fragment is the spec's §11.1. Every intermediate a clause evaluates must fit `Int`; the checker may show that from the operands' types or from the body, as it proves any `after`. A product of two variables is admitted when their widths or ranges bound it. Floats are carried, never reasoned about.

## 3. Required cases

A conforming checker produces the specified acceptance or rejection for each of these. The list grows only by review amendment; a checker that rejects everything does not conform.

| Case | Verdict |
|---|---|
| A bounded sum: a `for` over a range or a bounded array, accumulating into a refined integer whose range the bound implies | proven |
| Counting, a running maximum or minimum, set-membership accumulation over a bounded range or array | proven |
| The filter shape: a loop over a bounded array that starts from an empty array and appends at most one element per source element, skipping allowed; the result's `length` is at most the source's | proven; nothing else about appends |
| A branch excluding a zero divisor, `if d == 0 then … else a / d`, or a divisor whose type excludes zero | accepted; an unguarded variable divisor is rejected naming it |
| A helper call proved through the helper's contract | proven |
| An `allow` argument that is a literal, a `const` name, or a value the checker can show, violating a bound of the grant | rejected at check time; any other argument is the runtime's |
| A value the checker knows, a literal, a `const` name, a `with` whose fields it sees, against a refinement | accepted when the condition holds on the value; rejected on that line otherwise |
| A field test on a value, `p.status in {…}`, then `p` passed where a refinement with that very condition is expected | rejected naming the expected type; only `p is T` establishes it (C20 b) |
| A `with` on a refined value changing no field the condition names, then use as the refined type; the same `with` changing a named field, or an `enters` | accepted; the second rejected naming the expected type until the refinement is established again (C23) |
| `x is T` on a value, then use as `T` inside the branch; `and` combining tests; `or` narrowing nothing; the `else` of a single `in` test on a closed set knowing the complement | accepted as the spec states |
| `enters` from a value whose every possible source state has a declared edge to the target | accepted; otherwise rejected naming the states not covered |
| A `when` field read where the state is known; written on entering; absent outside | accepted; otherwise rejected naming the field and the state |
| A contract the checker cannot prove and cannot refute | rejected as not proven; never reported wrong |
| A contract refuted by a counterexample | rejected; the counterexample is printed where the checker has one (form open) |
| A recursive call, an unbounded loop, a chained comparison, mixed `and`/`or` at one level, an unused `let`, an untyped `let`, a discarded value other than `Done` | rejected |

The loop procedure behind the first rows, from review S1: a local rebound each iteration by a value in `lo to hi` over at most N iterations is known at exit to lie in `start + k·lo` to `start + k·hi` for `k in 0 to N`; any other loop-carried value is known by its declared type alone. Whether an explicit invariant clause is ever needed waits for a real loop the inferred shape misses.

### Authority cases

What the checker establishes about authority, and what it does not. The second column is the honest one.

| Case | Verdict |
|---|---|
| An access value built from a literal, a record, bytes or a reply; an access stored, returned or captured | rejected (§8.1); authority exists only as a grant or a parameter |
| An `allow` called with a literal or `const` destination outside a bound of the grant | rejected at check time; a run-time value is refused by the host before any effect (§8.3) |
| Input choosing between two operations the function may perform, or filling an argument an `allow` sends | accepted; input selects among permitted actions and cannot widen them. The check does not establish that the choice matches anyone's intent |
| A body holding two accesses that reads through one and sends through the other | accepted when types fit; nothing in v0.3 establishes which data may reach which recipient |
| The same `allow` called twice where the contracts hold each time | accepted; a successful check does not bound effect count or order (§11.2) |
| A grant widened in `system`, within the access type | accepted and hashed into `lock`; the check is not proof of review (§10.1) |
| A grant outside the access type's refinement | rejected (§8.4) |

## 4. Bounds on proving

The proof bound per obligation is a checker-defined unit of work, a `brass` setting recorded in `lock` beside the checker identity; the spec promises only that the bound exists and that exceeding it is the rejection *not proven in time*, a third answer beside proven and refuted. Interval reasoning against exact search for bounded products, and where the bound bites, is this file's to decide.

## 5. Run-time evaluation

Every proven clause is evaluated again at run time where it applies, always; the fragment names only values present at the boundary and performs no effect, so every clause can be. A failure aborts the task with the clause and the values in the transcript. It can only mean a checker or runtime defect, or a value that entered without the boundary check; the tier stays proven, and the report says the run-time evaluation is a second line of defense, not a source of assurance.

## 6. Diagnostics

An error says what is wrong and what to change. The decided lines are listed in `brass-report-design.md` §6. Two things a checker distinguishes, because the repair differs: a demonstrated violation (a counterexample) and an undischarged obligation (not proven). A hole (`@@name`) is a rejection that lists the hole's expected type, the bindings in scope with their narrowings, and what would have to be established for each candidate.

## 7. Parked

*Proven how far* (review E49): per function, how much of the result space the contract rules out, cheapest by perturbing the body and reporting which perturbations the contract failed to catch. Needs the checker; never in the hot path; a low score is not a defect. Not before the checker exists and the correlation with real risk has been looked at once.

The caught-bad-edit rate (review C19): the fraction of five plausible-but-wrong edits `brass check` refuses, measured on the five §9.5 systems: widen a bound past its grant; add a machine edge not declared; discard an `Outcome`; pass a `CaseRecord` where an `OpenCase` is required; use a host outside `hosts`.
