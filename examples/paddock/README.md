# Paddock lockdown

A staff member supplies a paddock number and asks to lock it down. Three modules and a `system` file define the permitted operations.

## What the interface says

Read `park/doors.brass` without its bodies:

- **What `lockdown_request` may do.** Read an enclosure and close a door through `doors`, and nothing else: `doors` is its only access parameter. `system.brass` permits paddocks 1 to 3 and gives each call two seconds.
- **Who may cause the effect.** `close` takes a `DoorOperator`. Nothing that holds `Doors` can close a door without one. `lockdown_request` takes plain `Staff` and a paddock id. Before calling `close`, its helpers test `who is staff.DoorOperator` and `p is enclosures.OpenPaddock`.
- **What it promises.** The paddock that comes back has the id that was asked for, and its enclosure is `Secured`: that is the return type.

Read `park/enclosures.brass`: `Enclosure` says which states a paddock may enter. `Breached` has no edge out; repair is outside this program. `Secured` has no edge to itself: locking down a secured paddock is not a transition this machine declares.

The body tries `close` up to three times, retrying every failure, including `Unauthorized`. The range bounds the attempts even if the loop never breaks. `last` starts before the loop and holds each attempt's result. This retry policy is not in the interface.

The paddock's state enters the program through `enclosure`, an `allow` whose result type carries the machine. The runtime checks that the reply fits the type. Whether it describes the actual enclosure is assumed.

**What breaks if it changes.**

- **Change `close` to take `Staff`** → still checks. The operation no longer requires a door operator. The helper's stricter parameter and test remain, but any holder of `Doors` can call `close` with plain `Staff`.
- **Change `OpenPaddock` to `Paddock` in `lockdown`** → rejected; the wrong edit below.

## Which promises are checked, and where?

**Proven**

- `lockdown`'s transition `Open enters Secured`: `p` is an `OpenPaddock`, and the edge is declared.
- `lockdown`'s `after`: `with` copies every field it does not name.
- The return type `SecuredPaddock`: the checker sees `status enters Enclosure.Secured` in the `with`.
- The loop runs at most three times: `for attempt in 1 to 3` is bounded by its range.

**Enforced**

- `enclosure`'s and `close`'s `before paddock in paddocks`: authority checks; an id outside the grant is refused with `Unauthorized` before the call is sent.
- `enclosure`'s `after result.id == paddock`: the runtime checks the successful reply; a violation aborts.
- `lockdown_as`'s and `lockdown_request`'s `after result.id == paddock`: they rest on `enclosure`'s `after`.
- Each `close` call ends within `deadline_ms`, with a reply, `Unavailable`, or `Unknown`.
- The boundary check of `who` and `paddock` against their types.
- CPU and memory limits abort the task on excess. The transcript limit drops the oldest records (spec §10.1).

**Assumed**

- That the paddock `enclosure` returns is really `Open` in the park: the reply's shape is checked; its truth is the host's.
- That `who` is entitled to act as a door operator: a refined record is not a credential; the host's authentication supplies that.
- That the door is physically closed when `close` returns `Ok`.
- That a retry after `Unknown` is safe: closing a closed door is harmless, and nothing in Brass checks that an `allow` is idempotent. The spec's convention (§5.2) asks a key parameter of an `allow` whose repeat would be a second effect; a repeated close is the same effect, so `close` declares none.

The optional `impact_modules` policy reports changes that exceed the configured scope. It is separate from the promise tiers and does not reject a program. Its count is provisional (spec §10.1).

## The wrong edit, rejected

A model lets any paddock be locked down:

```brass
# park/doors.brass — wrong edit
  fn lockdown(doors: Doors, operator: staff.DoorOperator, p: enclosures.Paddock) -> Outcome<enclosures.SecuredPaddock>
```

The body's transition no longer has an edge from every possible source state:

```
fault edge not established: p.status enters enclosures.Enclosure.Secured
  source states not covered: Secured, Breached
  at park/doors.brass: fn lockdown
  fix: narrow p to a state with that edge, or test p is enclosures.OpenPaddock first
```

The machine declares no move from `Breached` or `Secured` into `Secured`. Closing a door does not repair a breached enclosure, and this program has no transition for locking down an already secured paddock.

## What these declarations leave open

- That the paddock is still open in the park's records when the door closes. `OpenPaddock` describes the value read.
- That the *same* paddock's state moved. The machine enforces the state graph, not the history of one entity; `after result.id == paddock` is what ties the result to the request here.
- A door operator's assigned paddocks. This program checks the role but declares no assignment check. A `before` on `close` could require one.
- Which failure `close` returned on the last attempt. The retry replaces it with its own `Unavailable`; the transcript holds the original.
