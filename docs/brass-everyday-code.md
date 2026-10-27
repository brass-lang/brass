These six programs are reviewed by hand, not verified by a checker. Unsettled rules are noted beside the examples that need them.

This file is not a spec. When a change to the language affects a form used here, update the program and read it again.

# Brass — everyday code

**These are warm-ups.** Six programs every language gets asked to write: an area, FizzBuzz, Fibonacci, a bank transfer, a filter, a retry. Small on purpose: this is the code a model writes all day, and it should read well in Brass too.

**What Brass is for:** code where a wrong edit costs money or trust. A refund must name the right customer. A door needs an operator. A feeding has a signer only when delivered. `examples/` shows those three programs whole.

Their declarations carry authority, state, and promises for a reviewer to inspect. **The bet:** a checker can reject edits that break those declarations. It cannot catch mistakes the declarations do not describe.

This file asks the smaller question: **does the ordinary code around them read well?** The model writes the payout and the FizzBuzz. A reviewer has to read both.

Each program says what is distinctive about it and where the language is limited or leans on something unsettled. The verdicts are the author's.

| # | Program | Verdict |
|---|---|---|
| 1 | Calculate area | clean |
| 2 | FizzBuzz | readable; no contract for the FizzBuzz rule |
| 3 | Fibonacci | bounded loop; the last iteration can overflow |
| 4 | Bank transfer | clean; the one to show someone |
| 5 | Filter an array | clean since v0.2; the loop is longer than it should be |
| 6 | Retry a stuck gate | clean, with one awkward line |

---

## 1. Calculate area

Begin with a rectangle. The calculation is familiar; the question is how to keep a later edit from changing it. `calculate_area` declares the formula as its promise, with integer widths chosen so the product fits.

```brass
# geometry/area.brass
module geometry.area

interface
  type Measure = Int32

  fn calculate_area(width: Measure, height: Measure) -> Int
    before width >= 0 and height >= 0
    after  result == width * height

body
  fn calculate_area(width, height) = width * height
```

Changing the body to `width + height` would break the promise and be rejected before running. The integer widths also matter: two `Int32` values multiplied fit an `Int`. That lets the checker accept the contract's product while the body computes it at 64 bits.

Nothing here reaches outside. To see why Brass makes authority explicit, add an operation as ordinary as printing.

---

## 2. FizzBuzz

Now give a function something to print. FizzBuzz separates naturally into choosing a label and writing it to the console. In Brass, that familiar split also shows which function has permission to reach outside.

```brass
# fizzbuzz/main.brass
module fizzbuzz
import std.console as console
import std.text as text

interface
  type Round = Int where it in 1 to 100

  fn label(i: Round) -> Text

  fn main(out: console.Console) -> Outcome<Done>

body
  fn label(i) =
    if i % 15 == 0 then "FizzBuzz"
    else if i % 3 == 0 then "Fizz"
    else if i % 5 == 0 then "Buzz"
    else text.of(i)

  fn main(out) =
    for i in 1 to 100
      out.write(label(i))?
    Ok(Done)
```

The functions describe what they need. The system file supplies the console to `main` and sets the program's limits:

```brass
# system.brass
system fizzbuzz
  requires std = brass.std v0.2
  grants   fizzbuzz.main: out = console.Console
  limit    cpu_ms 1000
  limit    memory_bytes 16777216
  limit    transcript_bytes 1048576, drop oldest
  limit    impact_modules 2
```

A reviewer can see the separation in the signatures. `label` has no access parameter and cannot reach outside; `main` receives a console from `system.brass`.

The divisors here are nonzero constants. The checker can establish that the remainder operations are safe.

**Where it is limited.** `label` declares a text result but no FizzBuzz contract. The direct "if divisible by … then …" contract needs implication. That form remains open.

`text.of` comes from `std.text`. The loop range establishes that `i` stays in `1 to 100` (spec §3).

---

## 3. Fibonacci

