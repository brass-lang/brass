# Feeding delivery

A keeper delivers the pending feeding for a paddock. The delivered feeding records who signed for it; a planned feeding has no signer. Four modules and a `system` file define the workflow.

## What the interface says

Read `park/feeding.brass` without its bodies:

- **A field that exists in one state.** `delivered_by` is present exactly when `status` is `Delivered`. Reading a signer from a `Planned` feeding is rejected.
- **How a value enters that state.** `deliver` takes a `PendingFeeding` and a `Deliverer` and returns a `DeliveredFeeding` whose signer is the deliverer's badge. Its `after` may name `result.delivered_by` because `result` is known to be `Delivered`.
- **Who may deliver.** `Deliverer` is a keeper. `deliver` cannot be called with plain `Staff`.
- **Library functions.** `plan`, `skip`, and `signer` have no caller in this program; they are the module's other operations, shown so the machine's three states each have a use.

In `park/control.brass`, `deliver_feeding` holds one access, `registry`, for paddocks 1 to 5. It tests that `who` is a `Deliverer`, then calls a private helper to read, deliver and save the feeding.

Its `after` promises that the result is for the requested paddock and signed by `who`.

Adding `delivered_by` connects the state declaration to the caller:

- The field's `when` attaches it to `Delivered`.
- `deliver` accepts `by` and supplies the badge in its `with`.
- `deliver`'s `after` ties the badge to `by`.
- `control` establishes a `Deliverer` and includes the signer in its result contract.

`plan` is untouched because a `Planned` feeding must not mention the field. The trials behind this design are described in [principles §4](../../docs/brass-core-principles.md#4-evidence-limits).

**What breaks if it changes.**

- **Add a state to `FeedingStatus`** → still checks: `deliver`'s `with` transitions from `Planned` only; the interface hash changes, so the change is detectable.
- **Rename `delivered_by` without updating its uses** → rejected: `signer`'s body, `deliver`'s `after` and body, and `deliver_feeding`'s `after` still name the old field.
- **Drop the `is` test from `signer`** → rejected; the wrong edit below.

## Which promises are checked, and where?

**Proven**

- `deliver`'s and `skip`'s transitions from `Planned`: a declared edge from the one source state.
- `deliver`'s `after`, `delivered_by` included: the `with` supplies the field on entering `Delivered`.
- `skip`'s `after`: `with` copies the rest.
- `plan`'s `after` and its `PendingFeeding` return type: the literal's fields are known to the checker, so it satisfies the refinement on the line (spec §7.2).
- `signer` reads `delivered_by` only inside `if f is DeliveredFeeding`: anywhere else is a rejection.

**Enforced**

- `pending`'s and `save`'s `before … in paddocks`: authority checks; the runtime refuses with `Unauthorized`.
- `pending`'s `after result.paddock == paddock`: the runtime checks the successful reply; a violation aborts.
- `deliver_feeding`'s and `deliver_as`'s `after`: `result.paddock == paddock` rests on `pending`'s `after`, an enforced fact; `result.delivered_by == who.badge` follows from `deliver`'s.
- The boundary check of `who` and `paddock` against their types.
- CPU and memory limits abort the task on excess. The transcript limit drops the oldest records (spec §10.1).

**Assumed**

- That the registry holds the feeding it saved, and that the feeding `pending` returns is really pending there: the host implements both; the reply's shape is checked, its truth is not.
- That `who` is the keeper the badge says: the host's authentication.

The optional `impact_modules` policy reports changes that exceed the configured scope. It is separate from the promise tiers and does not reject a program. Its count is provisional (spec §10.1).

## The wrong edit, rejected

A model simplifies `signer`:

```brass
# park/feeding.brass — wrong edit
  fn signer(f) = Ok(f.delivered_by)
```

```
fault field not present on this path: delivered_by needs status in {FeedingStatus.Delivered}
  at park/feeding.brass: fn signer
  in scope: f: Feeding (not narrowed)
  fix: test f is DeliveredFeeding first, or take a DeliveredFeeding
```

Writing `delivered_by` into a `Planned` literal is also rejected. The field exists only in the `Delivered` state.

## What these declarations leave open

- Which failure `pending` returned: not found, unavailable, or refused. A body tests `x is Err` and passes it on.
- That the feeding is still pending in the registry when `save` runs. `PendingFeeding` describes the value read.
- Two signers, or a signer on a `Skipped` feeding. Either requires changing the record declaration.
