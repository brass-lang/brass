Session sonnet5-20261019-d/D/KC4. Complete the task using the supplied project at `/private/tmp/rerun-sonnet5-20261019-d/D/KC4/project`. Everything you may read is under that directory; do not read, search, or list anything outside it. Read the code you need with `bin/brass show` and `show --body` (several modules per call), then write every edit in one `bin/brass apply`, which runs the check. Fix anything it marks with another `apply`. Make the change by modifying files under that directory. Budget: at most 150 tool calls and sixty minutes. When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task that caused the most unnecessary work; (3) every assumption you made that the task did not settle.

The project's `BRASS-REFERENCE.md` is reproduced below so you know the language before you start.

Compact edition of the editing reference, r33, 2026-10-18: r31 with `std.text`'s `of` beside `++` (r32) and the facts that prove a range (C47, r33). r31, 2026-10-17: r30 with C46's section on a field for states of several machines. r30, 2026-10-16: the r24 compact edition with every rule that changed by r30 restated in r30's words. Same rules as the full reference (`BRASS-REFERENCE-FULL.md` in the project), fewer words. If a rule here and an example disagree, the rule wins.

# Brass: the editing reference, compact

Brass is written by models and reviewed by people. The facts a reviewer needs sit in declarations: what a function may reach, what it requires, what it promises. Plan an edit from declarations; open a body only when they do not say what you need. When you change a type or refinement, find every declaration that uses it; a refinement shared by two functions changes both. Open `system.brass` when an entry point's access parameters change.

**What checks your work in this run.** `bin/brass`: `show` prints every module's declarations in one call, `show --body a b c` several whole files in one call, `apply` writes every edit across every file in one call (all or nothing) and then runs `check`, the completion gate: structure, every `example`, every scenario, the host contract, the order of writes against refusals, and what each entry point you touched now does. A clean `check` ends with `done`. It proves no contract. Your patch is evaluated after you finish.

## Sentences, not words

| Shape | Means | Inside it |
|---|---|---|
| `type T = B where <condition>` | the values of `B` that pass the condition | `it` is the value; its fields are `it.field` |
| `fn f(params) -> T` then `before`, `after`, `example` | an operation and its obligations | `before` names parameters; `after` adds `result` |
| `if x is T then … else …` | a test that picks a branch | inside `then`, `x` counts as a `T` |
| `for x in xs` | a bounded loop | `x` is one element; `break` leaves |
| `any x in xs where cond` / `all x in xs where cond` | is at least one / every element like this? | no effects; `any` of empty is `false`, **`all` of empty is `true`** |
| `r with { field: v }` | a copy of `r` with fields changed | other fields carry over |
| `r with { status enters S }` | a copy of `r` in state `S` | only a declared edge is legal; the `when` fields of `S` must be given |
| `access A` then `allow op(…)` | an outside capability and what it offers | reached only through a parameter of type `A` |

`in` asks membership or walks a collection; `is` asks a type or an `Ok`/`Err` arm. `where` states a condition; `if` chooses. `with` changes fields; `enters` changes state along a declared edge. `after` is proven for every input; `example` is one input, tested.

## Modules

```brass
# ship/shipments.brass
module ship.shipments
import ship.ids as ids

interface
  type Weight   = Int where it in 1 to 50000
  type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus }
  fn grams_over(s: Shipment, ceiling: Weight) -> Int
    after result == s.weight - ceiling
private
  fn is_heavy(s: Shipment) -> Bool
body
  fn grams_over(s, ceiling) = s.weight - ceiling
  fn is_heavy(s) = s.weight >= 20000
```

