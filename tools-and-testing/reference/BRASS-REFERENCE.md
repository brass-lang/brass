Revision r33, 2026-10-18: r32 with C47 applied, the facts that prove a range where a value enters a ranged type, named refinements included (sections 3 and 7). r32, 2026-10-18: r31 with one sentence beside `++` naming `std.text`'s `of` (spec §8.1, C4), which no earlier revision mentioned; seven of ten Stage 2 Brass sessions hand-built a digit converter and the other three could not put a number in an audit reason. r31, 2026-10-17: r30 with C46 applied, a shared vocabulary for a field that holds a state of one of several machines (section 5). r30, 2026-10-16: r29 with three sentences corrected to the spec (an `is` test, not `in`, gives a named type; a contract proved from an enforced fact reports enforced; an `allow`'s `after` is checked on every successful reply). r29, 2026-10-03, was built from `brass-core-spec.v0.2.md` with change entries C3, C4, C14, C7, C8, C10(a), (d), and (e), C11, C12, C13 with its additions, C15, C16, C18, C19, C20(b), C23, C25, C26, C28, and C31 to C36 applied. Status: source; a run freezes a copy. The language is v0.2 with those entries applied.

# Brass: the editing reference

This is the one document you need to edit Brass code. The explanation and the exact forms sit together: each rule appears once, beside its example. If a rule here and an example here disagree, the rule wins. Report the disagreement as a defect of this document.

Every example comes from a small shipping system: `ship.ids` (plain ids and the `Region` sum), `ship.shipments` (records and states), and `ship.desk` (the entry point and its accesses). It has nothing to do with your project. The examples show forms. They are not answers. Each code block names its file on the first line, except the built-in declarations in section 4.

## 1. Before you edit

Brass is written by models and reviewed by people. The facts a reviewer needs sit in declarations: what a function may reach, what it requires, and what it promises. Most edits can be planned from declarations alone.

**Start from the declaration you were asked about and the code that uses it.**

- If you change a type or a refinement, find the declarations that use it, and inspect each one that depends on the condition you are changing. Finding the first caller is not enough: a refinement shared by two functions changes both.
- Open `system.brass` when an entry point's access parameters, or their bounds, change (section 6).
- Open a body when the declarations do not say what you need.

**What checks your work in this run.** *[Set when a run freezes this copy: one of the two lines below.]*

- *No tool:* nothing compiles or checks. Your patch is reviewed by hand against the rules below, and nothing is proven or enforced.
- *brass:* run `bin/brass` from the project directory; it is allowed, it is not a compiler, and it calls a script outside the project on your behalf. **`bin/brass check`** checks structure and, when clean, prints each entry point in check order: what refuses it and with which code, what it calls and whether a failure passes up, how often a call repeats, and which states it enters. Compare that summary with the requirements; it replaces asking about code you just wrote. `bin/brass check --scenarios` runs each `scenarios/*.json` against a scripted host and compares the result and the order of host calls with what the scenario expects; the file format is in `BRASS.md`. `bin/brass info <module>.<name>` prints a declaration and its direct uses grouped by how they use it, each with its source line, the declaration it sits in, and the tests on its path or its contracts; long answers name the omitted lines and the `--in <module>` call that prints them. **Edit the declarations first. Then run `bin/brass propagate`.** It writes the mechanical consequences into the tree: a new parameter becomes `@@name` at every call, a new state-dependent field becomes `@@name` at every expression entering that state, each hole printed with its type and what is in scope. Fill every hole; a program with a hole is rejected. It then prints `changes`: what changed against the starting tree and the places to inspect, each marked edited or unchanged. Run `bin/brass changes` again after later edits. Ask about several names in one call: `bin/brass info records.Payment desk.refund`. All of it matches by text and says what it could not resolve. Listed places are for looking, not required edits. Nothing proves or rejects anything; your patch is reviewed by hand.

**Contents.** 2 Modules and functions. 3 Conditions on values. 4 Bodies. 5 Record updates and states. 6 Authority. 7 Exact forms and an index of common rejections. 8 Every keyword.

### Learn the sentences, not the words

Brass's keywords come in fixed shapes. Each shape tells you what names exist inside it, what facts hold, and what you may do there.