Fibonacci needs to carry two values from one iteration to the next. With recursion unavailable, an ordinary loop does that work. A bounded loop can still overflow before it returns.

```brass
# fib/main.brass
module fib

interface
  type Index = Int where it in 0 to 92               # fib(93) does not fit an Int

  fn fib(n: Index) -> Int

body
  fn fib(n) =
    let a: Int = 0
    let b: Int = 1
    for i in 1 to n
      let next: Int = a + b
      a = b
      b = next
    a
```

`Index` stops at 92 because `fib(93)` does not fit 64 bits. The parameter type rejects a call with 100, and the range bounds the loop. Neither fact accounts for the extra value the body computes along the way.

The report marks `a + b` as "may abort on overflow". At `n = 92`, the final iteration computes `fib(93)` for `b` before returning `a`. It would abort, even though the intended result fits.

There is no `after`. Even `result >= 0` is outside the loop shapes a checker must prove. A checker unable to prove it would reject the clause as not proven.

The recurrence `fib(n) = fib(n-1) + fib(n-2)` cannot be stated as a contract: v0.3 permits neither recursion nor calls in contracts.

---

## 4. Bank transfer

Moving money brings the earlier pieces together. First calculate the new balances and state what must hold before and after that calculation. Then put the reads and writes in a separate function. The arithmetic can be proved; storing both balances is another problem.

```brass
# bank/transfer.brass
module bank.transfer

interface
  const max_balance: Int = 100000000000                # one billion dollars in cents
  type Cents     = Int where it in 0 to max_balance
  type AccountId = Int where it in 1 to 999999999
  type Account   = { id: AccountId, balance: Cents }

  type RawRequest = { from_acc: Int, to_acc: Int, amount: Int }
  type Request    = { from_acc: AccountId, to_acc: AccountId, amount: Cents }
    where it.from_acc != it.to_acc and it.amount > 0

  type Transfer = { from_acc: Account, to_acc: Account }

  fn transfer(from_acc: Account, to_acc: Account, amount: Cents) -> Transfer
    before from_acc.id != to_acc.id
    before amount <= from_acc.balance
    before to_acc.balance + amount <= max_balance
    after  result.from_acc.id == from_acc.id and result.to_acc.id == to_acc.id
    after  result.from_acc.balance == from_acc.balance - amount
    after  result.to_acc.balance   == to_acc.balance + amount

body
  fn transfer(from_acc, to_acc, amount) =
    { from_acc: { id: from_acc.id, balance: from_acc.balance - amount },
      to_acc:   { id: to_acc.id,   balance: to_acc.balance + amount } }
```

Here is the part that reaches the bank. It reads two accounts, checks the balances, calls `transfer`, and writes the results. The writes are separate: if the second fails, the first remains.

```brass
# bank/main.brass
module bank.main
import bank.transfer as transfers

interface
  access Banking
    allow pull_account(id: transfers.AccountId) -> Outcome<transfers.Account>
      after result.id == id
    allow write(account: transfers.Account) -> Outcome<Done>

  fn move(banking: Banking, raw: transfers.RawRequest) -> Outcome<Done>

body
  fn move(banking, raw) =
    if raw is transfers.Request then
      let src: transfers.Account = banking.pull_account(raw.from_acc)?
      let dst: transfers.Account = banking.pull_account(raw.to_acc)?
      if raw.amount > src.balance then Err(FailureCode.Conflict, "insufficient funds")
      else if dst.balance + raw.amount > transfers.max_balance then Err(FailureCode.Conflict, "destination over max balance")
      else
        let done: transfers.Transfer = transfers.transfer(src, dst, raw.amount)
        banking.write(done.from_acc)?
        banking.write(done.to_acc)?
        Ok(Done)
    else Err(FailureCode.InvalidInput, "not a valid request")
```

The system file supplies the `Banking` access. Its limits bound execution, but they do not turn the two writes into a transaction:

