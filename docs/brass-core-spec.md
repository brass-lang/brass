# Brass Core Specification v0.3

This file defines the language rules. The [grammar](brass-core-grammar.md) provides syntax examples and lookup tables. [Principles](brass-core-principles.md) records design choices, reasons, and evidence. Open and deferred questions are kept in a private considerations file; [HISTORY](../HISTORY.md) lists what is still to decide.

Companion documents define [report formats](design/brass-report-design.md), runtime mechanics (a private design note, to be rewritten once the runtime is decided), and [required checker cases](design/brass-checker-design.md). This specification takes precedence when a companion disagrees.

## 0. Scope and tiers

This specification defines Brass v0.3, a language for code that AI models write and modify while humans review it.

The full checker and the runtime are not yet implemented; the `brass` tool does not establish conformance to this specification.

Every obligation and access bound carries a tier. Reports display tiers as specified in §12.

| Tier | Meaning |
|---|---|
| proven | The checker proves the obligation before execution. |
| enforced | The runtime checks the obligation on every applicable call. |
| assumed | Nothing checks the obligation. The program proceeds as if it held. |

Only a proven obligation is called a guarantee. Conditions on these guarantees are in §11.2.

## 1. Reference index

| Question | Section |
|---|---|
| Which values and operators exist? | §2 |
| How are functions, bindings, branches, and loops written? | §3 |
| Which declarations are public or private? | §4 |
| How are failure and absence represented? | §5 |
| What do contracts and examples establish? | §6 |
| How are refinements tested and records projected? | §7 |
| What authority can a function use? | §8 |
| Which state changes and conditional fields are legal? | §9 |
| How are dependencies, grants, limits, and execution recorded? | §10 |
| What does checking establish? | §11 |
| What does `brass` report? | §12 |

## 2. Types, values, and names

Refinements are defined in §7. Failure and absence types are defined in §5.1.

| Type | What it is |
|---|---|
| `Int8 Int16 Int32 Int64 Int` | fixed-width signed integers, two's complement; `Int` is `Int64` |
| `Float` | IEEE 754 binary64, one width |
| `Bool` | A Boolean value. Its literals are `true` and `false`. |
| `Text` | Text. `length` counts characters. |
| `Bytes` | a byte sequence; a size is an `Int` named for its unit |
| `Array<T>` | one ordered collection; `[]` and `[a, b]` are its literals; `length` is a field-like path |
| `Set<T>` | A set used for bounds and membership. Its literal is `{a, b}`. Sets are not iterable. |
| `Outcome<T>`, `Done` | §5.1 |
| `Maybe<T>` | §5.1 |

A record is declared as `type Name = { field: Type, … }`. Fields are written and read by name. `type Name = T` names an existing type. The two types are interchangeable.

A sum is declared as `type Name = A | B`. Its arms are bare names without payloads. The built-in `Ok` and `Err` arms carry data (§5.1). `Map<K, V>`, unions of record types, and function values are not defined in v0.3.

```brass
# support/types.brass — declaration excerpts
type PaymentId = Text
type Processor = Stripe | Adyen
type Receipt = { amount: Int, customer: Int }
```

Type and constructor names begin uppercase. Module, function, parameter, field, and alias names begin lowercase. A name with the wrong initial case is rejected. A keyword is never a legal name. Reserved words are listed in §2.3.

A declaration may continue onto following lines while a `(`, `<`, or `{` it opened is unclosed. Those lines belong to the declaration regardless of indentation.

Constructors are qualified by their type: `CaseStatus.Open`, `FailureCode.NotFound`. Built-ins `Ok`, `Err`, `Done`, and `None` stay bare, as do states inside their own machine declaration. Qualification lets a type and constructor share a name.

Every literal takes its type from its position: a typed `let`, an argument, a return, a field, or the other operand of an operator. A literal in no typed position is a rejection.

Literals carry no suffix. `0` is the one spelling of zero and is legal in a `Float` position. A literal with a point, such as `1.5`, is rejected in an integer position.

`a ^ b` writes a large integer using exponentiation. Both operands must be constants evaluated at check time, and the exponent must be zero or positive. `a ^ 0` is `1`. This is not a runtime operation. For declared record projections, see §7.4.

`const name: Type = value` declares a checker-known value inline. A table uses a record or array literal. Constants are part of the module recorded by `lock` (§10.2). A `const` name may appear wherever a literal of its type may, including contracts and refinements.

```brass
# bank/types.brass — constant excerpt
const max_balance: Int = 100000000000
```

Rejected: loading a constant from a file is not a defined form.

### 2.1 Arithmetic

`+ - * /` apply to two integers or two floats of one type, never mixed. `-x` negates an integer or float. A negative literal is written `-100`. Negating an integer's minimum value overflows and aborts like any other overflow. `%` and `^` are integer only.

`++` joins two `Text` values or two arrays of one element type and nothing else. `+` never joins.

Integer division and remainder require a nonzero divisor. The checker must prove this from its type or a guard on the path. Otherwise it rejects the program and names the divisor. `/` truncates toward zero. `%` takes the sign of the dividend.

A range refinement is always permitted on an integer type and never required. Arithmetic on refined integers has the base type. If `n` has type `Int where it in 1 to 100`, `n - 1` is an `Int`.

A range is checked when a value enters a ranged type through a `let`, argument, field, or result. The range must be proved there or the program is rejected. A comparison such as `m == n - 1` is not such a location.

Integer overflow never wraps. Arithmetic on an integer type without a range aborts if it overflows that type's width. The report (§12) marks every such operation. Every intermediate is computed at 64 bits and checked against the type it flows into.

Floats are outside the contract fragment (§11.1) and never abort. They compare by IEEE equality: `NaN == NaN` is false, the one exception to structural equality. A body compares floats with `== != < <= > >=`. Range membership is defined in §7.3.

Operator precedence and grouping are defined in §2.2.

### 2.2 Operator precedence and grouping

Operators bind in this order, tightest first.

