Complete the task using the supplied project at `/private/tmp/keel-16-run/K3/project`. Everything you may read is under that directory; do not read, search, or list anything outside it. Start with `README.md`. Nothing compiles, checks, or runs in this project. Make the change by modifying files under that directory. Budget: at most 150 tool calls and sixty minutes. When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task that caused the most unnecessary work; (3) every assumption you made that the task did not settle.

The project's `KEEL-REFERENCE.md` is reproduced below so you know the language before you start.

Compact edition of the editing reference, r24 with the arrays-and-sets and several-`has` paragraph, 2026-10-01. Same rules as the full reference (`KEEL-REFERENCE-FULL.md` in the project), fewer words. If a rule here and an example disagree, the rule wins.

# Keel: the editing reference, compact

Keel is written by models and reviewed by people. The facts a reviewer needs sit in declarations: what a function may reach, what it requires, what it promises. Plan an edit from declarations; open a body only when they do not say what you need. When you change a type or refinement, find every declaration that uses it; a refinement shared by two functions changes both. Open `system.keel` when an entry point's access parameters change.

**What checks your work in this run.** Nothing compiles, checks, or runs. Your patch is evaluated after you finish.

## Sentences, not words

| Shape | Means | Inside it |
|---|---|---|
| `type T = B where cond` | the values of `B` that pass `cond` | `it` is the value; bare names are its fields |
| `fn f(params) -> T` then `before`, `after`, `example` | an operation and its obligations | `before` names parameters; `after` adds `result` |
| `if x is T then … else …` | a test that picks a branch | inside `then`, `x` counts as a `T` |
| `for x in xs` | a bounded loop | `x` is one element; `break` leaves |
| `any x in xs where cond` / `all x in xs where cond` | is at least one / every element like this? | no effects; `any` of empty is `false`, **`all` of empty is `true`** |
| `r with { field: v }` | a copy of `r` with fields changed | other fields carry over |
| `r with { status enters S }` | a copy of `r` in state `S` | only a declared edge is legal; `S`'s `has` fields must be given |
| `access A` then `allow op(…)` | an outside capability and what it offers | reached only through a parameter of type `A` |

`in` asks membership or walks a collection; `is` asks a type or an `Ok`/`Err` arm. `where` states a condition; `if` chooses. `with` changes fields; `enters` changes state along a declared edge. `after` is proven for every input; `example` is one input, tested.

## Modules

```keel
# ship/shipments.keel
module ship.shipments
import ship.ids as ids

interface
  type Weight   = Int where it in 1 to 50000
  type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus }
  fn grams_over(s: Shipment, ceiling: Weight) -> Int
    after result == s.weight - ceiling
private interface
  fn is_heavy(s: Shipment) -> Bool
body
  fn grams_over(s, ceiling) = s.weight - ceiling
  fn is_heavy(s) = s.weight >= 20000
```

- One module per file: `interface` (public), optional `private interface`, then `body`. Write `interface` and `body` even when empty. A function is declared once with types; its body repeats the names without types. A body with no declaration, or a declaration with no body, is a rejection.
- Every import has an alias and every imported name goes through it: `ids.ShipmentId`, never `ShipmentId`. No two imports share an alias; imports do not cycle. No versions on `module` or `import`.
- `type ShipmentId = Text` names an existing type. `Text` has `length`: `type Note = Text where length in 1 to 200`.
- Types and constructors start uppercase, everything else lowercase. Keywords are never names (not `from`, not `to`). `system`, `requires`, `grants`, `limit` are keywords only in the system file.
- A record literal names every field: `{ id: id, weight: w, fragile: false, status: ShipmentStatus.Packed }`.
- **Authority is a parameter.** A function reaches outside only through an access it was handed. No access parameter, no effect.

## Conditions

```keel
type Ready = Shipment where status in {ShipmentStatus.Packed}
type Route = { origin: ids.Depot, dest: ids.Depot } where origin != dest
type Batch = Array<Shipment> where length in 0 to 200
type HeavyReady = Ready where weight >= 20000
```