| Shape | Means | Inside it |
|---|---|---|
| `type T = B where <condition>` | the values of `B` that pass the condition | `it` is the value; its fields are `it.field` |
| `fn f(params) -> T` then `before`, `after`, `example` | an operation and its obligations | `before` names parameters; `after` adds `result` |
| `if x is T then … else …` | a test that picks a branch | inside `then`, `x` counts as a `T` |
| `for x in xs` | a bounded loop | `x` is one element; `break` leaves |
| `any x in xs where cond` | is at least one element like this? | `x` is one element; no effects; `false` when empty |
| `all x in xs where cond` | is every element like this? | same; **`true` when empty** |
| `r with { field: v }` | a copy of `r` with fields changed | the other fields carry over |
| `r with { status enters S }` | a copy of `r` in state `S` | only a declared edge is legal; the `when` fields of `S` must be given |
| `access A` then `allow op(…)` | an outside capability and what it offers | reached only through a parameter of type `A` |

A new form should fit one of these shapes when its meaning fits, and should not borrow a shape whose meaning differs.

### Four distinctions to keep

| These | Differ like this |
|---|---|
| `in` and `is` | `in` asks about membership or walks a collection; `is` asks about a type or an `Ok`/`Err` arm |
| `where` and `if` | `where` states the condition something must meet; `if` chooses between two branches |
| `with` and `enters` | `with` changes ordinary fields; `enters` changes state, and only along a declared edge |
| `after` and `example` | `after` is proven for every input; `example` is one input, tested |

## 2. A module declares what its functions accept and return

A module is one file. Its public declarations come first, then private ones, then the bodies.

```brass
# ship/shipments.brass
module ship.shipments
import ship.ids as ids

interface
  type Weight   = Int where it in 1 to 50000
  type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus }
    # abbreviated: the full declaration adds a state-dependent field (section 5)

  fn grams_over(s: Shipment, ceiling: Weight) -> Int
    after result == s.weight - ceiling
private
  fn is_heavy(s: Shipment) -> Bool
body
  fn grams_over(s, ceiling) = s.weight - ceiling
  fn is_heavy(s) = s.weight >= 20000
```

- `interface` holds what other modules may use; it may not name anything private. `private` holds what only this file may name; omit it when empty. `body` holds the bodies of both.
- Write `interface` and `body` even when they are empty.
- A function is declared once with its parameter types; its body repeats the parameter names without types. A private function is declared too. A body with no declaration is a rejection.
- Every import has an alias, and every imported name is written through it: `ids.ShipmentId`, never `ShipmentId`. Two imports may not share an alias, an alias may not match a parameter name, and imports may not form a cycle.
- Module and import lines carry no version.
- A name for an existing type, `type ShipmentId = Text`, is the same type under a new name; `ship.ids` is a list of these.
- `Text` has a `length`, its number of characters: `type Note = Text where it.length in 1 to 200`.
- Type and constructor names start uppercase; everything else starts lowercase. A keyword is never a name: not `to`, not `in`. The system-file words `system`, `requires`, `grants`, and `limit` are keywords only in the `system` file; in a module, `limit` is an ordinary name.

A record is built by naming every field:

```brass
# ship/shipments.brass
fn pack(id: ids.ShipmentId, w: Weight) -> Shipment                                     # interface
fn pack(id, w) = { id: id, weight: w, fragile: false, status: ShipmentStatus.Packed }  # body
```

**Authority is a parameter.** A function reaches outside the program only through an access it was handed as a parameter (section 6). `grams_over` has none, so it computes and does nothing else.

## 3. Conditions narrow the values a function accepts

### A refinement names a condition

```brass
# ship/shipments.brass
type Ready    = Shipment where it.status in {ShipmentStatus.Packed}        # a condition on a field
type Heavy    = Shipment where it.weight >= 20000
type Route    = { origin: ids.Depot, dest: ids.Depot } where it.origin != it.dest   # across fields
type Batch    = Array<Shipment> where it.length in 0 to 200                # a bounded array
```

- `it` is the value itself, and its fields are `it.field`, nesting by dotted path. A bare field name is a rejection: write `it.shift`, not `shift`.
- A refinement may follow a type anywhere a type is written: a `type` line, a field, a parameter, a return type, a `let`.
- A refined value is accepted where its base type is expected. A base value is not accepted where the refinement is expected.
- A refinement may build on another: `type HeavyReady = Ready where it.weight >= 20000` holds both conditions.

### `in` tests membership, `is` tests a type; a passed test narrows

```brass
# ship/desk.brass
if s is shipments.Ready then Ok(shipments.ship(s, t)) else Err(FailureCode.Conflict, "not packed")
```