| # | Operators | Associativity |
|---|---|---|
| 1 | `f(x)` call, `.` member access | left |
| 2 | `?` failure propagation | postfix, applies to the expression on its left |
| 3 | `^` exponentiation, constants only | right |
| 4 | `-x` negation | prefix |
| 5 | `*` `/` `%` | left |
| 6 | `+` `-` `++` | left |
| 7 | `==` `!=` `<` `<=` `>` `>=` `in` `is` | non-associative: a chain is a rejection |
| 8 | `not` | prefix; `not a == b` is `not (a == b)` |
| 9 | `and`, `or` | left; not mixed at one parenthesis level |

`with` and `enters` take the full level 1–2 expression on their left, do not chain, and are parenthesized to compose. `@@name` is a primary expression (§3.2). `to` is range syntax, not an operator. `->` is return-type syntax only.

At one parenthesis level, a condition may use `and` or `or`, not both. Mixing them is rejected. The checker never inserts parentheses.

Rejected: `a < b < c` chains comparisons. Write `a < b and b < c`.
Rejected: `a and b or c` mixes operators. Write `(a and b) or c` or `a and (b or c)`.

### 2.3 Reserved words

The following language and body keywords are reserved in every file.

- Language: `module import as interface private body type where it in is to and or not when with projects fn before after example access allow machine states initial enters const`.
- Body: `let if then else for break any all`.

`system`, `requires`, `grants`, and `limit` are reserved only in a `system` file. They are ordinary names in a module.

`Ok`, `Err`, `Done`, `None`, `result`, and `length` are built-ins, not keywords. `?`, `@@`, `->`, `=`, and `#` are tokens. For `none` and `drop oldest`, see §10.1.

## 3. Functions and bodies

A function has a typed declaration, `fn name(params) -> Type`, and a body, `fn name(params) = …`, with parameter names only. Declaration placement is defined in §4. Contracts are defined in §6. For fallible functions, see §5.1. For body replacement, see §11.2.

**Body result.** Lines run from top to bottom. The last line is the function's value.

Earlier lines may:

- Bind a name with `let` or rebind a local name.
- Loop with `for`, leave a loop with `break`, or branch with `if`.
- Call a function whose value, after `?` if present, is `Done`.

Discarding any other value is rejected.

**Branches.** An `if` used as a step may omit `else`. An `if` used as a value requires both branches and yields the selected branch's value.

A branch may contain an indented block beneath `then` or `else`. The block follows body rules. Its last line is its value. A `for` body uses the same block layout.

```brass
# bank/control.brass — branch excerpt
if raw.amount > src.balance then Err(FailureCode.Conflict, "insufficient funds")
else
  let done: transfers.Transfer = transfers.transfer(src, dst, raw.amount)
  banking.write(done.from_acc)?
  Ok(Done)
```

Rejected: an `if` used as a value without an `else`.

**Bindings.** Every `let` names its type: `let name: Type = expr`. An untyped `let`, a type mismatch, or an unused `let` is a rejection. The unused-binding rule checks only whether the binding is used; a loop variable may go unread.

`name = expr` rebinds a local `let` to a value of the same type. Parameters, loop variables, and interface names cannot be rebound. A rebinding inside a `for` block survives the loop, as any rebinding does. Only the loop variable is gone after it. If an `if` branch does not rebind a name, it keeps its old value on that branch.

**Loops.** `for x in <array>` and `for i in lo to hi` are the bounded iteration forms.

Range endpoints and the loop variable are `Int`. `lo to hi` includes both ends: `1 to 3` is 1, 2, and 3, and `3 to 1` is empty. Inside `for i in lo to hi`, `i` is known to lie in `lo to hi`.

In a refinement, `where it in lo to hi`, the endpoints instead take the refined base type. A range is bounded by its type. A loop over an array requires a type that bounds `length`. Nested loops multiply their bounds for termination.

`break` exits the nearest enclosing loop and carries no value. Execution continues after that loop. `while`, `return`, recursion, and unbounded loops are not permitted.

Rejected: iterating over an unbounded `Array<T>` or making a recursive call.

```brass
# park/doors.brass — body excerpt
fn lockdown(doors, operator, p) =
  let last: Outcome<Done> = Err(FailureCode.Unavailable, "not tried")
  for attempt in 1 to 3
    last = doors.close(operator, p.id)             # host assumption: closing is safe to repeat; see spec §5.2
    if last is Ok then break
  if last is Ok then Ok(p with { status enters enclosures.Enclosure.Secured })
  else Err(FailureCode.Unavailable, "door did not close in three attempts")
```

**`any` and `all`.** `any x in xs where p` is `true` when `p` holds for at least one element; `all x in xs where p` is `true` when it holds for every one. Both are `Bool` expressions, legal in a body.

```brass
# park/health.brass — body excerpts
fn any_feverish(animals) = any a in animals where a is Feverish
fn all_fever_free(animals) = all a in animals where not (a is Feverish)
```

- **Source.** The permitted sources are the same as for `for` above.
- **Empty.** `any` over nothing is `false`. `all` over nothing is `true`. Neither form requires a nonempty source.
- **Order.** Elements are tested in array order, and evaluation stops at the first element that decides the answer.
- **The predicate** is a `Bool` expression, total and effect-free: no `?`, no access call, no call to a function that returns `Outcome`. Narrowing inside it follows the ordinary rules, so `c is Valid and c.badge == badge` reads `c` as a `Valid` on the right of `and`.
- **The bound name** exists only inside the expression, and follows a loop variable's rules. The condition also sees every name in scope where the expression stands, parameters included.
- **Extent.** The predicate runs to the end of the expression, as an `else` does. Parenthesize it to combine it with another expression: `(any c in cs where p) and q`.
- **Contracts.** See §11.1 for the permitted fragment.

**Filter bound.** Starting with an empty array and appending at most one element per source element proves that the result's length is at most the source's length. The source array must be bounded. The checker proves no other append bounds by this rule. Returning `Outcome` does not excuse an unproved bound.