```brass
# system.brass
system bank
  grants bank.main.move: banking = Banking
  limit  cpu_ms 2000
  limit  memory_bytes 67108864
  limit  transcript_bytes 16777216, drop oldest
  limit  impact_modules 2
```

The six contract lines state `transfer`'s requirements and promises. Flipping a sign in its body would break a promise. Removing the insufficient-funds check in `move` would leave a requirement unproved. Both edits would be rejected.

The call also depends on the records being the right accounts. The `Request` test establishes that their requested ids differ. `pull_account`'s enforced `after` ties each reply to its requested id. At this call, `transfer`'s first `before` reports **enforced** because it rests on those replies.

**Where it is limited.** The reads and writes do not form a transaction. Another transfer between them can see a stale balance. This access declares no operation that stores both balances at once.

Nothing checks how often `write` is called. The grant bounds what `move` may touch, but if the second write fails, the first has already happened. Returning an `Err` does not undo it.

---

## 5. Filter an array

Suppose a caller has a collection of support cases and wants only the open ones. The result type can say that every returned case is open. A second promise bounds the result's length, and the loop must establish both.

```brass
# orders/open.brass
module orders.open

interface
  type CaseId   = Int where it in 1 to 999999999
  type Cents    = Int where it in 0 to 100000000
  type Status   = Open | Closed
  type Case     = { id: CaseId, status: Status, paid_total: Cents }
  type OpenCase = Case where it.status in {Status.Open}
  type Cases    = Array<Case> where it.length in 0 to 1000

  fn open_cases(cases: Cases) -> Array<OpenCase> where it.length in 0 to 1000
    after result.length <= cases.length

body
  fn open_cases(cases) =
    let kept: Array<OpenCase> where it.length in 0 to 1000 = []
    for c in cases
      if c is OpenCase then kept = kept ++ [c]
    kept
```

The test `c is OpenCase` gives the loop the fact it needs: inside that branch, `c` has the type required by the result array.

The length promise is proven with no loop annotation: start empty and add at most one element per source element. The result is no longer than the input. The input's declared length bound also bounds the number of iterations.

**Where it is limited.** Five lines for what most languages write as one. A proposed helper, `cases.keep(OpenCase)`, would filter by a named refinement with no lambda. It is not part of the language or library.

The bound `1000` is written three times. Naming it once as a `const` would help. That is a style choice, not a missing form.

A refinement cannot relate a case to a runtime value outside it. Filtering for "cases paid more than this one" therefore stays a loop.

---

## 6. Retry a stuck gate

Finally, an operation that may need another try. A gate controller can fail to reply, and the program needs a stopping point. This body tries at most three times and returns the last outcome. Whether repeating the operation is safe is **assumed**; nothing checks the host's promise.

```brass
# park/gates.brass
module park.gates

interface
  type DoorId = Int where it in 1 to 200

  access Doors { doors: Set<DoorId>, deadline_ms: Int }
    allow open(door: DoorId) -> Outcome<Done>
      before door in doors

  fn open_with_retry(gates: Doors, g: DoorId) -> Outcome<Done>

body
  fn open_with_retry(gates, g) =
    let last: Outcome<Done> = Err(FailureCode.Unavailable, "not tried")   # starts as a failure, so the loop has something to replace
    for attempt in 1 to 3
      last = gates.open(g)
      if last is Ok then break
    last
```

The outcome stays in `last`, and `break` ends the loop on success. No exception handling is needed. The range bounds the attempts even if every call fails.

The runtime enforces each call's deadline and returns `Unavailable` or `Unknown` when it expires. It also checks `before door in doors`, refusing a door outside the grant before sending the call.

The awkward part is the first line: every `let` needs a value, so a failure stands in for "not tried yet". The first attempt replaces it.

The loop also retries failures such as `Unauthorized` that will not clear on another attempt. A body cannot inspect the failure code. The [paddock example](../examples/paddock/) puts the same loop inside a lockdown, with a requirement on who may close the door.