Inside `then`, `s` counts as a `Ready`. Tests joined with `and` all narrow. Tests joined with `or` narrow nothing. In `else`, only a single test on machine states or on `Ok`/`Err` knows the complement. A narrowing lasts until the name is rebound.

| Form | Means |
|---|---|
| `x in 1 to 10` | integer range |
| `x in {A, B}` | one of these values |
| `x in s` | member of a named set, such as an access bound |
| `x is T` | passes refinement `T`; `x` must have `T`'s field names and field types |
| `x is Ok`, `x is Err` | which arm an `Outcome` holds |

The right side picks the word. A range or a set takes `in`; a type or `Ok`/`Err` takes `is`. A state test is a set test: `s.status in {ShipmentStatus.Packed}`, and it narrows like any other. `x is None` is a rejection; write `x == None`.

Only `x is T` gives a value a named type. Testing a field, `p.status in {ShipmentStatus.Packed}`, lets you read what depends on that field but does not make `p` a `Ready`, even though that is `Ready`'s condition; to pass `p` where a `Ready` is expected, test `p is Ready`. A value also has a refined type when a parameter or a callee's result declares it. A `let`, argument, field, or result also holds a refinement when the checker can prove its condition there from the facts that establish a `before` (see Types and literals, section 7); a refinement is never established by assertion.

A value the checker can see, a literal, a `const` name, or a `with` whose fields it knows, satisfies a refinement directly when the condition holds on it. No test is needed.

### `before` and `after` are the promises

```brass
# ship/shipments.brass
type Cents = Int where it in 0 to 100000

fn postage(s: Heavy, base: Cents) -> Cents
  before base <= 1000
  after  result == base + 500
```

```brass
# ship/desk.brass
fn fetch(store: Store, id: ids.ShipmentId) -> Outcome<shipments.Shipment>
  after result.id == id
```

- `before` is what the caller must establish: by a parameter's type, a `const` fact, its own `before`, a callee's `after`, an `in` or `is` test on the path, or a comparison on the path that matches the clause.
- `after` is what the function promises on success. On an `Outcome<T>` it applies only to the value inside `Ok`, and `result` names that value: `fetch` promises the shipment it returns has the id asked for.
- Several `before` lines hold together.
- A condition may use: integer `+` and `-`; multiplication by a constant, or of two values whose types bound the product; division and remainder by a nonzero constant; `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`; `not`, `and`, `or`. It may name parameters, `result`, their fields, `const` names, and `length`. It uses no calls, no quantifiers, no floats.
- To promise "when p, then q", write `not (p) or q`: `after not (s.fragile) or result >= 700`.
- At one level of parentheses, a condition uses `and` or `or`, never both. Either may be the outer one: `a and (b or c)`, `a or (b and c)`. The operator table in section 7 refers here.
- What the left side of `and` establishes holds while checking the right side: `x != None and x > 0` is legal.
- Contracts are optional. But a caller's clause that depends on a callee with no contract cannot be proven, and is rejected naming the callee; the remedy is a contract on the callee.

### `example` shows one input and its result

```brass
# ship/shipments.brass
fn postage(s: Heavy, base: Cents) -> Cents
  before base <= 1000
  after  result == base + 500
  example postage({ id: "s1", weight: 25000, fragile: false, status: ShipmentStatus.Packed }, 400) == 900
```

- One call to the function it sits under, with concrete arguments, and the expected result. `brass check` runs it; a different result is a rejection.
- Only on a total `fn` with no access parameter. The arguments must satisfy the parameter types and every `before`.
- It is a tested case, not a proof. It establishes nothing for the checker.

### Every promise has a tier

- **Proven:** the checker proves it before the program runs. This is every contract on a Brass function, unless it is proved from an enforced fact.
- **Enforced:** the runtime checks it on every call. This is an access's reserved bounds and authority checks, every reply from outside, an entry point's `before` lines at the boundary, and anything proved from one of these.
- **Assumed:** nothing checks it.

An `example` is not a promise and has no tier; a report lists it as tested.

Only proven is a guarantee.

## 4. A body evaluates the steps you write

A body is lines run top to bottom, and the last line is the function's value. **Each line runs where it is written.** An `if` runs its condition and then only the branch it takes. `and` and `or` stop at the first operand that decides them. Arguments and fields evaluate left to right.