```brass
# support/filter.brass — body excerpt
let kept: Array<OpenCase> where it.length in 0 to 1000 = []
for c in cases  # cases: Array<CaseRecord> where it.length in 0 to 1000
  if c is OpenCase then kept = kept ++ [c]
kept
```

### 3.1 Fixed rules

Values are immutable. Rebinding changes what a name refers to, not the previous value. There is no observable address or identity, and no finalizer. Equality is structural.

Operands, call arguments, and record fields evaluate left to right in source order. `and` and `or` stop at the first operand that decides the result. An `if` runs its condition and then only the branch it takes. Arrays iterate in element order.

### 3.2 A hole marks an unfinished expression

`@@name` marks an unfinished expression. A program containing a hole is rejected. `brass check` reports each hole's expected type and bindings in scope.

```brass
# park/control.brass — rejected incomplete expression
registry.save_feeding(feeding.deliver(f, @@deliverer))?
```

## 4. Modules and imports

A module occupies one file. It starts with `module <name>`, without a version, followed by imports, `interface`, an optional `private` section, and `body`. `interface` and `body` are written even when empty. `interface` holds what importers see.

`private` holds types, constants, and signatures with their contracts. Only this file may name them. They are outside the interface hash and absent from reports on their own. An `interface` declaration may not name anything private.

An interface determines authority, inputs, outputs, contracts, constants, and legal state transitions. It does not determine what a body computes. `body` holds implementations for public and private functions. Function syntax is defined in §3.

A function declared in neither `interface` nor `private` is rejected. `private` appears only in that heading. There are no visibility modifiers and no export list: disclosure follows placement.

```brass
# park/control.brass — module layout
module park.control
import park.ids as ids
import park.feeding as feeding

interface
  …
private
  …
body
  …
```

Every import binds a file-local alias: `import <name> as <alias>`. Every imported name is used as `alias.name`. Bare imported names, shared aliases, aliases matching parameter names, and import cycles are rejected.

Names resolve in the system's source tree or through a `requires` line (§10.1). A name resolving in both places, or neither, is rejected. `lock` records each resolution. Base types and built-ins are not imported. For authority, see §8.

The interface hash covers its declarations with comments and whitespace between tokens removed. Text literals are hashed exactly. A `#` comment directly above a declaration is shown by `brass info` and is outside the hash.

Comparing an interface against a named baseline, `brass` reports **compatible**, **incompatible**, or **not established**. `not established` is neither a rejection nor a proof. Checking the callers a system has today establishes nothing about the callers it does not have.

## 5. Failure

Aborts are defined in §10.4.

### 5.1 `Outcome`

`Outcome<T>` holds either `Ok(T)` or `Err(FailureCode, Text)`.

```brass
# builtins.brass — built-in type notation
type Outcome<T>   = Ok(T) | Err(FailureCode, Text)
type FailureCode  = Unauthorized | InvalidInput | Conflict | Unavailable | ResourceExhausted | Other | Unknown | NotFound
```

A fallible function declares `-> Outcome<T>` in full. This return type is the only marker that it may return `Err`. Nothing wraps a return type by implication. It establishes nothing about effects, termination, or freedom from aborts.

A function with no success payload declares `-> Outcome<Done>`. `Done` is both the type and its one value.

`Err` always takes a code from the closed set and text for the transcript and reader. A body may choose a code when constructing an `Err`, but cannot read one. It can only test `x is Err` and pass the value on.

A failure code describes the operation that produced it. An `Unauthorized` passed up by `?` says that operation had no effect. Effects from earlier operations in the same function remain (§10.4).

The following codes have specified meanings:

- **`Unknown`:** produced only by the runtime when an operation was requested but no result was received. The effect may have happened. Retrying is unsafe unless the operation is idempotent.
- **`Unavailable` on a deadline failure:** the runtime never dispatched the call. Other uses of `Unavailable` do not necessarily mean a retry is safe.
- **`ResourceExhausted`:** a quota was exhausted. The transcript names it.
- **`NotFound`:** a lookup found no result and that is a failure. For absence represented as a value, see `Maybe<T>` below.
- **`Other`:** the program's choice when no category fits.

**Propagation.** `expr?` yields the value inside `Ok` and returns any `Err` to the caller.

Propagation is legal only inside a function whose return type is `Outcome<T>`. In a total function it is rejected.

A body whose type is `Outcome<T>` yields `Ok(…)`, `Err(…)`, or propagates with `?`. On its last line, `call()` returns the `Outcome` itself. Writing `call()?` there is rejected because it yields a `T`.

```brass
# park/control.brass — propagation excerpt
fn deliver_as(registry, by, paddock) =
  let f: feeding.PendingFeeding = registry.pending(paddock)?
  let done: feeding.DeliveredFeeding = feeding.deliver(f, by)
  registry.save(done)?
  Ok(done)
```

**`Maybe<T>`.** A value that may be absent has the type `Maybe<T>`, and only such a value may be absent.

A `Maybe<T>` holds either a `T` or `None`. The caller passes the value itself or writes `None`. An omitted argument is not supplied as `None`. A `T` is accepted where a `Maybe<T>` is expected. Other permitted conversions are indexed in §15.

`None` is accepted where any `Maybe<T>` is expected and nowhere else. Its type comes from its position.

Where `x != None` holds, `x` counts as a `T`. Where `x == None` holds, `x` is `None`. The `else` of either test establishes the opposite condition.

Combination with other tests follows §7.2. A `Maybe<T>` is legal for any `T` except another `Maybe`: `Maybe<Maybe<T>>` is a rejection. `Maybe<T>` has no unwrapping operator or default value. Constructor matching is not defined in v0.3.

```brass
# park/control.brass
fn lockdown(doors: Doors, registry: Registry, operator: ids.BadgeId,
            second: Maybe<ids.BadgeId>, gates: Array<ids.GateId> where it.length in 0 to 50) -> Outcome<Done>
body
  ...
  if second != None then
    let keeper: staff.Staff = registry.staff(second)?                    # second is a plain BadgeId here
    ...
  else Err(FailureCode.Unauthorized, "a second keeper is required")
```

### 5.2 What crosses the boundary

