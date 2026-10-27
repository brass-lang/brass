# Brass — three examples

Read these in order to follow authority, contracts, and state changes through complete programs. Each directory includes the modules, `system.brass`, and a README explaining its promises, limits, and a rejected edit.

| Example | Shows | The wrong edit |
|---|---|---|
| [`refund/`](refund/) | A merchant refunds a customer. Parameters limit authority; contracts describe the result. | Refunding a case that is not open is rejected. Refunding twice still meets the contracts. |
| [`paddock/`](paddock/) | A door operator locks down an open enclosure, with up to three attempts. | Accepting any paddock is rejected: two states cannot move to `Secured`. |
| [`feeding/`](feeding/) | A delivered feeding records its keeper; a planned feeding has no signer. | Reading the signer before establishing the delivered state is rejected. |

These programs were reviewed by hand and through three blind reads. Their verdicts and tiers are what the full checker establishes; `brass` today checks structure and runs the examples.

**Running `brass` on them.** From the repository root, `tools-and-testing/checks/check-example.sh paddock` (or `feeding`, `refund`). Paddock and feeding pass. Refund spans two source folders and `brass` reads one, so it reports one false rejection.

**Where to find the rules.** The [spec](../docs/brass-core-spec.md) defines types and names (§2), local bindings (§3), modules and imports (§4), failure (§5), accesses (§8), and system limits (§10.1).

**Two forms used throughout.** `?` yields a successful result or passes the failure to the caller. It is legal only in a function returning `Outcome`. A successful `x is T` test lets its branch use `x` as the narrower type `T`.

**How to read the tiers.** *Proven*: a checker proves it before the program runs. *Enforced*: the runtime checks it on every call. *Assumed*: nothing checks it; the program goes forward as if it held. Each README applies these tiers to its program's promises.

**The `fix:` line.** Each rejection names a repair, as required by spec §12. The wording is illustrative; [The report design](../docs/design/brass-report-design.md) defines the format.