### `let` names a value, `=` rebinds it

```brass
# ship/shipments.brass
fn total_weight(batch) =
  let total: Int = 0                        # every let names its type
  for s in batch
    total = total + s.weight                # rebinding, same type
  total
```

- Every `let` names its type. A `let` that is never read is a rejection.
- A value computed and then dropped is a rejection, unless it is `Done`, such as `store.save(x)?` on its own line.
- A parameter or loop variable cannot be rebound. A branch that does not rebind a name leaves its old value. Rebinding gives the name a new value; the old value is unchanged, as every value is.
- An `if` used as a value, on the last line or to the right of `let` or `=`, needs both branches. An `if` on a line of its own is a step and needs no `else`.

### `if` is a value, or a step

```brass
# ship/shipments.brass
let fee: Int = if s is Heavy then 900 else 400             # a value
if s.fragile then count = count + 1                        # a step
```

A branch may be an indented block. Its last line is the branch's value:

```brass
# ship/desk.brass
if s is shipments.Ready then
  let t: ids.TrackingId = carrier.book(s, region)?
  store.save(shipments.ship(s, t))                         # the block's value: Outcome<Done>
else Err(FailureCode.Conflict, "shipment is not packed")
```

### A fallible function returns `Outcome<T>`

```brass
type Outcome<T>  = Ok(T) | Err(FailureCode, Text)
type FailureCode = Unauthorized | InvalidInput | Conflict | Unavailable | ResourceExhausted | Other | Unknown | NotFound
```

- A function that can fail returns `Outcome<T>`. Nothing else marks it.
- A declaration continues onto the next line while a `(`, `<`, or `{` it opened is still open, as in Python; indentation inside does not matter.
- A function with no value to return declares `Outcome<Done>` and ends a successful path with `Ok(Done)`.
- `Err` always takes a code and a text in the program's words: `Err(FailureCode.NotFound, "no such shipment")`. `Unknown` is the runtime's code for a call with no reply; a program does not write it. When no code fits, write `Other`.
- `x?` gives the value inside `Ok`, or returns the `Err` to the caller at that point. It is legal only inside a function that returns `Outcome`.
- To replace a failure with your own, test first; then `?` in the branch where the value is known to be `Ok` gives the value and cannot fail:

```brass
# ship/desk.brass
if last is Err then Err(FailureCode.Unavailable, "carrier did not book in three attempts")
else
  let t: ids.TrackingId = last?                 # known Ok here
  store.save(shipments.ship(s, t))
```

- When the last line is a call, `call()` returns its `Outcome` as is; `call()?` as the whole last line is a rejection, since it yields the inner value. A `?` nested inside, as in `Ok(f(x)?)`, is fine.
- A body can test `x is Err` but cannot read which code came back.
- An `Err` undoes nothing. Effects already made through an access stand, so check what can refuse before you act.
- A retry loop retries every failure, `Unknown` included. Retry only an operation that is safe to repeat, or one that takes a key.
- A failure code describes the operation that produced it, not the function that passed it up. An `Unauthorized` passed up by `?` says nothing about effects made earlier in the same function.

### A value that may be absent is `Maybe<T>`

```brass
# ship/shipments.brass
fn label(note: Maybe<Text>) -> Text                                       # interface
fn label(note) = if note != None then "fragile: " ++ note else "standard"  # body
```

- A `Maybe<T>` holds a `T` or `None`. The caller passes the value itself, `label("glass")`, or writes `None`, `label(None)`. Nothing is filled in for a missing argument.
- Inside `if note != None then …`, `note` is a plain `Text`. Inside `if note == None then …`, it is `None`. The `else` of either knows the other.
- A `Maybe<T>` is legal for any `T` except another `Maybe`: `Maybe<Maybe<T>>` is a rejection.
- Use `Maybe` when absence is normal. Use `Err(FailureCode.NotFound, …)` when absence is a failure.

### A lookup that can fail goes where it is needed

There is no early exit, so tests nest. Name the cheap facts first with `let`, then decide. A lookup with `?` runs on the line where you write it, so write it after the tests that decide whether it is needed.