For invalid entry-point inputs, see §8.5. For invalid `allow` replies, see §8.3 and §10.4.

By convention, an `allow` whose repeat would be a second effect declares a key parameter, `allow charge(key: IdemKey, …)`, and every retry of one logical operation reuses the key. The key alone guarantees nothing: the receiving operation must honor it. Nothing checks the convention in v0.3.

A retry loop cannot tell `Unknown` from any other failure, so it retries them all. Retry only an operation that is safe to repeat, such as closing a door, or one that takes a key. Nothing checks this in v0.3.

## 6. Contracts are proved or the program is rejected

`before` states what must hold at entry. The caller establishes it. `after` states what must hold on successful return. The implementation establishes it.

```brass
# support/refund.brass — declaration excerpt
fn issue(pay: StripePay, who: Merchant, case: payments.OpenCase, amount: payments.Money) -> Outcome<payments.Receipt>
  before amount > 0
  before case.merchant == who.id
  before amount <= who.refund_limit
  before amount <= case.paid_total
  after  result.amount == amount
```

On a function returning `Outcome<T>`, `after` applies only to the value inside `Ok`. It says nothing about `Err` or an abort.

A caller establishes a `before` through any of these facts:

- A parameter's type.
- A fact established by a `const`.
- Its own `before`.
- A callee's `after` on a value it holds.
- An `if x is T` test on the path.
- A comparison on the path whose clause the checker can match. For example, `if o.cost <= cap then …` establishes `before o.cost <= cap`.

A `before` that no input satisfies is rejected. Contradictory clauses are rejected together.

Rejected edit: add `before amount <= 0` beside the example's `before amount > 0`.

Contracts are optional on every declaration. A function without them is checked for types, termination, authority, and states, and nothing more. A declaration is never rejected for lacking a contract.

If a caller's clause cannot be proven because a callee states no contract, it is rejected as not proven. The diagnostic names the callee. The remedy is a contract on that callee.

Every contract clause on a Brass function is proven at check time or the program is rejected. Two kinds of clause belong to the runtime instead: an `allow`'s authority checks and its `after` (§8.3).

The runtime evaluates every proven clause again: `before` at entry and `after` on successful return. A failing clause aborts the task. The transcript names the clause and the values.

Run-time evaluation does not change the tier. A clause proved from an enforced fact, such as an `allow`'s `after`, reports enforced.

### 6.1 Checked examples

`example f(args) == value` specifies one call to the function under whose declaration it appears, and the expected result.

```brass
# fizz/fizz.brass
fn fizz(i: Int where it in 1 to 100) -> Text
  example fizz(15) == "FizzBuzz"
  example fizz(9) == "Fizz"
  example fizz(7) == "7"
```

- **Values.** Every argument and the expected value are concrete: a literal, a constructor, a record or array literal of concrete values, or a `const` name.
- **Placement.** An `example` may sit under a total `fn` with no access parameter. On a function that returns `Outcome`, an `allow`, or a function that takes an access, it is a rejection.
- **Inputs are legal calls.** The arguments must satisfy the parameter types and every `before`. One that does not is a rejection naming the type or clause.
- **The check runs it.** `brass check` evaluates every example. A result not equal to the expected value is a rejection that prints both. An example exceeding 1,000,000 evaluation steps is rejected. This budget is fixed.
- **Report.** A report lists an example as `tested`, never as proven, and it has no tier. It establishes no fact for the checker and stands in for no `before` or `after`. A regenerated body must pass it as required by §11.2.
- **Excluded forms.** No fixtures, generators, mocks, or assertion forms beyond `==`.

## 7. A refinement is a named condition

Refinement syntax is defined in §7.1. Tests are defined in §7.2.

### 7.1 The form

`Type where <condition>` may appear wherever a type is written: a `type` line, a record field, a parameter, a return type, a `let`. The condition is the fragment of §11.1.

`it` is the value being refined. Its fields are written `it.field`, at any depth by dotted path. A bare field name is rejected. `length` follows the same rule: `Array<T> where it.length in 0 to 50`.

Rejected edit: replace `it.status` with bare `status` in a refinement.

A refinement names only the refined value, its fields, and `const` names. A report refers to an unnamed refinement by its path.

```brass
# support/payments.brass — declaration excerpts
type Money    = Int where it in 0 to 100000000
type OpenCase = CaseRecord where it.status in {CaseStatus.Open}
type Deliverer = staff.Staff where it.role in {staff.Role.Keeper}
```

A refinement of a refinement stacks the conditions. A refined value is accepted wherever its base is expected. A base value is not accepted where a refinement is expected. The call is rejected with both types named. An empty refinement, one no value can satisfy, is a rejection.

A refinement establishes that a value satisfies its condition. It does not establish where the value came from. Provenance is the boundary's claim (§8.5) and a machine state's (§9.2).

### 7.2 The test

A value gets a refinement type by passing `x is T`, where `T` is declared with `where`. The test returns a `Bool`. Inside the successful `if` branch, each value tested before `then` counts as its refined type. Tests combine with `and`.

Under `or`, neither side counts as established; under `not`, nothing does. For `Maybe<T>` tests and their complements, see §5.1.

The `else` of a single `in` test on a closed set of machine states, or an `is Ok` or `is Err` test, knows the complement. `Maybe<T>` complements are defined in §5.1. No other test narrows in `else`.

A test gives a value a named refinement only by `x is T`. A value also holds a refinement by its declared type, by the known-value rule below, and across a `with` as §9.3 defines.

A test on a field, `p.status in {…}`, narrows only that field and what depends on it, such as a `when` field. It does not make `p` a `T`, even when the test is `T`'s own condition. A refinement is never established by assertion.

There is no constructor call or validation keyword. A value known to the checker (a literal, a `const` name, or a `with` whose fields it can see) satisfies a refinement when its condition holds on that value. A mismatch is rejected on that line.

```brass
# park/doors.brass — body excerpt
fn lockdown_request(doors, who, p) =
  if who is staff.DoorOperator then lockdown(doors, who, p)
  else Err(FailureCode.Unauthorized, "not a door operator")
```

