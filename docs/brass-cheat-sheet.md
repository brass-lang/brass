# Brass cheat sheet

Use this sheet to look up Brass syntax through short examples from a dinosaur park. Each section links to the rule in the [specification](brass-core-spec.md), which decides what is valid.

The rejection notes describe language rules, including checks still to be implemented. Today's `brass` tool checks program structure, runs examples and answers questions about the code. Proving function contracts requires the full checker.

## The smallest program

A module declares and implements a greeting. The system file makes it callable by the host.

```brass
# hello/greet.brass
module hello.greet

interface
  fn greet(name: Text) -> Text
    example greet("Ada") == "Hello, Ada"

body
  fn greet(name) = "Hello, " ++ name
```

```brass
# system.brass
system hello
  grants hello.greet.greet: none
  limit  cpu_ms 1000
  limit  memory_bytes 16777216
  limit  transcript_bytes 1048576, drop oldest
```

A program is its modules plus one `system.brass`. The host calls an entry point by its full name, `hello.greet.greet`; there is no `main`. Only a function with a `grants` line can be called from outside. There is no `print`: output goes through an access ([Authority](#authority-access-allow-grants)).

## Comments

```brass
# park/ids.brass — declaration excerpt
# a comment runs from # to the end of the line
type PaddockId = Int where it in 1 to 40   # at the end of a line, too
```

A comment directly above a declaration is shown by `brass info`.

## Modules and imports

```brass
# park/doors.brass — layout
module park.doors
import park.enclosures as enclosures

interface
  …
private
  …
body
  …
```

- **One module, one file.** `interface` and `body` are always written; `private` is optional.
- **Placement is visibility.** `interface` is what other modules see. `private` is for this file only. There are no visibility modifiers and no export list.
- **Every import has an alias**, and imported names are always written through it: `enclosures.Paddock`, never `Paddock`.
- **`body` holds implementations only.** Every function is declared in `interface` or `private`.

[Spec §4](brass-core-spec.md#4-modules-and-imports)

## Names

| What | Case | Example |
|---|---|---|
| types, constructors, states | Uppercase | `Paddock`, `Species.Rex` |
| modules, functions, parameters, fields, aliases | lowercase | `park.doors`, `secure`, `p.id` |

Constructors are qualified by their type: `Species.Rex`, `FailureCode.NotFound`. `Ok`, `Err`, `Done` and `None` stay bare. A keyword is never a name.

## Built-in types

| Type | Meaning |
|---|---|
| `Int` | signed 64-bit integer; also `Int8 Int16 Int32 Int64` |
| `Float` | 64-bit IEEE float |
| `Bool` | `true` or `false` |
| `Text` | text; `length` counts characters |
| `Bytes` | a byte sequence |
| `Array<T>` | ordered; literals `[]`, `[a, b]` |
| `Set<T>` | for membership and bounds; literal `{a, b}`; not iterable |
| `Maybe<T>` | a `T` or `None` |
| `Outcome<T>` | `Ok(T)` or `Err(FailureCode, Text)` |
| `Done` | the one value of a call with nothing to return: `Outcome<Done>` |

No `Map`, no function values, no null. [Spec §2](brass-core-spec.md#2-types-values-and-names)

## Bindings and constants

Use `const` for a value known to the checker and `let` for a local binding.

```brass
# park/enclosures.brass — excerpts
interface
  const max_heads: Int = 12

body
  fn total(…) =
    let count: Int = 0        # every let names its type
    count = count + 1         # rebinding: same type, local lets only
    count
```

- **Values never change.** Rebinding points the name at a new value.
- **Rejected:** an untyped `let`, an unused `let`, rebinding a parameter.
- **Literals take their type from where they stand.** `0` is an `Int` in an `Int` position and a `Float` in a `Float` one. `1.5` in an integer position is rejected.

## Operators

| Kind | Operators |
|---|---|
| arithmetic | `+ - * / %`, `-x` |
| powers | `a ^ b`, constants only |
| join text or arrays | `++` |
| compare | `== != < <= > >=` |
| logic | `and or not` |
| membership, type test | `in`, `is` |
| pass up a failure | `?` |

- **`+` never joins text.** `"a" ++ "b"`.
- **`Int` and `Float` never mix** in one operation.
- **Overflow never wraps.** On an integer without a range, it aborts the task.
- **Integer `/` and `%` need a divisor the checker can prove nonzero.** `/` truncates toward zero.
- **Rejected:** `a < b < c`. Write `a < b and b < c`.
- **Rejected:** `a and b or c`. Write `(a and b) or c`.

Full precedence table: [spec §2.2](brass-core-spec.md#22-operator-precedence-and-grouping)

## Text

```brass
# park/signs.brass — body excerpt; needs `import std.text as text`
fn sign(p) =
  let label: Text = "Paddock " ++ text.of(p.id)
  if label.length <= 20 then label else "Paddock"
```

`text.of` turns an `Int` into its decimal text. Using `std` needs `requires std = brass.std v0.2` in `system.brass`.

## Records and sums

```brass
# park/enclosures.brass — excerpts
type Species = Goat | Raptor | Rex                     # a sum: bare names, no payloads
type Paddock = { id: PaddockId, species: Species, status: Enclosure }

let p: Paddock = { id: 2, species: Species.Rex, status: Enclosure.Secured }
let q: Paddock = p with { species: Species.Raptor }   # a copy; p is unchanged
```

- **`with` copies a record** and replaces only the fields named.
- **Equality is structural.** Two records with equal fields are equal.
- **Sums carry no data.** `Ok` and `Err` are the only arms that do.

## If and else

```brass
# park/enclosures.brass — body excerpt
fn ration(species) =
  if species in {Species.Goat} then 2000
  else if species in {Species.Raptor} then 12000
  else 50000
```

- **`if` is an expression.** Used as a value, it needs an `else`.
- **Blocks are indented.** A block's last line is its value.
- There is no `match`; test with `in` and `is`.

## Loops

```brass
# park/doors.brass — body excerpt
for attempt in 1 to 3                 # both ends included: 1, 2, 3
  last = doors.close(operator, p.id)
  if last is Ok then break

for p in paddocks                     # paddocks: Array<Paddock> where it.length in 0 to 40
  …
```

```brass
# park/enclosures.brass — body excerpt
any p in ps where p is OpenPaddock and p.species in {Species.Rex}
all p in ps where p.status in {Enclosure.Secured}
```

- **Every loop is bounded.** `for` walks a range or an array whose type caps its `length`.
- **No `while`, no recursion.**
- **`break`** leaves the nearest loop and carries no value.
- **`any` and `all`** return a `Bool`. Over an empty array, `any` is false and `all` is true.

[Spec §3](brass-core-spec.md#3-functions-and-bodies)

## Functions

```brass
# park/enclosures.brass
module park.enclosures

interface
  fn ration(species: Species) -> Grams    # declaration: types and promises

body
  fn ration(species) =                    # body: parameter names only
    if species in {Species.Goat} then 2000
    else 50000
```

- **No `return`.** The last line is the result.
- **A call whose result is discarded** must yield `Done`, after `?` if there is one. Discarding any other value is rejected.
- **A long declaration** may continue while a `(`, `<` or `{` is open.
- **No overloads and no function values.**

## Promises: `before`, `after`, `example`

A function can state a general condition, or give one concrete call and the answer it must give.

```brass
# park/enclosures.brass — declaration excerpt
fn secure(p: OpenPaddock) -> SecuredPaddock
  after result.id == p.id

fn ration(species: Species) -> Grams
  example ration(Species.Goat) == 2000
```

| Line | Who makes it true | Checked |
|---|---|---|
| `before` | the caller | proven at check time |
| `after` | the body, on success | proven at check time |
| `example` | the body | run by `brass check` |

- **A function's `before` and `after` are proved, or the program is rejected.** An access operation's authority checks and reply promises are enforced when the program runs instead. The runtime checks proved clauses again as the code runs; a clause proved from an enforced fact, such as an `allow`'s `after`, reports **enforced** (spec §6).
- **Promises are optional.** A function without them is still checked for types, loops, authority and states.
- **Conditions use a small set of operations:** integer `+ -` (and `* / %` in limited cases), comparisons, `in`, `and or not`. No calls, floats, `any` or `all`.
- **`example`** only on a function that returns no `Outcome` and takes no access.

[Spec §6](brass-core-spec.md#6-contracts-are-proved-or-the-program-is-rejected)

## Types with conditions: `where` and `is`

```brass
# park/enclosures.brass — declaration excerpts
type PaddockId   = Int where it in 1 to 40
type OpenPaddock = Paddock where it.status in {Enclosure.Open}
type Pen         = Array<Paddock> where it.length in 0 to 40
```

```brass
# park/doors.brass — body excerpt
if p is enclosures.OpenPaddock then
  Ok(enclosures.secure(p))             # p counts as an OpenPaddock here
else Err(FailureCode.Conflict, "paddock is not open")
```

- **`it`** is the value being described; its fields are `it.field`.
- **`x is T`** is the only test that gives a value a named type. There are no casts.
- **`in`** tests membership: `x in 1 to 40`, `x in {A, B}`.
- **A field test narrows the field only.** `p.status in {Enclosure.Open}` does not make `p` an `OpenPaddock`.

[Spec §7](brass-core-spec.md#7-a-refinement-is-a-named-condition)

## Errors: `Outcome` and `?`

```brass
# park/doors.brass — body excerpt
fn lockdown_as(doors, operator, paddock) =
  let p: enclosures.Paddock = doors.enclosure(paddock)?   # the Ok value, or return the Err
  if p is enclosures.OpenPaddock then
    doors.close(operator, p.id)?
    Ok(enclosures.secure(p))
  else Err(FailureCode.Conflict, "paddock is not open")
```

- **A function that can fail says so:** `-> Outcome<T>`. No exceptions, no `try`.
- **`?`** passes an `Err` up. It works only inside a function that returns `Outcome`.
- **Test without passing up:** `if r is Ok then …`, `if r is Err then …`.
- **Failure codes:** `Unauthorized InvalidInput Conflict Unavailable ResourceExhausted Other Unknown NotFound`.
- **Nothing is undone.** If the door closed and a later step fails, it stays closed.
- **Some failures abort the task** and can't be caught: overflow on an unranged integer, running out of memory or CPU time, a host reply breaking its `after`, a proven promise failing at run time.

[Spec §5](brass-core-spec.md#5-failure), [§10.4](brass-core-spec.md#104-abort)

## Absence: `Maybe`

```brass
# park/enclosures.brass — excerpt
fn signers(first: BadgeId, second: Maybe<BadgeId>) -> Int
fn signers(first, second) =
  if second != None and second != first then 2 else 1   # right of and: a plain BadgeId
```

- **Only a `Maybe<T>` can be absent.**
- **`x != None`** makes `x` a plain `T` where it holds. `x is None` is rejected.
- No unwrap operator and no default value.

## State machines

```brass
# park/enclosures.brass — excerpts
machine Enclosure
  states  Secured, Open, Breached
  initial Secured
  Secured enters Open
  Open    enters Secured | Breached

fn secure(p) = p with { status enters Enclosure.Secured }
```

- **`enters`** is the only way to change a state, and only along a declared move. Every state the value might be in needs a move to the target.
- **New values start in an `initial` state.** A literal can't invent a later one.
- **Rejected:** `p with { status: Enclosure.Secured }`. Use `enters`.

```brass
# park/enclosures.brass — a variant of Paddock
type Paddock = { id:          PaddockId,
                 status:      Enclosure,
                 breached_at: Int when it.status in {Enclosure.Breached} }
```

- **`when`** makes a field exist only in the states listed: required there, absent elsewhere. Its type is a named type.

[Spec §9](brass-core-spec.md#9-a-machine-says-which-states-a-value-may-enter)

## Authority: `access`, `allow`, `grants`

```brass
# park/doors.brass — declaration excerpt
access Doors { paddocks: Set<enclosures.PaddockId>, deadline_ms: Int }
  allow close(operator: enclosures.DoorOperator, paddock: enclosures.PaddockId) -> Outcome<Done>
    before paddock in paddocks

fn lockdown_as(doors: Doors, operator: enclosures.DoorOperator, paddock: enclosures.PaddockId) -> Outcome<enclosures.SecuredPaddock>
```

```brass
# system.brass — grant excerpt
grants park.doors.lockdown_request: doors = Doors { paddocks: {1, 2, 3}, deadline_ms: 30000 }
```

- **A function reaches outside only through an access parameter.** No parameter, no effect. No global connections.
- **`allow`** declares one operation the host implements. It always returns `Outcome`.
- **Call it** as `doors.close(operator, p.id)`.
- **Accesses are created only by `grants`** in `system.brass`. They can't be stored, returned or put in a record.
- **A `before` that names a bound,** like `paddock in paddocks`, is checked by the runtime on every call.

[Spec §8](brass-core-spec.md#8-authority-is-a-parameter-and-only-narrows)

## The system file

```brass
# system.brass
system park
  requires std = brass.std v0.2
  grants   park.doors.lockdown_request: doors = Doors { paddocks: {1, 2, 3}, deadline_ms: 30000 }
  limit    cpu_ms 5000
  limit    memory_bytes 268435456
  limit    transcript_bytes 67108864, drop oldest
  limit    impact_modules 4
```

| Line | Meaning |
|---|---|
| `requires` | an exact release of an outside dependency |
| `grants` | an entry point and the access it gets; `: none` if it needs none |
| `limit cpu_ms`, `memory_bytes`, `transcript_bytes` | required; the first two abort the task when exceeded |
| `limit impact_modules` | optional review notice when a change reaches too many modules |

`brass` writes a `lock` file beside the system file. Nobody edits it by hand.

## Holes

```brass
# park/doors.brass — body excerpt
doors.close(@@operator, p.id)?
```

`@@name` marks an expression not written yet. The program is rejected until it's filled; `brass check` names the type that fits.

## What `brass` reports

| Command | What it does |
|---|---|
| `brass check` | checks the whole program and runs every `example` |
| `brass info <name>` | one declaration: its promises, their labels, who uses it |
| `brass show <module> …` | the declarations of the modules named, exactly as written |
| `brass apply` | applies a patch, checking it before anything is written |

Every promise is labeled:

- **proven:** the checker proved it before the program runs.
- **enforced:** the runtime checks it on every call.
- **assumed:** nothing checks it.

## Not in Brass

| Instead of | Brass has |
|---|---|
| classes and inheritance | records and `projects to` |
| exceptions | `Outcome<T>` and `?` |
| null | `Maybe<T>` |
| `return` | the last line |
| `while`, recursion | bounded `for` |
| `match` | `if` with `is` and `in` |
| mutation | `with` |
| casts | `x is T` |
| global services | access parameters |
| `pub` / `private` per item | `interface` and `private` sections |
| `"a" + "b"` | `"a" ++ "b"` |
| overloading, macros | one form for each thing |

[Spec §15](brass-core-spec.md#15-excluded-constructs)

## Coming from Python

- **Every `let` and parameter has a type.** Nothing is inferred from use.
- **Indentation marks blocks,** as in Python, but there is no `:` at the end of a line.
- **`if` is an expression** and the last line is the result. No `return`.
- **`for` only.** It walks a range, `1 to 3` (both ends included), or an array with a capped length.
- **No `None` by default.** Only a `Maybe<T>` may be absent.
- **No exceptions.** A function that can fail returns `Outcome<T>`.
- **No `print`, `open` or `requests`.** Anything outside comes in as an access parameter.

## Coming from Rust

- **`Outcome<T>` is like `Result`**, and `?` works much the same. But `Err` always holds a fixed `FailureCode` and a message.
- **`Maybe<T>` is like `Option`**, without `unwrap` or `match`. Test with `!= None`.
- **No borrowing or mutation.** Values are immutable; `with` makes an updated copy.
- **Enums carry no data**, except `Ok` and `Err`.
- **Overflow never wraps**, in any build. On an integer without a range, it aborts the task.
- **No traits, closures or function values.** Behavior is a plain function.