```brass
# ship/desk.brass
fn dispatch(carrier: Carrier, store: Store, id: ids.ShipmentId, region: ids.Region) -> Outcome<Done>           # interface

fn dispatch(carrier, store, id, region) =                                                                      # body
  let s: shipments.Shipment = store.shipment(id)?
  if s is shipments.Ready then
    let cleared: Bool = if region in {ids.Region.Abroad} then store.customs_cleared(s.id)? else true
    if cleared then
      let t: ids.TrackingId = carrier.book(s, region)?
      store.save(shipments.ship(s, t))
    else Err(FailureCode.Conflict, "customs has not cleared this shipment")
  else Err(FailureCode.Conflict, "shipment is not packed")
```

A domestic dispatch never calls `customs_cleared`, so its failure cannot stop one.

Negate with `not`: `not cleared`, `not (s is Heavy)`. `not` binds looser than a comparison, so `not a == b` is `not (a == b)`. Under `not`, a passed test narrows nothing.

### Loops are bounded

```brass
# ship/desk.brass
let last: Outcome<ids.TrackingId> = Err(FailureCode.Unavailable, "not tried")
for attempt in 1 to 3
  last = carrier.book(s, region)
  if last is Ok then break
```

```brass
# ship/shipments.brass
let ready: Batch = []
for b in batch                                   # batch: Batch, so its length is bounded
  if b is Ready then ready = ready ++ [b]
```

- A `for` walks a range or an array whose type bounds its `length`. The loop variable may go unread. Inside `for i in 1 to 100`, `i` is known to lie in `1 to 100`.
- A loop that starts from `[]` and appends at most one element per source element keeps the source's length bound. Nothing else about appends is proven.
- `break` leaves the nearest enclosing loop, and the body continues after it. `lo to hi` includes both ends: `1 to 3` runs three times. There is no `while`, `return`, recursion, or `match`.

### `any` and `all` replace a flag loop

```brass
# ship/shipments.brass
fn has_fragile(batch) = any b in batch where b.fragile
fn all_ready(batch) = all b in batch where b is Ready
```

- Both are `Bool`. `any` over an empty array is `false`.
- **`all` over an empty array is `true`.** If at least one element is required, say so: `batch.length > 0 and all b in batch where b is Ready`.
- Elements are tested in order; evaluation stops once the answer is known.
- The predicate is total and effect-free: no `?`, no access call. Narrowing works inside it as anywhere else.
- `b` exists only inside the expression; the condition also sees every name around it, parameters included. The predicate runs to the end of the expression; parenthesize to combine.
- Body only: not in a `before`, `after`, or `where`.

## 5. Updates preserve a record and change named fields

### `with` copies a record and replaces fields

```brass
# ship/shipments.brass
let marked: Shipment = s with { fragile: true }                  # every other field is copied
```

The braces hold a partial record literal. A repeated field, an unknown field, or an empty `with { }` is a rejection. A `with` that changes none of the fields a refinement tests keeps that refinement: a note added to a `Ready` shipment is still `Ready`. Changing a field that a refinement tests, `enters` included, gives back the base type; the checker can establish the refinement again from the fields it sees (section 3).

### A machine lists the legal state changes

```brass
# ship/shipments.brass
machine ShipmentStatus
  states  Packed, Shipped, Arrived, Returned
  initial Packed
  Packed  enters Shipped
  Shipped enters Arrived | Returned

type InTransit = Shipment where it.status in {ShipmentStatus.Shipped}

fn land(s: InTransit) -> Shipment                                       # interface
fn land(s) = s with { status enters ShipmentStatus.Arrived }            # body
```

- A state change is `enters` inside `with`. Writing it as a plain `status: ShipmentStatus.Arrived` inside `with` is a rejection.
- A `with` that does not name the state keeps it: `s with { fragile: true }` leaves `status` as it was. Staying in a state needs no edge.
- `enters` names one state. To choose between two, branch: `if done then s with { status enters A } else s with { status enters B }`.
- The checker must know that every possible current state has an edge to the target. Here the parameter's type says `s` is `Shipped`.
- A literal may hold an initial state, or a state obtained legitimately: from `enters`, from an access's reply, or from an entry point's parameter. Inventing a later state in a literal is a rejection.

### `when` attaches a field to some states

The full `Shipment` declaration gives a shipped value a tracking number:

```brass
# ship/shipments.brass
type Shipment = { id: ids.ShipmentId, weight: Weight, fragile: Bool, status: ShipmentStatus,
                  tracking: ids.TrackingId when it.status in {ShipmentStatus.Shipped, ShipmentStatus.Arrived} }

fn ship(s: Ready, t: ids.TrackingId) -> Shipment                                 # interface
fn ship(s, t) = s with { status enters ShipmentStatus.Shipped, tracking: t }     # body
```