`x is T` is legal when `x` and `T` have the same field names and corresponding field types have the same underlying type after removing refinements. The test checks every refinement `T` requires, including field refinements.

A refinement established by a test on a name holds until the name is rebound. The rebound value keeps its declared type's refinements and loses what the test established.

### 7.3 `in` and `is`

`in` asks about membership; `is` asks about a type. Narrowing is defined in §7.2. `in` takes a range or a set. `x in lo to hi` tests integer range membership. Range endpoints are inclusive (§3).

`x in {A, B}` is set membership, and a single value is `in {A}`; `x in s` where `s` names a set, an access bound or a `const` set, is membership in that set. For iteration, see §3. For machine-state tests and conditional-field reads, see §9.4.

`is` takes a type or a result arm. `x is T` tests a refinement (§7.2). `x is Ok` and `x is Err` ask which arm an `Outcome` holds. `is` never takes a value: `x is None` is a rejection, and `x == None` is the test (§5.1).

When the left side is a set, `in` is inclusion.

### 7.4 A projection copies a declared set of fields

A source record declares `projects to T1, T2, …` to allow conversion wherever a target type is expected.

```brass
# bank/types.brass — declaration excerpt
type AccountRef = { id: Int }
type Account = { id: Int, balance: Int }
  projects to AccountRef
```

The target copies exactly its declared fields from the source by name and type. The source is unchanged. There is no reverse conversion. A projection is rejected if:

- A target field is missing from the source or has a different type.
- A target condition does not follow from the source's own conditions.
- It projects a machine-typed field.

Each target is declared only on the source type. There is no projection syntax at a use. The compiler never chains projections.

Rejected edit: add `balance: Int` to `AccountRef` after removing that field from `Account`.

## 8. Authority is a parameter and only narrows

A function reaches the outside only through an access it received as a parameter. Authority is created in one file, `system`, and moves only down parameter lists. Foreign computation uses the same `access` boundary (§8.1).

### 8.1 `access` and `allow`

`access Name { bounds }` declares a type whose values come only from a `system` grant. `allow name(params) -> Outcome<T>` beneath it declares an operation available to a holder. The host implements it; it has no body in Brass.

`<access-parameter>.<allow>(args)` is how a body calls one. Every `allow` returns `Outcome<T>`, written in full; there is no total `allow`.

```brass
# support/payments.brass — declaration excerpt
access Pay { processor: Processor, per_txn_max: Money }
  allow refund(case: OpenCase, amount: Money) -> Outcome<Receipt>
    before amount > 0
    before amount <= per_txn_max
    after  result.amount == amount and result.customer == case.customer
```

Rejected: an `allow` declared with a return type other than `Outcome<T>`.

An access value exists in two places: a `system` grant and a function parameter. It is never a record field, a collection element, a return value, or stored. A function's parameter list is its complete authority. No literal, constructor, or return produces an access.

A function cannot capture an access. Without an access parameter, a function is pure over its inputs and constants. The same authority rules apply to libraries.

Text conversion needs no access: the bundled module `std.text` provides `fn of(i: Int) -> Text`, an integer's decimal text, total and pure.

Time is an access: `Clock`, declared in the bundled module `std.time` with `allow now_ms() -> Outcome<Int>`, imported as `time` and granted in `system` like any other.

### 8.2 Bounds

An access's fields are its bounds: argument bounds or reserved bounds.

**An argument bound** applies to an `allow` argument through that operation's own `before`. For example, `before paddock in paddocks` checks membership in the granted set, and `before amount <= per_txn_max` checks the amount against the ceiling.

An argument bound that no `before` names imposes no checked condition. It reports assumed.

**A reserved bound** is enforced by the runtime over the call itself. There are two: `budget_<unit>` and `deadline_ms`. Each is an `Int` field on the access, supplied by the grant.

`deadline_ms` bounds one call in milliseconds. When the deadline passes:

- A call not yet dispatched returns `Err(FailureCode.Unavailable, …)`.
- A dispatched call whose reply misses the deadline returns `Err(FailureCode.Unknown, …)` (§5.1).

A `budget_<unit>` field is a quota. An access may declare at most one. A bare `budget` is a rejection.

Each task (§8.5) gets a fresh counter for each grant. Every draw through that access counts against it. Passing the access on creates no second counter. All counters expire when the task ends.

A call is admitted only while the counter has quota. The host reports consumption, charged in the bound's unit. A call that would exceed the counter is stopped at the remaining quota, where the host can stop it, and returns `Err(FailureCode.ResourceExhausted, …)`.

A call refused before it runs consumes nothing. One stopped after it started keeps the charge for what it consumed.

The counter bounds what the runtime admits and meters. The runtime companion defines how the host meters a call and whether it can stop one mid-way. An effect the host cannot stop is charged what it reports. The counter may end below zero; the next call through that grant is refused.

The budget bounds admission. It bounds consumption only as far as the host can stop a call. Budgets shared between tasks are not defined in v0.3.

### 8.3 Authority checks and contracts on an `allow`

A `before` on an `allow` has two kinds of conjunct, and each is checked differently. An **authority check** is a conjunct that names a bound of the access.

The runtime evaluates it before the call and refuses with `Err(FailureCode.Unauthorized, …)`, before the operation or any side effect; it reports enforced.

It is rejected at check time only when the argument's value is known to the checker, a literal, a `const` name, or a value the checker can show to be one, and violates the bound. Every other conjunct is a **contract**: the caller proves it or the program is rejected (§6).

An `after` on an `allow` is enforced at the boundary. The runtime checks every successful reply. A violation aborts the task and is recorded in the transcript (§10.4). A caller's proof may use the clause as a fact; tier propagation is defined in §6.

### 8.4 Narrowing

An access may be narrowed, never widened.

In v0.3 only a `system` grant narrows an access:

- The grant's values must satisfy the declared type's refinement.
- A set may only be a subset.
- A limit may only be lower.

Grant values are known, so values that do not fit are rejected at check time.

