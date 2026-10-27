# Brass Core Grammar v0.3

Use this file to look up syntax, operators and keywords. The [specification](brass-core-spec.md) defines the rules and takes precedence if the two disagree. Its examples are reproduced here for lookup. Ellipses mark omitted source; excerpts are not complete modules.

## 1. Module layout

The module layout below is defined in [spec §4](brass-core-spec.md#4-modules-and-imports), along with name resolution.

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

## 2. Types and refinements

Aliases, sums, and records: [spec §2](brass-core-spec.md#2-types-values-and-names). Refinements: [spec §7.1](brass-core-spec.md#71-the-form). Projection: [spec §7.4](brass-core-spec.md#74-a-projection-copies-a-declared-set-of-fields).

```brass
# support/types.brass — declaration excerpts
type PaymentId = Text
type Processor = Stripe | Adyen
type Receipt = { amount: Int, customer: Int }
```

```brass
# support/payments.brass — declaration excerpts
type Money    = Int where it in 0 to 100000000
type OpenCase = CaseRecord where it.status in {CaseStatus.Open}
type Deliverer = staff.Staff where it.role in {staff.Role.Keeper}
```

```brass
# bank/types.brass — declaration excerpt
type AccountRef = { id: Int }
type Account = { id: Int, balance: Int }
  projects to AccountRef
```

Base types: `Int8 Int16 Int32 Int64 Int Float Bool Text Bytes Array<T> Set<T> Outcome<T> Done Maybe<T>`. Literal typing, names, and constructor qualification: spec §2.

## 3. Functions, contracts, and examples

Function syntax: [spec §3](brass-core-spec.md#3-functions-and-bodies). Contract declarations: [spec §6](brass-core-spec.md#6-contracts-are-proved-or-the-program-is-rejected). Checked examples: [spec §6.1](brass-core-spec.md#61-checked-examples).

```brass
# support/refund.brass — declaration excerpt
fn issue(pay: StripePay, who: Merchant, case: payments.OpenCase, amount: payments.Money) -> Outcome<payments.Receipt>
  before amount > 0
  before case.merchant == who.id
  before amount <= who.refund_limit
  before amount <= case.paid_total
  after  result.amount == amount
```

```brass
# fizz/fizz.brass
fn fizz(i: Int where it in 1 to 100) -> Text
  example fizz(15) == "FizzBuzz"
  example fizz(9) == "Fizz"
  example fizz(7) == "7"
```

Declaration continuation: spec §2. The body form is `fn name(params) = …`; its parameters have names only.

## 4. Failure and absence

`Outcome<T>`, `Ok`, `Err(code, text)`, `Done`, and propagation with `?`: [spec §5.1](brass-core-spec.md#51-outcome).

```brass
# park/control.brass — propagation excerpt
fn deliver_as(registry, by, paddock) =
  let f: feeding.PendingFeeding = registry.pending(paddock)?
  let done: feeding.DeliveredFeeding = feeding.deliver(f, by)
  registry.save(done)?
  Ok(done)
```

`Maybe<T>`, `None`, and absence tests: spec §5.1.

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

## 5. Machines, updates, and conditional fields

This machine declares three states and two transitions. See [spec §9](brass-core-spec.md#9-a-machine-says-which-states-a-value-may-enter) for the rules.

```brass
# park/feeding.brass — declaration excerpt
machine FeedingStatus
  states  Planned, Delivered, Skipped
  initial Planned
  Planned enters Delivered | Skipped
```

The body below updates a record. See [spec §9.3](brass-core-spec.md#93-with).

```brass
# park/feeding.brass — declaration excerpt
fn deliver(f, by) = f with { status enters FeedingStatus.Delivered, delivered_by: by.badge }
```

The record below makes `delivered_by` conditional on its state. See [spec §9.4](brass-core-spec.md#94-when-conditional-fields).

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

## 6. Access declarations

Accesses and operations: [spec §8.1](brass-core-spec.md#81-access-and-allow). Bounds: spec §8.2. Authority checks and contracts: spec §8.3.

```brass
# support/payments.brass — declaration excerpt
access Pay { processor: Processor, per_txn_max: Money }
  allow refund(case: OpenCase, amount: Money) -> Outcome<Receipt>
    before amount > 0
    before amount <= per_txn_max
    after  result.amount == amount and result.customer == case.customer
```

Call form: `<access-parameter>.<operation>(args)`. The propagation excerpt in §4 shows calls through a registry.

## 7. Constants

A constant declaration names a fixed value. See [spec §2](brass-core-spec.md#2-types-values-and-names).

```brass
# bank/types.brass — constant excerpt
const max_balance: Int = 100000000000
```

## 8. Body forms

Bindings, rebinding, bounded loops, `break`, and the final expression: [spec §3](brass-core-spec.md#3-functions-and-bodies).

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

Branch blocks: spec §3.

```brass
# bank/control.brass — branch excerpt
if raw.amount > src.balance then Err(FailureCode.Conflict, "insufficient funds")
else
  let done: transfers.Transfer = transfers.transfer(src, dst, raw.amount)
  banking.write(done.from_acc)?
  Ok(Done)
```

`any` and `all`: spec §3.

```brass
# park/health.brass — body excerpts
fn any_feverish(animals) = any a in animals where a is Feverish
fn all_fever_free(animals) = all a in animals where not (a is Feverish)
```

Membership uses `x in lo to hi`, `x in {A, B}`, or `x in set`; type and result-arm tests use `x is Type`, `x is Ok`, or `x is Err`. Rules: spec §7.2–§7.3. Array filtering is shown once in spec §3.

Unfinished expressions: [spec §3.2](brass-core-spec.md#32-a-hole-marks-an-unfinished-expression).

```brass
# park/control.brass — rejected incomplete expression
registry.save_feeding(feeding.deliver(f, @@deliverer))?
```

## 9. Operators

Precedence lookup, tightest first, reproduced from [spec §2.2](brass-core-spec.md#22-operator-precedence-and-grouping). That section also defines grouping and the placement of `with`, `enters`, `to`, and `->`. Arithmetic semantics: spec §2.1. The contract fragment: spec §11.1.

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

## 10. System forms

Dependencies and limits: [spec §10.1](brass-core-spec.md#101-system). Grants: [spec §8.5](brass-core-spec.md#85-grants-and-entry-points).

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

An entry point with no access uses `grants <module.fn>: none`; see spec §8.5.

## 11. `lock`

`lock` is generated by the tool. Its contents and validation are defined in [spec §10.2](brass-core-spec.md#102-lock).

## 12. Reports and diagnostics

Query semantics and the report example: [spec §12](brass-core-spec.md#12-brass-reports). Detailed formats: [report design](design/brass-report-design.md).

## 13. Reserved words

Keyword lookup, reproduced from [spec §2.3](brass-core-spec.md#23-reserved-words). That section defines reservation scope and the distinction between keywords, built-ins, and tokens.

- Language (29): `module import as interface private body type where it in is to and or not when with projects fn before after example access allow machine states initial enters const`.
- Body (8): `let if then else for break any all`.
- System file (4): `system requires grants limit`.

Built-ins: `Ok Err Done None result length`. Tokens: `? @@ -> = #`. The fixed forms `none` and `drop oldest` are defined in spec §10.1.

## 14. Excluded forms

Current exclusions: [spec §15](brass-core-spec.md#15-excluded-constructs). Deferred designs are kept in the private considerations file.