- The field exists only in the listed states. The field it tests (`status`) is itself unconditional, and its type is a named type.
- Read it only where the value is known to be in one of them, by its type or by an `in` test.
- The update that enters the states must supply the field. A move between listed states keeps it. The update that leaves them drops it, and naming it there is a rejection.
- A literal or update outside those states must not mention it.

### A field for states of several machines takes a shared vocabulary

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

## 6. External operations require an access parameter

An access is how a Brass program reaches anything outside it. The host implements its operations; `system.brass` hands it out. An `access` is a declaration like any other: it sits in `interface`, or `private`, indented like a `type`, and the entry points that take it are declared beside it.

```brass
# ship/desk.brass
access Carrier { regions: Set<ids.Region>, budget_calls: Int }
  allow book(s: shipments.Ready, region: ids.Region) -> Outcome<ids.TrackingId>
    before region in regions and s.weight <= 50000

access Store
  allow shipment(id: ids.ShipmentId) -> Outcome<shipments.Shipment>
  allow save(s: shipments.Shipment) -> Outcome<Done>
  allow customs_cleared(id: ids.ShipmentId) -> Outcome<Bool>
```

- A body calls an operation through its parameter: `carrier.book(s, region)`.
- Every `allow` returns `Outcome<T>`.
- A `before` on an `allow` splits by conjunct. A conjunct that names a bound, `region in regions`, is an **authority check**: the runtime refuses the call with `Unauthorized` before anything happens. Any other conjunct, `s.weight <= 50000`, is a **contract** the caller proves; here `Weight`'s range proves it.
- An `after` on an `allow` is checked on every successful reply; it says nothing about an `Err`.
- A bound that no `before` names checks nothing; it reports assumed.
- `budget_<unit>` and `deadline_ms` are reserved bounds the runtime enforces. An access has at most one `budget_` field, and a bare `budget` is a rejection. A call past `deadline_ms` returns `Unavailable` if it was never sent, `Unknown` if it was sent and the reply was late. `budget_calls: 20` allows twenty calls per run of the entry point; past that, calls return `ResourceExhausted`.
- An access is never stored, returned, or put in a record. A function passes on the whole access it holds; nothing in a body narrows one.

**A state change that depends on a computation belongs in one pure helper with `after` clauses,** `fn apply_refund(p: Open, amount: Cents) -> Payment`, which an `example` or a scenario can test on its own; the entry point then calls it once.

**A requirement on who or what may cause an effect goes on the operation.** Put it in the operation's parameter type or `before`, as `book` takes only a `Ready` shipment. A caller holding a plain `Shipment` tests `s is Ready` first; a test on `s.status` alone does not make it a `Ready`.

### `system.brass` grants accesses to entry points

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

- An entry point is a function with a `grants` line. Each of its access parameters is filled by name, with its bounds; the braces are omitted when the access has none. `none` exposes a function that holds no access.
- A grant only narrows: a subset of a set, a lower limit.
- The line changes when an entry point gains, loses, or renames an access parameter. Other parameters do not appear in it.
- The three runtime `limit` lines are required; `impact_modules` is an optional review policy: exceeding it gives a review notice, not a check failure, and omitting it sets no cap (spec §10.1 says when each is checked and what happens). The `system` line carries no version; a `requires` line names a release, `requires std = brass.std v0.2`.
- At the boundary, the runtime checks an entry point's arguments against its parameter types and every `before`, before the body runs. So a check the requirements order after others belongs in the body, with a plain parameter type. A failure replies `InvalidInput` and the function never runs.

## 7. Look up an exact form

### Operators, tightest first

| # | Operators | Associativity |
|---|---|---|
| 1 | `f(x)` call, `.` member access | left |
| 2 | `?` failure propagation | postfix |
| 3 | `^` exponentiation, constants only | right |
| 4 | `-x` negation | prefix |
| 5 | `*` `/` `%` | left |
| 6 | `+` `-` `++` | left |
| 7 | `==` `!=` `<` `<=` `>` `>=` `in` `is` | none: `a < b < c` is a rejection |
| 8 | `not` | prefix; `not a == b` is `not (a == b)` |
| 9 | `and`, `or` | left; see section 3 on mixing |