No body expression narrows an access. A body passes the whole access it holds. A function that needs a helper to hold less must receive less from its caller. A refinement on an access type is declared like any refinement (§7) and used in signatures and grants:

```brass
# support/payments.brass — declaration excerpt
type StripePay = payments.Pay where it.processor in {payments.Processor.Stripe} and it.per_txn_max in 0 to 50000
```

An access argument has the parameter's type or a refinement of it; its bounds travel with it, so authority never widens. `x is T` on an access is a rejection.

### 8.5 Grants and entry points

A task is one call of an entry point by the host, from its start until it returns or aborts. A grant names a module-qualified function and fills its access parameters by name: `<param> = <Type> { bounds }`, the braces omitted when the access declares no bounds.

Order carries no meaning. Type names on the right resolve in that function's module, through its own imports.

A grant naming a parameter the function does not declare, an access parameter left without a grant, or a grant whose values do not fit the parameter's type (§8.4) is a rejection.

A grant carries bounds and identifiers, never secrets. The host maps identifiers to credentials it holds outside Brass.

```brass
# system.brass — grant excerpt
system support
  grants support.refund.issue: pay = StripePay { processor: payments.Processor.Stripe, per_txn_max: 50000 }
```

A function is reachable from outside the program exactly when `system` has a `grants` line for it. A function that holds no access is exposed with `grants <module.fn>: none`. The host starts an entry point by its module-qualified name; there is no bare `main`.

Whether a transport serves an entry point is a hosting setting, not a language fact.

**At the boundary**, `brass` generates an adapter from the entry point's declaration. The adapter checks incoming data against the parameter types and evaluates every `before` of the entry point. The function runs only when all checks pass.

Invalid data or a failing clause produces `Err(FailureCode.InvalidInput, …)` without running the function. The check reports enforced.

A parameter may carry a machine-typed field: the adapter checks the value against the parameter type, and the state itself is the host's claim, at the assumed tier, as identity is.

The reply to the host is always `Outcome<T>`: a total entry point's result arrives as `Ok(result)`, and one already returning `Outcome<T>` is forwarded as is.

An exported entry point holds exactly the accesses its `grants` line names, on every call. Per-caller restriction is a contract over identity data supplied by the boundary. No authority is created per request. Identity is an assertion of the adapter, reported assumed.

The checker rejects a call that fails a declared requirement on the protected operation. It does not infer authorization requirements from body code. A refined record does not establish authentication; the host supplies that connection at the assumed tier (§8.5).

## 9. A machine says which states a value may enter

Machine declarations are defined in §9.1. Construction and transitions are defined in §9.2.

### 9.1 The form

A machine declares its states, its initial states (`initial A` or `initial A | B`), and one line per source state naming the targets it may enter. List order carries no meaning. Construction is defined in §9.2.

```brass
# park/feeding.brass — declaration excerpt
machine FeedingStatus
  states  Planned, Delivered, Skipped
  initial Planned
  Planned enters Delivered | Skipped
```

A state is a plain name, never a machine, record, or other type. One machine never references another. A record may hold several machine-typed fields, each transitioning independently. A condition relating them is a refinement on the record.

### 9.2 Transition and construction

`<value> enters <State>` produces a value of the machine type in the target state. Its result type does not depend on proof context. The checker must establish that every possible source state has a declared edge to that target; otherwise the expression is rejected, naming the source states not covered.

Rejected edit: use `enters FeedingStatus.Delivered` when the source may already be `Delivered`; the machine in §9.1 declares no such edge.

`enters` applies to a value of a machine type, usually a record field. An `enters` whose result is discarded is a rejection; the result must be bound, returned, or consumed by another expression.

New machine values start in an allowed initial state. A non-initial value comes only from:

- `enters` on a value already held.
- A granted `allow` whose declared result carries the machine type, at that access's tier.
- An entry point's parameter, checked against its type at the boundary and assumed beyond that (§8.5).

Inventing a non-initial state in a literal is rejected. Placing a legitimately obtained one in a record is permitted. Record construction does not itself authorize a non-initial state. A legitimately obtained state can be placed beside changed data. The machine checks the state graph, not the history of one entity.

### 9.3 `with`

`<record> with { <field>: <value>, … }` produces a new record of the same shape. It replaces the named fields and copies every other field. The braces hold a partial record literal with ordinary record commas.

```brass
# park/feeding.brass — declaration excerpt
fn deliver(f, by) = f with { status enters FeedingStatus.Delivered, delivered_by: by.badge }
```

A machine-field transition uses `<field> enters <State>` (§9.2). This names the record's own field, never a local, and writes the transitioned value back under that name. Writing the transition as an ordinary `<field>: <value>` entry is rejected.

Rejected edit: replace `status enters FeedingStatus.Delivered` with `status: FeedingStatus.Delivered`.

A `with` that does not name the machine field leaves the state as it is; staying in a state needs no edge. A repeated field, an unknown field, or an empty `with { }` is rejected.

A `with` keeps every refinement whose condition names none of the fields it changes; `enters` changes the machine field. Updating a field named by a refinement's condition yields the base type. The checker can establish the refinement again from the new value.

### 9.4 `when`: conditional fields

The form is `<name>: <Type> when it.<machine field> in {State, …}`, on a field inside the record's braces. The condition is a machine-state test on another field of the same record and nothing else; `it` is the record.

The field exists exactly in the listed states: required there, forbidden everywhere else. Each conditional field carries its own `when`; several may test the same field. The field a `when` tests has no `when` of its own.

A conditional field's type is a named type, never an inline refinement, so `it` in a `when` always means the record.

A named type is a declared name, a built-in such as `Text`, or a built-in applied to a name such as `Array<Item>`. An inline refinement such as `Int where it > 0 when …` is rejected. Declare the refinement with `type` first.

`when` determines field presence. Record-wide conditions use `where` (§7.1). For the meaning of `it` in a field refinement, see §7.1.