- One module per file: `interface` (public), optional `private`, then `body`. Write `interface` and `body` even when empty. A function is declared once with types; its body repeats the names without types. A body with no declaration, or a declaration with no body, is a rejection.
- Every import has an alias and every imported name goes through it: `ids.ShipmentId`, never `ShipmentId`. No two imports share an alias; imports do not cycle. No versions on `module` or `import`.
- `type ShipmentId = Text` names an existing type. `Text` has `length`: `type Note = Text where it.length in 1 to 200`.
- Types and constructors start uppercase, everything else lowercase. Keywords are never names (not `to`, not `in`). `system`, `requires`, `grants`, `limit` are keywords only in the system file.
- A declaration continues onto the next line while a `(`, `<`, or `{` it opened is still open, as in Python; indentation inside does not matter.
- A record literal names every field: `{ id: id, weight: w, fragile: false, status: ShipmentStatus.Packed }`.
- **Authority is a parameter.** A function reaches outside only through an access it was handed. No access parameter, no effect.

## Conditions

```brass
type Ready = Shipment where it.status in {ShipmentStatus.Packed}
type Route = { origin: ids.Depot, dest: ids.Depot } where it.origin != it.dest
type Batch = Array<Shipment> where it.length in 0 to 200
type HeavyReady = Ready where it.weight >= 20000
```

