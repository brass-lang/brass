# Refund

A merchant refunds a customer on an open support case. The program has two modules and a `system` file.

## What the interface says

Read `support/refund.brass` without its body:

- **What `issue` may do.** Refund through `pay`, and nothing else. `pay` is its only access parameter, and `StripePay` refines it: Stripe, at most 50000 cents per transaction. No parameter, no effect.
- **What it promises.** On success, the receipt is for `amount`. Its four `before` lines say what the caller must show first.
- **Where the merchant check sits.** On `issue`, as a `before`: `case.merchant == who.id`. It applies to callers of `issue`. The paddock example puts its authorization requirement on the `allow` itself, where every holder must meet it. Both are legal.

Read `payments/core.brass`: `refund` takes the case and pays its customer. A body cannot choose the customer.

**What breaks if it changes.**

- **Widen the grant past 50000** → rejected: the grant must fit `StripePay`.
- **Widen `StripePay`'s ceiling** → still checks; the interface hash changes, so the change is detectable.
- **Drop `before amount > 0` from `issue`** → rejected: `refund`'s own `before amount > 0` can no longer be proved.
- **Change `case` to `payments.CaseRecord`** → rejected; the wrong edit below.

## Which promises are checked, and where?

`issue`'s four entry conditions depend on who calls it:

- **Called from Brass — proven:** the caller proves them or is rejected.
- **Called by the host — enforced:** the boundary checks each before running `issue`. A failure replies `Err(FailureCode.InvalidInput, …)` (spec §8.5).

`refund`'s `before amount > 0` follows from `issue`'s entry condition and carries that fact's tier.

**Proven**

- The grant's values fit `StripePay`, including the `Stripe` literal.

**Enforced**

- `refund`'s `before amount <= per_txn_max`: an authority check; the runtime refuses with `Unauthorized`.
- `refund`'s `after`: the runtime checks every successful reply; a violation aborts the task.
- `issue`'s `after result.amount == amount`: it rests on `refund`'s `after`, an enforced fact.
- `per_txn_max: 50000` in the grant: `refund`'s `before` names it.
- CPU and memory limits abort the task on excess. The transcript limit drops the oldest records (spec §10.1).

**Assumed**

- That the host routes to Stripe. Checking the grant's literal against `StripePay` does not check routing; no `before` on `refund` names `processor`.
- That the host pays the customer the receipt names: where `Receipt` carries the customer, `refund`'s `after` binds it; the rest is the host's promise.
- That `who` identifies the merchant and `case` identifies the case in the stated status. The host supplies those identities and the incoming machine state (spec §8.5).

The optional `impact_modules` policy reports changes that exceed the configured scope. It is separate from the promise tiers and does not reject a program. Its count is provisional (spec §10.1).

## The wrong edit, rejected

A model widens `issue` "to handle every case":

```brass
# support/refund.brass — wrong edit
  fn issue(pay: StripePay, who: Merchant, case: payments.CaseRecord, amount: payments.Money) -> Outcome<payments.Receipt>
```

The body's `pay.refund(case, amount)` no longer fits `refund`'s declaration:

```
fault argument type: expected payments.OpenCase, found payments.CaseRecord
  at support/refund.brass: fn issue, pay.refund(case, amount)
  fix: test case is payments.OpenCase first, or keep the parameter as payments.OpenCase
```

## The wrong body that checks clean

This body satisfies every clause and refunds twice:

```brass
# support/refund.brass — passes every clause; refunds twice
body
  fn issue(pay, who, case, amount) =
    let first: payments.Receipt  = pay.refund(case, amount)?
    let second: payments.Receipt = pay.refund(case, amount)?
    let chosen: payments.Receipt = if first.amount == second.amount then first else second
    Ok(chosen)
```

`before` states conditions on inputs; `after` states conditions on successful results. Neither counts calls. `Pay` has only a per-transaction ceiling. A total would need a `budget_<unit>` bound and the host metering described in spec §8.2.

This grant permits both calls. A reviewer or test must inspect the body to find the duplicate refund.

## What these declarations leave open

- Which failure `refund` returned. A body can test `x is Err` and pass the error on, but cannot inspect its failure code.
- That the case is still open in the store when the refund runs. `OpenCase` describes the value passed, not the store.
- That the receipt corresponds to a real payout. `refund`'s `after` checks the reply's shape; the money is the host's.
- A spending total across separate tasks. A task gets fresh quota counters; a quota shared between tasks is not defined.
- Safe retries. `refund` declares no idempotency key. The convention in spec §5.2 calls for one when repeating an operation could repeat the effect; a real payout operation would need it.

For state transitions with `enters`, see [paddock](../paddock/) and [feeding](../feeding/).