```brass
# park/feeding.brass — declaration excerpt
type Feeding = { paddock:      ids.PaddockId,
                 species:      ids.Species,
                 heads:        ids.Count,
                 grams:        ids.Grams,
                 day:          ids.Day,
                 status:       FeedingStatus,
                 delivered_by: ids.BadgeId when it.status in {FeedingStatus.Delivered} }
```

**Reading.** A conditional field may be read only where the value is known to be in one of its states, by its declared type or by an enclosing `in` test, in a body or a contract alike. Anywhere else is a rejection naming the field and the state it needs.

**Construction and change.** The presence rule applies to every expression producing a record, including record literals.

Entering the states through `with` requires the field in the same update. A transition within the field's state set keeps the field, and `with` may replace it. Leaving the set drops it; naming it in that update is rejected. Rejected edit: remove `delivered_by` from an update entering `Delivered`.

For equality, see §3.1.

## 10. The system file, lock, transcript, and abort

### 10.1 `system`

`system` is authored and carries no version. Two `system` files in one tree are rejected. A binding line uses `=`.

```brass
# system.brass — excerpt
system park
  requires std = brass.std v0.2
  grants   park.control.deliver_feeding: registry = Registry { paddocks: {1, 2, 3, 4, 5} }
  limit    cpu_ms 5000
  limit    memory_bytes 268435456
  limit    transcript_bytes 2000000000, drop oldest
  limit    impact_modules 12
```

`requires <name> = <provider> <release>` selects one exact published release for a dependency outside the source tree, including the standard library. A release identifier is `v` followed by dotted numbers. Grants are defined in §8.5.

`limit <subject> <bound>` sets a bound and binds nothing. Every subject names its unit. `cpu_ms`, `memory_bytes`, and `transcript_bytes` are required. Omitting any is a rejection.

`limit impact_modules` is an optional review policy. Exceeding it produces a review notice, not a check failure. When omitted, no impact cap applies. The impact count is provisional (§12.2).

| Limit | Checked | When exceeded |
|---|---|---|
| `cpu_ms` | while a task runs | the task aborts (§10.4); effects already made stand |
| `memory_bytes` | while a task runs | the task aborts |
| `transcript_bytes` | while a task runs | the oldest records are dropped (`drop oldest`); nothing aborts |
| `impact_modules` | at check time, on each change | `check` reports that the change exceeds the configured scope |

`limit transcript_bytes <bound>, drop oldest` also names the drop rule. `oldest` is the only rule in v0.3. `drop oldest` in `limit transcript_bytes` and `none` in `grants` are fixed forms. The words `drop`, `oldest` and `none` are not reserved keywords.

Raising a limit is an edit to `system`, hashed into `lock` like any other. It is not proof of human review. A limit governs what the release tolerates. A bound in a grant governs what the program may do.

A system selects one release per provider. Two names bound to one provider must select the same release. Release ranges and automatic upgrades are not defined in v0.3.

### 10.2 `lock`

`brass` generates `lock`. It is not edited by hand. It records the hash of every module and the `system` file, the resolved contents of every selected release, where every import resolved, the checker and runtime identities, and the inventory of functions that can fail.

A `lock` is refused when it is incomplete, when its checker or runtime differs from the one running, or when a module, the `system` file, or a selected release no longer matches what it records.

Authored files never contain hashes. The runtime companion defines the format and mechanics.

### 10.3 The transcript

Every access operation and its outcome is written to a transcript. `limit transcript_bytes` in `system` sets its size bound and drop rule. Diagnostics use the transcript. A record dropped by the limit, or not yet durable when the host fails, is not available to a restart.

Reproducing an execution from the transcript is not a language guarantee. The runtime companion defines whether a runtime can do it.

### 10.4 Abort

A total function returns its declared type or the task aborts. An abort is not a value and cannot be caught or propagated with `?`. It discards local state. The transcript records the cause. Only these conditions abort a task:

- Integer overflow on an unranged value.
- Allocation beyond `limit memory_bytes`.
- A task exceeding `limit cpu_ms`.
- An `allow` reply violating its `after`.
- A run-time failure of a proven `before` or `after`.

Effects performed through an access stand. The language undoes nothing. An `Err` is a value, not a rollback: effects made before it stand as they do before an abort.

## 11. What the checker establishes

### 11.1 The fragment

A `before`, an `after`, and a `where` (§7) use the same set of expressions, called the fragment. It permits:

- Integer addition and subtraction.
- Multiplication by a constant.
- Multiplication of two variables when the checker can bound their product from their types.
- Division and remainder by a nonzero constant.
- Equality, ordering (`<`, `<=`, `>`, `>=`), set membership, and range membership, including `== None` and `!= None` on a `Maybe`.
- Conditions joined with `and` and `or`, and negated with `not`.

Expressions may name parameters, `result`, their fields by dotted path, the bounds of an access parameter, `const` names, and `length` as a path (`xs.length`; in a `where`, `it.length`). Quantifiers, calls, and floats are not allowed. `any` and `all` (§3) are body forms only.

Every intermediate must be shown to fit `Int`, or the clause is not proven. Grouping follows §2.2. What the left operand of `and` establishes holds while checking its right operand.

```brass
# support/refund.brass — contract excerpt
before status in {CaseStatus.Open} and (amount <= cap or override in {Override.Granted})
```

### 11.2 What a successful check establishes

A successful check establishes types (§2), authority restrictions (§8), legal transitions (§9), and the following properties:

1. **Contracts.** For inputs satisfying the declared types and `before`, every normal return satisfies `after`.
2. **Termination.** Every loop is bounded (§3). Termination proved by the checker is over Brass computation. It does not establish that a host operation replies; deadlines and runtime limits stop an execution that a proof cannot.
3. **Aborts.** Every integer operation that may overflow is marked (§2.1); a float does not abort. Every other condition that aborts a task is on the closed list in §10.4, and each is a runtime fact.
4. **No guarantee of success.** A fallible body that always returns `Err` may pass. Checking does not establish that any execution reaches `Ok`, or that any execution completes without aborting.

**Contract limits.** Contracts do not specify what a body does between entry and successful return (§6).