`with` and `enters` take the whole level-1 and level-2 expression on their left; parenthesize to compose. `++` joins text or arrays; `+` never joins. To put a number in text, import the bundled module `std.text` (`import std.text as text`) and write `"period " ++ text.of(n)`: `of` takes an `Int`, gives its decimal text, is total and pure, and needs no access.

### Types and literals

- Base types: `Int8 Int16 Int32 Int64 Int Float Bool Text Bytes Array<T> Set<T> Outcome<T> Done Maybe<T>`. Integers are signed; `Int` is `Int64`. Never negative is a refinement: `Int where it in 0 to n`.
- Literals: `true`, `false`, `0`, `1.5`, `"text"`, `[]`, `[a, b]`, `{a, b}`. A literal takes its type from where it stands. A literal nowhere typed is a rejection.
- Constructors are always qualified, in their own module too: `ShipmentStatus.Packed`, `ids.Region.Home`. Only a state named inside its own `machine` declaration is bare. `Ok`, `Err`, `Done`, `None` stay bare.
- Sums are bare names: `type Region = Home | Abroad`. Only `Ok(x)` and `Err(code, text)` take arguments.
- Arithmetic takes two integers or two floats of one type, never mixed. `%` and `^` are integer only.
- Arithmetic on ranged integers gives a plain `Int`: where `n: Int where it in 1 to 100`, `n - 1` is an `Int`. A range is proven where a value is stored or passed into a ranged type, never inside a comparison. The proof uses the facts that establish a `before`: the operands' declared types, `const` facts, the function's `before`, a callee's `after`, and an `is` test or a comparison on the path. It holds for a named refinement whose condition is a range, such as `Cents`, as for an inline one: where `c` and `v` are `Cents`, `if c > v then c - v else 0` is a `Cents`. Arithmetic on an unranged integer that overflows aborts; it never wraps.
- An abort ends the task; nothing catches it. Only these abort: overflow on an unranged integer, memory or CPU past its `limit`, an `allow` reply that breaks its `after`, and a proven `before` or `after` failing at run time.
- Division needs a divisor the checker can show is not zero.

### Constants

```brass
# ship/shipments.brass
const max_weight: Int = 50000                            # inline
```

A `const` name may stand anywhere a literal of its type may, including conditions.

### Holes

`@@name` stands for a value not written yet. A program with a hole is rejected; the checker lists each hole with its type and what is in scope.

### Projections

`type Parcel = { … } projects to Label` lets a `Parcel` be passed wherever a `Label` is expected, copying `Label`'s fields by name. There is no syntax at the use and no reverse. It is rejected if a target field is missing or has another type, if a target condition does not follow from the source's, or if it copies a machine field. Nothing else converts between types.

### Common rejections, and where the rule is

| Rejection | Section |
|---|---|
| `return`, `while`, `match`, recursion | 4 |
| untyped or unused `let`; a dropped value | 4 |
| mixed `and`/`or` without parentheses | 3 |
| imported name without its alias; unqualified constructor | 2, 7 |
| a version on a `module`, `import`, or `system` line | 2, 6 |
| `Err` without a text; `call()?` as the last line | 4 |
| a `when` field read where its state is not known | 5 |
| a bare field name in a `where`: write `it.field` | 3 |
| a state written as a plain value inside `with` | 5 |
| `any` or `all` in a contract; `?` or an access call inside their predicate | 4 |
| an `example` on a fn that returns `Outcome` or one taking an access; an example whose result differs | 3 |

### Not in this version

`Map<K, V>`, function values, unbounded loops, and narrowing an access inside a body. If a task seems to need one of these, or anything section 4 rules out, say so in your answer rather than inventing a form.

## 8. Every keyword

Forty-one words. Thirty-seven are reserved in every file and are never a name. Four are reserved only in `system`.

**By where they appear.**

| Where | Words |
|---|---|
| a module's declarations | `module import as interface private body type where it in is to and or not when with projects fn before after example access allow machine states initial enters const` |
| a body | `let if then else for break any all` |
| the `system` file only | `system requires grants limit` |

**By what they do.**

| Purpose | Words |
|---|---|
| file layout | `module import as interface private body` |
| values and types | `type where it const projects` |
| operations and promises | `fn before after example` |
| tests and logic | `in is to not and or` |
| records and states | `with machine states initial enters when` |
| authority | `access allow` |
| steps in a body | `let if then else for break any all` |
| system configuration | `system requires grants limit` |

Built in, not keywords: `Ok Err Done None result length`.