- `it` is the value; a bare name is a field; fields nest by dots. A refinement may follow a type anywhere a type is written. A refined value passes where its base is expected; a base value does not pass where the refinement is expected.
- Tests: `x in 1 to 10` (range), `x in {A, B}` (set), `x in s` (a named set), `x is T` (refinement; `x` must have `T`'s fields), `x is Ok` / `x is Err`. A state test is a set test: `s.status in {ShipmentStatus.Packed}`. `x is None` is a rejection: write `x == None`.
- A passed test narrows the name inside `then`; tests joined with `and` all narrow; `or` narrows nothing; `not` narrows nothing. In `else`, only a single test on states or on `Ok`/`Err` knows the complement. A narrowing lasts until the name is rebound.
- **Only `x is T` gives a value a named type.** Testing a field (`p.status in {…}`) lets you read what depends on it but does not make `p` a `Ready`. A `let` may declare a refinement only for a value already known to satisfy it. A literal, a `data` name, or a `with` whose fields the checker sees satisfies a refinement directly when the condition holds.

**Contracts.**

```keel
fn postage(s: Heavy, base: Cents) -> Cents
  before base <= 1000
  after  result == base + 500
  example postage({ id: "s1", weight: 25000, fragile: false, status: ShipmentStatus.Packed }, 400) == 900
```

- `before`: what the caller must establish, by a parameter's type, a `data` fact, its own `before`, a callee's `after`, or a test on the path. `after`: what holds on success; on `Outcome<T>` it speaks of the value inside `Ok`, named `result`. Several `before` lines hold together.
- A condition may use `+`, `-`, `*` by a constant or of bounded values, `/` and `%` by a nonzero constant, comparisons, `in`, `not`, `and`, `or`, parameters, `result`, fields, `data` names, `length`. No calls, no quantifiers, no floats. "When p then q" is `not (p) or q`. At one level of parentheses use `and` or `or`, never both. The left side of `and` holds while the right is checked.
- A caller's clause that depends on a callee with no contract cannot be proven: the remedy is a contract on the callee.
- `example f(args) == value`: one concrete call, run by `check`. Only on a total `fn` with no access parameter; the arguments must satisfy the types and every `before`. Tested, never proven.
- **Tiers.** Proven: every contract on a Keel function. Enforced by the runtime: an access's reserved bounds and authority checks, every reply from outside, an entry point's parameter types and `before` lines at the boundary. Trusted: nothing checks it. Only proven is a guarantee.

## Bodies

A body is lines run top to bottom; the last line is the value. `and`/`or` stop at the first operand that decides them.

```keel
fn total_weight(batch) =
  let total: Int = 0
  for s in batch
    total = total + s.weight
  total
```

- Every `let` names its type. An unread `let`, or a value computed and dropped (unless it is `Done`, as in `store.save(x)?` on its own line), is a rejection. Parameters and loop variables cannot be rebound. A branch that does not rebind a name leaves its old value.
- `if c then a else b` is a value (both branches); `if c then x = x + 1` on its own line is a step and needs no `else`. A branch may be an indented block whose last line is its value.
- **Failure.** A function that can fail is `partial` and returns `Outcome<T>` (`Ok(T) | Err(FailureCode, Text)`); one without the other is a rejection. `Outcome<Done>` and `Ok(Done)` for no value. `Err` always carries a code (`Unauthorized InvalidInput Conflict Unavailable ResourceExhausted Other NotFound`; `Unknown` is the runtime's, never written) and a text. `x?` yields the value inside `Ok` or returns the `Err` to the caller there; legal only in a `partial` fn. To replace a failure, test `x is Err` first, then `?` in the `Ok` branch cannot fail. A last line `call()` returns its `Outcome` as is; `call()?` as the whole last line is a rejection. A body cannot read which code an `Err` holds. An `Err` undoes nothing: effects already made through an access stand, so check what can refuse before you act. A retry loop retries every failure; retry only what is safe to repeat.
- **Maybe.** `Maybe<T>` holds a `T` or `None`; the caller passes the value itself or `None`. Inside `if x != None then …`, `x` is a plain `T`; the `else` of either test knows the other. No `Maybe<Maybe<T>>`. `Maybe` for normal absence; `Err(NotFound, …)` for failure.
- **No early exit, so tests nest.** Name cheap facts with `let`, decide, and put a lookup with `?` after the tests that decide whether it is needed:

```keel
fn dispatch(carrier, store, id, region) =
  let s: shipments.Shipment = store.shipment(id)?
  if s is shipments.Ready then
    let cleared: Bool = if region in {ids.Region.Abroad} then store.customs_cleared(s.id)? else true
    if cleared then
      let t: ids.TrackingId = carrier.book(s, region)?
      store.save(shipments.ship(s, t))
    else Err(FailureCode.Conflict, "customs has not cleared this shipment")
  else Err(FailureCode.Conflict, "shipment is not packed")
```

- Negate with `not`; `not a == b` is `not (a == b)`.
- **Loops are bounded.** `for` walks a range (`for i in 1 to 3`; `i` is known in range) or an array whose type bounds its length. A loop from `[]` appending at most one element per source element keeps the source's bound. `break` leaves. No `while`, `return`, recursion, or `match`. Arrays cannot be indexed; walk them.
- **`any`/`all`** are `Bool`; the predicate is total and effect-free (no `?`, no access call), sees surrounding names, runs to the end of the expression (parenthesize to combine), body only.

**Arrays and sets.** An array cannot be indexed: walk it with `for`, test it with `any`/`all`, measure it with `length`, extend it with `++` (`xs ++ [x]`). There is no `in` on an array value; membership is `any y in xs where y == x`. A `Set<T>` is for bounds and `in` only (`x in {A, B}`, `region in regions`); `{a, b}` is its literal, and it is not iterable. To find the element at a position, count in a loop:

```keel
let at: Int = 0
for l in ls
  at = at + 1
  if at == pos then picked = picked ++ [l]
```

**Several `has` clauses.** A type may carry several clauses, on one machine field or on different ones; a comma list declares several fields for one state set. Two clauses may not declare the same field name.

```keel
type Order = { id: ids.OrderId, status: OrderStatus }
  where status in {OrderStatus.Shipped, OrderStatus.Delivered} has tracking: ids.TrackingId
  where status in {OrderStatus.Delivered} has signed_by: ids.Badge, signed_at: Int
```

## Records and states

```keel
machine ShipmentStatus
  states  Packed, Shipped, Arrived, Returned
  initial Packed
  Packed  enters Shipped
  Shipped enters Arrived | Returned

type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus }
  where status in {ShipmentStatus.Shipped, ShipmentStatus.Arrived} has tracking: ids.TrackingId

fn ship(s: Ready, t: ids.TrackingId) -> Shipment
fn ship(s, t) = s with { status enters ShipmentStatus.Shipped, tracking: t }
```

- `with { … }` copies a record and replaces named fields; a repeated or unknown field, or an empty `with { }`, is a rejection. Changing a field a refinement tests gives back the base type.
- A state change is `status enters S` inside `with`; a plain `status: S` there is a rejection. A `with` that does not name the state keeps it. `enters` names one state; branch to choose. The checker must know every possible current state has an edge to the target. A literal may hold the initial state, or a state obtained legitimately; inventing a later state in a literal is a rejection.
- A `has` field exists only in the listed states: read it only where the state is known; the update entering those states supplies it; a move between listed states keeps it; the update leaving them drops it, and naming it there is a rejection.

## Accesses and the system file

```keel
access Carrier { regions: Set<ids.Region>, budget_calls: Int }
  allow book(s: shipments.Ready, region: ids.Region) -> Outcome<ids.TrackingId>
    before region in regions and s.weight <= 50000
access Store
  allow shipment(id: ids.ShipmentId) -> Outcome<shipments.Shipment>
  allow save(s: shipments.Shipment) -> Outcome<Done>
```

- An `access` is a declaration in `interface` or `private interface`. A body calls through its parameter: `carrier.book(s, region)`. Every `allow` returns `Outcome<T>`, with no `partial`. A `before` on an `allow` splits by conjunct: one naming a bound is an authority check the runtime enforces; any other is a contract the caller proves. An `after` on an `allow` is checked on every reply. `budget_<unit>` and `deadline_ms` are reserved bounds; a bare `budget` is a rejection. An access is never stored, returned, or put in a record; a function passes on the whole access it holds.
- A state change that depends on a computation belongs in one pure helper with `after` clauses, which an `example` or scenario can test; the entry point calls it once. A requirement on who may cause an effect goes on the operation's parameter type or `before`.

```keel
# system.keel
system shipping
  grants ship.desk.dispatch: carrier = Carrier { regions: {ids.Region.Home, ids.Region.Abroad}, budget_calls: 20 }, store = Store
  grants ship.shipments.grams_over: none
  limit  cpu_ms 5000
  limit  memory_bytes 268435456
  limit  transcript_bytes 2000000000, drop oldest
  limit  impact_modules 12
```

- An entry point is a function with a `grants` line naming each access parameter and its bounds (braces omitted when none); `none` exposes a function holding no access. A grant only narrows. The line changes when an entry point gains, loses, or renames an access parameter. All four `limit` lines are required.
- At the boundary the runtime checks an entry point's arguments against its parameter types and every `before` before the body runs; a failure replies `InvalidInput`. A check that must come after others belongs in the body, with a plain parameter type.

## Exact forms

**Operators, tightest first:** `f(x)` `.` | `?` | `^` (constants) | `-x` | `*` `/` `%` | `+` `-` `++` | `==` `!=` `<` `<=` `>` `>=` `in` `is` (no chaining) | `not` | `and` `or`. `++` joins text or arrays; `+` never joins. `with`/`enters` take the whole call-level expression on their left.

**Types and literals.** `Int8 Int16 Int32 Int64 Int Float Bool Text Bytes Array<T> Set<T> Outcome<T> Done Maybe<T>`; `Int` is `Int64`. Literals `true false 0 1.5 "text" [] [a, b] {a, b}` take their type from where they stand; a literal nowhere typed is a rejection. Constructors are always qualified, in their own module too (`ShipmentStatus.Packed`, `ids.Region.Home`); only a state inside its own `machine` block is bare; `Ok Err Done None` stay bare. Sums are bare names: `type Region = Home | Abroad`. Arithmetic takes two integers or two floats of one type; `%` `^` integer only; arithmetic on ranged integers gives plain `Int`, and a range is proven where a value is stored or passed into a ranged type. Overflow on an unranged integer aborts. Division needs a divisor the checker knows is nonzero.

**Data:** `data max_weight: Int = 50000`; `data zones: ZoneTable from "ship/zones.json"`. **Holes:** `@@name` is rejected until filled. **Projections:** `type Parcel = { … } projects to Label` passes a `Parcel` where a `Label` is expected, by field name; nothing else converts between types.

**Common rejections:** `return`, `while`, `match`, recursion; untyped or unused `let`; a dropped value; mixed `and`/`or` without parentheses; an imported name without its alias; an unqualified constructor; a version on `module`/`import`/`system`; `Err` without a text; `call()?` as the last line; a `has` field read where its state is unknown; a state written as a plain value in `with`; `any`/`all` in a contract, or `?` or an access call in their predicate; an `example` on a `partial` fn.

**Not in this version:** `Map<K, V>`, function values, unbounded loops, narrowing an access in a body. Say so rather than inventing a form.

## Keywords (43)

Module: `module import as interface private body type where it in is to and or not has with projects fn partial before after example access allow machine states initial enters data from`. Body: `let if then else for break any all`. System file only: `system requires grants limit`. Built in, not keywords: `Ok Err Done None result length`.


PATTERN: A FIELD THAT HOLDS A STATE OF ONE OF SEVERAL MACHINES

Keel has no type for "a state of either of these machines". When one field must record a state from more than one machine, declare a shared vocabulary of state names and one converter per machine into it. Keep the record's other fields as they are.

```keel
# desk/audit.keel — the pattern
type Step = Draft | Submitted | Approved | Rejected | ChangesRequested | Paid | Requested | Settled

fn of_report(s: reports.ReportStatus) -> Step
  example of_report(reports.ReportStatus.Paid) == Step.Paid
fn of_advance(s: advances.AdvanceStatus) -> Step
  example of_advance(advances.AdvanceStatus.Settled) == Step.Settled
```

A field that held one machine's state now holds a `Step`. Callers convert at the call site: `audit.of_report(reports.ReportStatus.Approved)`. Do not widen the field to `Text`, and do not add a host operation; the host's operations and record fields stay as they are.

TASK

# Task C: cash advances

## Requirement

Field staff cannot front the cost of a trip. Before a trip, a staff member may request a cash advance for a period, and settle it against the expense report they file afterwards.

- **Requesting.** An active staff member requests an advance for a period that is not closed, stating the amount (at least 1 cent). The advance belongs to the staff member's department.
- **Approving.** An advance is approved by the same people, in the same order, as an expense report of that amount from that staff member would be, with the same refusals: not by the requester, not in a closed period, not by anyone but the required approver, and at the last step not past the department's budget unless the approver is Finance. An approved advance counts against the department's budget for its period, like an approved report.
- **Paying.** Finance pays an approved advance through the ledger, in full, with the advance's id as the key.
- **Settling.** When Finance pays an expense report, they may settle it against one of the staff member's paid advances: the report's payment is reduced by the advance. If the advance covers the whole report, nothing is paid through the ledger, the report takes the advance's ledger reference, and the difference is recorded on the advance as owed by the staff member. Either way the advance is settled and the report is paid. An advance can be settled once, only against an approved report by the same staff member in the same period; otherwise Conflict.
- **Budget.** An advance counts against its department's budget for its period while Approved or Paid. Once settled it stops counting, since the report it was settled against counts instead.
- **Outstanding.** An advance paid but not settled within two periods of its period is outstanding: `period + 2 < today`.
- Every state change of an advance is audited like a report's: each approval step, the payment, and the settlement. Requesting one is not audited, as opening a draft is not.

## Interface

**Advance:** id, badge, department, period, amount, status, approvals (as a report's), reference (once paid), owed (once settled; 0 when the report covered it). Status: Requested → Approved → Paid → Settled. Advances are not rejected in this change.

An advance is paid like a report: a closed period does not block it.

New entry points:

```
request_advance(badge, period, amount) → advance id
approve_advance(advance_id, approver) → the advance's status after
pay_advance(advance_id, finance_badge) → ledger reference
pay_against(report_id, advance_id, finance_badge) → ledger reference, or "settled" when nothing was paid
outstanding_advances(today) → list of advance ids, in the store's order
```

**Statement:** spend and remaining include counted advances; after the report rows, one row per counted advance, in the store's order, with `total` and `budgeted` its amount.

**Store** gains `advance(id)`, `advances_for(department, period)` (every advance there, at most 1,000), `paid_advances()` (every Paid advance, at most 1,000), `save_advance(advance)`. `next_id()` supplies advance ids. Audit entries for an advance use the advance's id in the report field.

## Acceptance

The same hidden cases run against both implementations. They check results; every advance and report saved (status, approvals, reference, owed); every audit entry; every ledger call; that spend and the statement include approved and paid advances; and that everything the baseline already does is unchanged.