| Layer | Mechanism | Covers |
|---|---|---|
| values in and out | `before`, `after` | input validity, result correctness |
| who and what, per operation | the `allow`'s own parameter types and contracts | which customer, which case |
| how much, in total | the grant's bounds | the ceiling |
| how many times, in what order | nothing in v0.3 | body code; a reader or a test |

A body may be replaced while retaining its interface. Replacement preserves the checked obligations and examples, not equivalent behavior. Two bodies may differ in success, failure frequency, or permitted effects. Effect order and count require body inspection or tests.

For excluded constructs, see §15.

### 11.3 Proofs across modules

A proof across modules uses the imported declaration and its contracts: the semantic surface (§12.1). It never reads the imported body. A conforming checker must produce the specified acceptance or rejection for these required cases:

- A bounded sum with a refined result.
- A branch excluding a zero divisor.
- A helper call proved through its contract.
- Invalid `allow` arguments rejected before any effect.
- The filter shape (§3).

`design/brass-checker-design.md` carries the full table. Changes to the required cases are recorded with their reasons.

Every proven obligation is decided offline within bounded time. A correct program the checker cannot prove reports **not proven**, never **wrong**. A clause not decided within the proof bound is rejected as not proven in time. The bound is a `brass` setting.

## 12. `brass` reports

`brass` answers a structured query: a verb, a named thing, and flags. Its response identifies the program state recorded in `lock` (§10.2). Natural-language questions are outside this specification.

The answer is a pure function of the query, the current source tree, the checker build, and any checker configuration that can affect it. `lock` supplies the recorded facts. Bodies are read only when needed, such as for the body-references line below.

A report shows facts and never advises. The checker rejects programs; it never transforms or reinterprets authored code. An error says what is wrong and what to change. A *repair* is an edit made in answer to a rejection.

### 12.1 Semantic surface

A module's semantic surface is the transitive set of interface declarations (functions, types, machines, accesses, constants) reachable from its interface and imports. The checker computes this surface and checks the module against it. Reports read from it.

### 12.2 Impact set

The impact set is defined for a change to a declaration: every interface whose semantic surface contains it, every machine and access bound that references it, every `const` depending on it, and every module needing re-check. `brass info` reports it before an edit.

The count is provisional. The baseline, treatment of body-only edits, and meaning of ‘needing re-check’ are not defined in v0.3. For the optional review policy, see §10.1.

### 12.3 Report fields

- **Tiers:** every promise prints its own tier, and a declaration's line prints the weakest among its promises. A legend explains each word once per report; it does not assign tiers. For `example` results, see §6.1.
- **Query ids:** checkable citations, not retrieval keys. Nothing is stored. `brass` recomputes the report from the current tree and compares it with the citation. `check` refuses a repair whose cited reports no longer match.
- **Hashes:** twelve characters for display, the full hash for identity and `lock`. An ambiguous prefix is rejected with a request for a longer one.
- **The `end` line:** detects a cut-off report and nothing more.

```
# brass-info.txt — illustrative output
info feeding.deliver  q:9b31e0c72a54
  fn deliver(f: PendingFeeding, by: Deliverer) -> DeliveredFeeding      proven
    after result.paddock == f.paddock and result.grams == f.grams and result.delivered_by == by.badge
  used_by   control.deliver_as
  body      1 line   references: feeding.FeedingStatus
end q:9b31e0c72a54
```

For holes and their diagnostics, see §3.2. `design/brass-report-design.md` defines formats, flags, and error lines. The diagnostics here and in `examples/` illustrate the information, not final wording.

## 13. Conformance index

The eight rule identifiers name the requirements defined in the cited sections.

| Rule | Definition |
|---|---|
| **R1 Checkable** | §0, §6, §8.3, §11.3 |
| **R2 Surface** (interface contents) | §4 |
| **R3 One form** | §2, §5.1, §7.1, §7.4, §15 |
| **R4 Authority on the surface** | §8.1–§8.5 |
| **R5 Bounded, and fail closed** | §3, §8.2, §10.1, §10.2, §11.3, §15 |
| **R6 Provenance, written by machines** | §10.2 |
| **R7 Interfaces stable, bodies replaceable** | §4, §11.2 |
| **R8 Reject, don't rewrite** | §12 |

## 14. Terms

| Term | Definition |
|---|---|
| proven, enforced, assumed | §0 |
| Total function and abort | §10.4 |
| Budget | §8.2 |
| Transition | §9.2 |
| Task | §8.5 |
| Semantic surface | §12.1 |
| Impact set | §12.2 |

## 15. Excluded constructs

Refused constructs do not return without an amendment here. This section is the normative ledger of exclusions. Amendments follow the entry procedure in the private change record; dates, decisions, and reasons are recorded there.

The following constructs are excluded:

- Macros, reflection, overloading, user-defined syntax, stylistic alternatives, and hidden inference.
- Subtyping and implicit conversions other than the refinement conversion (§7.1), `T` to `Maybe<T>` (§5.1), and declared record projection (§7.4).
- Dynamic loading and open-world name resolution.
- Prose with language semantics, natural-language programming, and AI-specific control structures.
- Destructors and autonomous or implicit repair.
- An effect system, runtime compensation, and tolerance mechanisms for failed obligations.
- Visibility modifiers or an export list (§4).
- A separate marker on access parameters (§8.1).
- Optional fields or sum payloads as an alternative to state-dependent fields (§9.4).

Other exclusions are stated with their rules: collections and function values (§2), loops and early return (§3), identity and finalizers (§3.1), access storage (§8.1), and machine composition (§9.1).

Deferred designs and their reconsideration conditions are in the private considerations file. Decisions and historical forms are recorded in the private change record.

## 16. Open definitions

Unresolved definitions are listed in the private considerations file.

**Freeze criterion.** Validate the design on five systems: a payment workflow, a network service, a data pipeline, a multi-actor system, and a stateful simulation. Each is written by a model in Brass as specified, from the notation alone. Each produces an inventory of requirements it could not express and workarounds it needed.

The five inventories are the criterion for lifting the design freeze. A requirement that existing primitives cannot express is evidence for a new construct.