- `it` is the value, and its fields are `it.field`, nesting by dots. A bare field name is a rejection: write `it.status`, not `status`. A refinement may follow a type anywhere a type is written. A refined value passes where its base is expected; a base value does not pass where the refinement is expected.
- Tests: `x in 1 to 10` (range), `x in {A, B}` (set), `x in s` (a named set), `x is T` (refinement; `x` must have `T`'s fields), `x is Ok` / `x is Err`. A state test is a set test: `s.status in {ShipmentStatus.Packed}`. `x is None` is a rejection: write `x == None`.
- A passed test narrows the name inside `then`; tests joined with `and` all narrow; `or` narrows nothing; `not` narrows nothing. In `else`, only a single test on states or on `Ok`/`Err` knows the complement. A narrowing lasts until the name is rebound.
- **Only `x is T` gives a value a named type.** Testing a field (`p.status in {…}`) lets you read what depends on it but does not make `p` a `Ready`. A `let`, argument, field, or result also holds a refinement when the checker can prove its condition there from the facts that establish a `before` (see Types and literals). A literal, a `const` name, or a `with` whose fields the checker sees satisfies a refinement directly when the condition holds.

**Contracts.**

```brass
fn postage(s: Heavy, base: Cents) -> Cents
  before base <= 1000
  after  result == base + 500
  example postage({ id: "s1", weight: 25000, fragile: false, status: ShipmentStatus.Packed }, 400) == 900
```

- `before`: what the caller must establish, by a parameter's type, a `const` fact, its own `before`, a callee's `after`, or a test on the path. `after`: what holds on success; on `Outcome<T>` it speaks of the value inside `Ok`, named `result`. Several `before` lines hold together.
- A condition may use `+`, `-`, `*` by a constant or of bounded values, `/` and `%` by a nonzero constant, comparisons, `in`, `not`, `and`, `or`, parameters, `result`, fields, `const` names, `length`. No calls, no quantifiers, no floats. "When p then q" is `not (p) or q`. At one level of parentheses use `and` or `or`, never both. The left side of `and` holds while the right is checked.
- A caller's clause that depends on a callee with no contract cannot be proven: the remedy is a contract on the callee.
- `example f(args) == value`: one concrete call, run by `check`. Only on a total `fn` with no access parameter; the arguments must satisfy the types and every `before`. Tested, never proven.
- **Tiers.** Proven: every contract on a Brass function, unless it is proved from an enforced fact. Enforced by the runtime: an access's reserved bounds and authority checks, every reply from outside, an entry point's parameter types and `before` lines at the boundary. Assumed: nothing checks it. Only proven is a guarantee.

## Bodies

A body is lines run top to bottom; the last line is the value. `and`/`or` stop at the first operand that decides them.

```brass
fn total_weight(batch) =
  let total: Int = 0
  for s in batch
    total = total + s.weight
  total
```

- Every `let` names its type. An unread `let`, or a value computed and dropped (unless it is `Done`, as in `store.save(x)?` on its own line), is a rejection. Parameters and loop variables cannot be rebound. A branch that does not rebind a name leaves its old value. Rebinding gives the name a new value; the old value is unchanged, as every value is.
- `if c then a else b` is a value (both branches); `if c then x = x + 1` on its own line is a step and needs no `else`. A branch may be an indented block whose last line is its value.
- **Failure.** A function that can fail returns `Outcome<T>` (`Ok(T) | Err(FailureCode, Text)`); nothing else marks it. `Outcome<Done>` and `Ok(Done)` for no value. `Err` always carries a code (`Unauthorized InvalidInput Conflict Unavailable ResourceExhausted Other NotFound`; `Unknown` is the runtime's, never written) and a text. `x?` yields the value inside `Ok` or returns the `Err` to the caller there; legal only in a function that returns `Outcome`. To replace a failure, test `x is Err` first, then `?` in the `Ok` branch cannot fail. A last line `call()` returns its `Outcome` as is; `call()?` as the whole last line is a rejection. A body cannot read which code an `Err` holds. An `Err` undoes nothing: effects already made through an access stand, so check what can refuse before you act. A retry loop retries every failure; retry only what is safe to repeat.
- **Maybe.** `Maybe<T>` holds a `T` or `None`; the caller passes the value itself or `None`. Inside `if x != None then …`, `x` is a plain `T`; the `else` of either test knows the other. No `Maybe<Maybe<T>>`. `Maybe` for normal absence; `Err(NotFound, …)` for failure.
- **No early exit, so tests nest.** Name cheap facts with `let`, decide, and put a lookup with `?` after the tests that decide whether it is needed:

```brass
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
- **Loops are bounded.** `for` walks a range (`for i in 1 to 3`; `i` is known in range) or an array whose type bounds its length. A loop from `[]` appending at most one element per source element keeps the source's bound. `break` leaves the nearest enclosing loop, and the body continues after it. `lo to hi` includes both ends: `1 to 3` runs three times. No `while`, `return`, recursion, or `match`. Arrays cannot be indexed; walk them.
- **`any`/`all`** are `Bool`; the predicate is total and effect-free (no `?`, no access call), sees surrounding names, runs to the end of the expression (parenthesize to combine), body only.

**Arrays and sets.** An array cannot be indexed: walk it with `for`, test it with `any`/`all`, measure it with `length`, extend it with `++` (`xs ++ [x]`). There is no `in` on an array value; membership is `any y in xs where y == x`. A `Set<T>` is for bounds and `in` only (`x in {A, B}`, `region in regions`); `{a, b}` is its literal, and it is not iterable. To find the element at a position, count in a loop:

```brass
let at: Int = 0
for l in ls
  at = at + 1
  if at == pos then picked = picked ++ [l]
```

**Several `when` fields.** A record may carry several conditional fields, testing one machine field or different ones. Each conditional field carries its own `when`.

```brass
type Order = { id: ids.OrderId, status: OrderStatus,
               tracking:  ids.TrackingId when it.status in {OrderStatus.Shipped, OrderStatus.Delivered},
               signed_by: ids.Badge      when it.status in {OrderStatus.Delivered},
               signed_at: Int            when it.status in {OrderStatus.Delivered} }
```

## Records and states

```brass
machine ShipmentStatus
  states  Packed, Shipped, Arrived, Returned
  initial Packed
  Packed  enters Shipped
  Shipped enters Arrived | Returned

type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus,
                  tracking: ids.TrackingId when it.status in {ShipmentStatus.Shipped, ShipmentStatus.Arrived} }

fn ship(s: Ready, t: ids.TrackingId) -> Shipment
fn ship(s, t) = s with { status enters ShipmentStatus.Shipped, tracking: t }
```

- `with { … }` copies a record and replaces named fields; a repeated or unknown field, or an empty `with { }`, is a rejection. A `with` that changes none of the fields a refinement tests keeps that refinement: a note added to a `Ready` shipment is still `Ready`. Changing a field that a refinement tests, `enters` included, gives back the base type.
- A state change is `status enters S` inside `with`; a plain `status: S` there is a rejection. A `with` that does not name the state keeps it. `enters` names one state; branch to choose. The checker must know every possible current state has an edge to the target. A literal may hold the initial state, or a state obtained legitimately; inventing a later state in a literal is a rejection.
- A `when` field exists only in the listed states; the field it tests is itself unconditional, and its type is a named type: read it only where the state is known; the update entering those states supplies it; a move between listed states keeps it; the update leaving them drops it, and naming it there is a rejection.

**A field for states of several machines takes a shared vocabulary.**

A field has one machine type, and no type means "a state of one of these machines". When one record must hold states from several machines, declare a shared vocabulary of state names and one converter per machine, and convert where you build the record:

```brass
# ship/log.brass
type Subject = Shipment | Pickup
type Step    = Packed | Shipped | Arrived | Returned | Booked | Collected | Missed
type Entry   = { subject: Subject, subject_id: Text, was: Step, now: Step }

fn of_shipment(s: shipments.ShipmentStatus) -> Step
  example of_shipment(shipments.ShipmentStatus.Arrived) == Step.Arrived
fn of_pickup(p: pickups.PickupStatus) -> Step
  example of_pickup(pickups.PickupStatus.Missed) == Step.Missed
```

- A field that held one machine's state now holds the vocabulary. A `subject` beside a neutral id says which machine a value came from.
- Write a direct `example` for each state; each one is checked.
- Widening the field to `Text`, or adding a second record or host operation for the second machine, is legal and loses what the type said.

## Accesses and the system file

```brass
access Carrier { regions: Set<ids.Region>, budget_calls: Int }
  allow book(s: shipments.Ready, region: ids.Region) -> Outcome<ids.TrackingId>
    before region in regions and s.weight <= 50000
access Store
  allow shipment(id: ids.ShipmentId) -> Outcome<shipments.Shipment>
  allow save(s: shipments.Shipment) -> Outcome<Done>
```

- An `access` is a declaration in `interface` or `private`. A body calls through its parameter: `carrier.book(s, region)`. Every `allow` returns `Outcome<T>`. A `before` on an `allow` splits by conjunct: one naming a bound is an authority check the runtime enforces; any other is a contract the caller proves. An `after` on an `allow` is checked on every successful reply. `budget_<unit>` and `deadline_ms` are reserved bounds; a bare `budget` is a rejection. An access is never stored, returned, or put in a record; a function passes on the whole access it holds.
- A state change that depends on a computation belongs in one pure helper with `after` clauses, which an `example` or scenario can test; the entry point calls it once. A requirement on who may cause an effect goes on the operation's parameter type or `before`.

```brass
# system.brass
system shipping
  grants ship.desk.dispatch: carrier = Carrier { regions: {ids.Region.Home, ids.Region.Abroad}, budget_calls: 20 }, store = Store
  grants ship.shipments.grams_over: none
  limit  cpu_ms 5000
  limit  memory_bytes 268435456
  limit  transcript_bytes 2000000000, drop oldest
  limit  impact_modules 12
```

- An entry point is a function with a `grants` line naming each access parameter and its bounds (braces omitted when none); `none` exposes a function holding no access. A grant only narrows. The line changes when an entry point gains, loses, or renames an access parameter. The three runtime `limit` lines are required; `impact_modules` is an optional review policy: exceeding it gives a review notice, not a check failure, and omitting it sets no cap.
- At the boundary the runtime checks an entry point's arguments against its parameter types and every `before` before the body runs; a failure replies `InvalidInput`. A check that must come after others belongs in the body, with a plain parameter type.

## Exact forms

**Operators, tightest first:** `f(x)` `.` | `?` | `^` (constants) | `-x` | `*` `/` `%` | `+` `-` `++` | `==` `!=` `<` `<=` `>` `>=` `in` `is` (no chaining) | `not` | `and` `or`. `++` joins text or arrays; `+` never joins. To put a number in text, import the bundled module `std.text` (`import std.text as text`) and write `"period " ++ text.of(n)`: `of` takes an `Int`, gives its decimal text, is total and pure, and needs no access. `with`/`enters` take the whole call-level expression on their left.

**Types and literals.** `Int8 Int16 Int32 Int64 Int Float Bool Text Bytes Array<T> Set<T> Outcome<T> Done Maybe<T>`. Integers are signed; `Int` is `Int64`. Never negative is a refinement: `Int where it in 0 to n`. Literals `true false 0 1.5 "text" [] [a, b] {a, b}` take their type from where they stand; a literal nowhere typed is a rejection. Constructors are always qualified, in their own module too (`ShipmentStatus.Packed`, `ids.Region.Home`); only a state inside its own `machine` block is bare; `Ok Err Done None` stay bare. Sums are bare names: `type Region = Home | Abroad`. Arithmetic takes two integers or two floats of one type; `%` `^` integer only; arithmetic on ranged integers gives plain `Int`, and a range is proven where a value is stored or passed into a ranged type, from the facts that establish a `before`: the operands' declared types, `const` facts, the function's `before`, a callee's `after`, and an `is` test or a comparison on the path. That holds for a named refinement whose condition is a range, such as `Cents`: where `c` and `v` are `Cents`, `if c > v then c - v else 0` is a `Cents`. Overflow on an unranged integer aborts. Division needs a divisor the checker knows is nonzero.

**Constants:** `const max_weight: Int = 50000`; a `const` name may stand anywhere a literal of its type may. **Holes:** `@@name` is rejected until filled. **Projections:** `type Parcel = { … } projects to Label` passes a `Parcel` where a `Label` is expected, by field name; nothing else converts between types.

**Common rejections:** `return`, `while`, `match`, recursion; untyped or unused `let`; a dropped value; mixed `and`/`or` without parentheses; an imported name without its alias; an unqualified constructor; a version on `module`/`import`/`system`; `Err` without a text; `call()?` as the last line; a `when` field read where its state is unknown; a bare field name in a `where`; a state written as a plain value in `with`; `any`/`all` in a contract, or `?` or an access call in their predicate; an `example` on a fn that returns `Outcome` or one taking an access.

**Not in this version:** `Map<K, V>`, function values, unbounded loops, narrowing an access in a body. Say so rather than inventing a form.

## Keywords (41)

Module: `module import as interface private body type where it in is to and or not when with projects fn before after example access allow machine states initial enters const`. Body: `let if then else for break any all`. System file only: `system requires grants limit`. Built in, not keywords: `Ok Err Done None result length`.


## `bin/brass`

The starting tree passes `bin/brass check`. Put several names in one call.

```
brass show                               the index: every module, its length, declaration names, and imports
brass show review payment budget         those modules' declarations with their contracts; several per call
brass show --for audit.Entry queries.Row what an edit of these needs: each declaration with its body, then every declaration that uses it, with its body
brass show --body review payment queries the whole files of several modules, in one call, verbatim (copy find text from it as is)
brass info <module>.<name> [...]         what uses each declaration, and how
brass apply <<'PATCH'                    every edit, across every file, in one call; checked before anything is written
@@@ decl src/desk/payment.brass pay       a block: a declaration by name; `@@@ interface` then its interface lines, and/or `@@@ body` then its body, each replaced whole; a name the file does not declare is added
@@@ interface
…
@@@ body
…
@@@ end
@@@ edit src/desk/review.brass            a block: the text to find (once in the file; a wrong indent is forgiven and reported) and its replacement
@@@ find
…
@@@ replace
…
@@@ end
@@@ new src/desk/advances.brass           a block: a whole new file (on a file that exists, it replaces the whole file and says so)
…
@@@ end
PATCH
brass check                              the completion gate on its own; `apply` already runs it
```

`apply` checks before it writes. If every block matches and the check finds nothing new to reject, it writes and the answer ends with how many declarations changed. Otherwise nothing is written, the blocks that matched are held, and the answer names each ✗ block and each rejected line. Then send only what changes: a block with the same file and find text, the same new file, or the same declaration replaces the held one; any other block applies on top of what is held. `brass apply --drop` discards a held patch. An answer longer than about 26k characters stops at a module boundary and names what it left out; ask for those in the next call. `check` covers structure, examples, scenarios, the host contract (`host-contract.txt`), the order of writes against refusals, machine states passed to calls, declared types loosened to a builtin, and what each entry point you touched now does; a clean check ends with `done`, and `⚠` lines are for you to read before you finish.

## `host-contract.txt`: the operations the host implements

Only these exist at run time; `check` rejects any other `allow`.

```
# The operations the host implements for this change. `brass check` rejects any other `allow`.
# The host publishes these; the program does not add to them.
Store.staff
Store.report
Store.department
Store.reports_for
Store.submitted_reports
Store.period_closed
Store.next_id
Store.save_report
Store.append_audit
Store.close_period
Ledger.pay
Store.advance
Store.advances_for
Store.paid_advances
Store.save_advance
Registry.vendor
Registry.po
Registry.pos_for
Registry.txn
Registry.txns_for
Registry.delegation
Registry.delegations_from
Registry.cost_center
Registry.departments_of
Registry.entity
Registry.allowance
Registry.pos_of_vendor
Registry.card_limit
Registry.departments
Registry.exception
Registry.exceptions_for
Registry.save_po
Registry.save_txn
Registry.save_delegation
Registry.save_vendor
Registry.save_card_limit
Registry.save_exception
Store.trip
Store.trips_for
Store.trips_in
Store.save_trip
```


## Project map

Entry points are the `grants` lines of `src/system.brass`. Modules under `src/desk/`, with their declarations:

| Module | What it holds | Declarations |
|---|---|---|
| `advance_desk` | entry points: cash advances | request_advance approve_advance |
| `advances` | the advance record and its state machine | AdvanceStatus Amount Advance Advances Requested Approved PaidAdvance Counted add_approval approve pay settle outstanding |
| `allowances` | entry points: per diem and mileage lines | add_per_diem add_mileage |
| `audit` | audit entries for reports and advances: a subject, a shared state vocabulary, a converter per machine (C22) | Subject Step Entry report_entry advance_entry of_report of_advance |
| `budget` | spend against a department's budget | spend_of department_spend |
| `card_limits` | entry points: card limits | set_card_limit over_limit spent_by |
| `cards` | entry points: corporate card transactions | TxnIds import_txn match_txn dispute_txn unmatched |
| `delegation` | entry points: delegating approval authority | grant_delegation revoke_delegation delegate_in_force |
| `entities` | entry points: cost-center summaries | CostCenterSummary cost_center_summary |
| `exceptions` | entry points: policy exceptions | request_exception decide_exception |
| `forecasting` | entry points: spend forecasts | Forecast forecast |
| `host` | the accesses the host implements | Store Ledger |
| `ids` | value types | Money Period Badge Reason Description ReportId DepartmentId Role Category |
| `lines` | expense lines and category policy | Line Lines Policy policy_for line_valid all_valid total budgeted_total |
| `payment` | entry points: paying, closing periods | pay pay_advance pay_against close_period |
| `purchasing` | entry points: purchase orders | raise_po approve_po reject_po receive_po close_po po_commitments |
| `queries` | entry points: read-only views | Ids Row Rows Statement statement spend outstanding_advances pending_for |
| `readiness` | entry points: period readiness | Readiness period_readiness |
| `records` | records and machines for the added subsystems | VendorId PoId TxnId DelegationId CostCenterId EntityId Region Vehicle Amount PoStatus CardStatus Vendor PurchaseOrder POs PoRequested PoApproved PoReceived CardTxn Txns OpenTxn Delegation Delegations CostCenter Entity DeptIds CardLimit ExceptionId ExceptionStatus PolicyException Exceptions PendingException Badges commitments in_force per_diem_rate mileage_rate add_po_approval approve_po reject_po receive_po close_po decide match_txn dispute_txn |
| `registry` | the access for the added subsystems' data | Registry |
| `reporting` | entry points: period summaries | PeriodSummary period_summary |
| `reports` | the report record and its state machine | ReportStatus Approvals Report Reports Draft Submitted Approved AwaitingChanges Counted Editable add_line submit add_approval approve reject request_changes resubmit pay |
| `review` | entry points: drafting, submitting, approving | open_draft add_line submit approve reject request_changes resubmit may_act may_act_on |
| `routing` | who approves at which step | Step steps_for role_for |
| `staff` | staff and departments | Staff Active Finance Department |
| `vendors` | entry points: vendor management | onboard_vendor deactivate_vendor vendor_spend |
| `query` |  | q:cbfcef2b cite this id; `brass verify q:cbfcef2b` re-runs the query and says whether the answer still holds |


TASK

# Task D: trip commitments

## Requirement

Before a trip, a staff member files a trip plan. Once approved, the plan commits its cost against the department's budget, so the budget shows money that is promised but not yet spent. As the staff member's expense reports are approved, they take the commitment's place in the budget. After the trip, Finance reconciles the plan against what was actually spent, and the trip records it.

- **Filing.** An active staff member files a trip plan for a period that is not closed. The plan names a region and a number of per diem days (0 to 30), and a vehicle and a distance in kilometres (0 to 2,000); at least one of days and kilometres is positive, and a plan with both zero is refused with InvalidInput. Its committed amount is priced from the same per diem and mileage rate tables as report lines; a zero component contributes zero. Region and vehicle are always given, even when their component is zero. The trip belongs to the staff member's department. A staff member has at most one open trip per period: filing is refused with Conflict when they already have a Requested, Approved, or Reconciled trip for it. A Closed trip does not block a new one, because a trip is closed only before it is reconciled and never claims any expense. Every report and card transaction of that staff member for that period belongs to that trip. Filing is not audited, as opening a draft is not.
- **Approving.** A trip is approved by the same people, in the same order, as an expense report of its committed amount from that staff member would be, with the same refusals: not by the requester, not in a closed period, not by anyone but the required approver, and at the last step not past the department's budget unless the approver is Finance. That budget check counts the trip as it will count once approved: its committed amount less the staff member's approved and paid reports for the period, never below zero. The approval covers the plan exactly as it stood when approved.
- **Delegation.** The required approver may instead be someone who holds a delegation from that person in force for the period in which the approval happens, given as `today`: the current period, supplied by the host, not a value the approver chooses. Authority is checked when each approval happens: a delegation that has expired or been revoked by then does not count, and approvals already given stay valid. An approval given under a delegation says so: its audit reason must contain the badge of the person on whose behalf it was given and the period; the wording is free.
- **Amending.** Only the staff member who filed a trip may amend its plan, and only while it is Requested or Approved. Amending reprices the committed amount and clears every approval given so far; an Approved trip returns to Requested in the same save. Refusals in this order: anyone else, Unauthorized; a trip that is Reconciled or Closed, Conflict.
- **Budget.** While a trip is Approved, it counts against its department's budget for its period by the part of its committed amount not yet covered by the staff member's approved and paid reports for that period: the committed amount minus those reports' budgeted totals, never below zero. At any other status it counts nothing. Reports and advances count as they do today. Card transactions count toward no budget, as today.
- **Approving a report beside a trip.** When the last approval step of a report checks the department's budget, a trip of the same staff member and period counts by what it would count once that report is approved, so the report's amount is not charged twice.
- **Reconciling.** Finance reconciles an Approved trip against one expense report by the same staff member for the same period, and the report must be Approved or Paid; otherwise Conflict. The trip's actual amount is the report's total, every line counted, plus the staff member's card transactions for that period that are not matched to any report (open or disputed). A transaction matched to a report has a line of its category and amount in that report, so it is already in the total. The trip records the committed amount, the actual amount, the report, and the ids of the transactions it counted. The actual amount is a record for review; it changes no budget. Nothing is refused because it exceeds the committed amount; the report's own approval already applied the budget rule.
- **Reconciling again.** A Reconciled trip may be reconciled again, by the same rule. It recomputes everything and replaces the trip's reconciliation; it never adds to it. Run with unchanged inputs, it saves the same reconciliation and succeeds.
- **Closing.** When Finance closes a period, every trip for that period still Requested or Approved is closed, and stops counting. Finance may also close a single Requested or Approved trip earlier, with a reason. A Reconciled trip is never closed: its spending counts through its report.
- **Closing a period, in order.** The refusals come first: not Finance, Unauthorized; a period already closed, Conflict. Then each open trip of the period, in the store's order, is saved Closed and then audited. The period is marked closed last. Any failure is returned at once: the trips closed so far stay closed, and the period stays open. A retry does not roll back: it skips trips already Closed, closes the rest, then closes the period. A trip saved Closed whose audit entry failed is not audited by the retry.
- **Auditing.** Every state change of a trip is audited like a report's: each approval step, an amendment that returns an Approved trip to Requested, the reconciliation, and each closing. When the actual amount exceeds the committed one, the reconciliation's audit reason says so. A repeated reconciliation is audited only when its result differs from the one it replaces.
- **Order of writes, and failure.** Every check and refusal comes before the first write. Reconciling saves the trip once, then writes its audit entry. If the save fails, the failure is returned and no audit entry is attempted. If the save succeeds and the audit write fails, the failure is returned and the reconciliation stays saved; a later repeat with unchanged inputs succeeds and does not write the missing entry.
- **Assumptions of this change.** A write that fails leaves the store unchanged, and a write that succeeds is reported as succeeding; no reply is lost. Nothing else changes the store while an entry point runs, so no trip is filed during a period's closing. An audit entry missing after a failure stays missing: audit completeness is not promised.

## Interface

**Trip:** id, badge, department, period, plan (region, days, vehicle, km), committed, approvals (as a report's), status, and, once reconciled, the reconciliation: committed, actual, report id, the counted transaction ids. Status: Requested → Approved → Reconciled, with Approved → Requested on an amendment, and Requested or Approved → Closed.

New entry points:

```
file_trip(badge, period, region, days, vehicle, km) → trip id
amend_trip(trip_id, badge, region, days, vehicle, km) → the trip's status after
approve_trip(trip_id, approver, today) → the trip's status after
reconcile_trip(trip_id, report_id, finance_badge) → the actual amount
close_trip(trip_id, finance_badge, reason) → nothing
```

`close_period(period, finance_badge)` also closes that period's open trips, as above.

**Statement:** spend and remaining include approved trips; after the advance rows, one row per approved trip that still counts something, in the store's order, with `total` and `budgeted` the amount it counts.

**Store** gains `trip(id)`, `trips_for(department, period)` and `trips_in(period)` (every trip there; a period never holds more than 1,000, so the list is always complete), `save_trip(trip)`. `next_id()` supplies trip ids. The audit record's subject gains Trip; an entry for a trip has subject Trip, the trip's id, and the trip's statuses before and after.

## Acceptance

The same hidden cases run against every implementation. They check results; every trip and report saved (status, approvals, committed, reconciliation); every audit entry, including its reason where the case says what it must contain; the order of a reconciliation's and a period closing's writes when one of them fails, and the state a retry starts from; that spend and the statement count each approved trip by its remaining commitment and nothing else from trips; and that everything the starting program already does is unchanged.
