Complete the task using the supplied project at `/tmp/rerun-opus55-20261017/small-P2/project`. Everything you may read is under that directory; do not read, search, or list anything outside it. Start with `README.md`. You may run `python3`, and write and run your own tests under that directory. The project has no tests of its own. Make the change by modifying files under that directory. Budget: at most 150 tool calls and sixty minutes. When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task that caused the most unnecessary work; (3) every assumption you made that the task did not settle.

TASK

# Task C: cash advances

## Requirement

Field staff cannot front the cost of a trip. Before a trip, a staff member may request a cash advance for a period, and settle it against the expense report they file afterwards.

- **Requesting.** An active staff member requests an advance for a period that is not closed, stating the amount (at least 1 cent). The advance belongs to the staff member's department.
- **Approving.** An advance is approved by the same people, in the same order, as an expense report of that amount from that staff member would be, with the same refusals: not by the requester, not in a closed period, not by anyone but the required approver, and at the last step not past the department's budget unless the approver is Finance. An approved advance counts against the department's budget for its period, like an approved report.
- **Paying.** Finance pays an approved advance through the ledger, in full, with the advance's id as the key.
- **Settling.** When Finance pays an expense report, they may settle it against one of the staff member's paid advances: the report's payment is reduced by the advance. If the advance covers the whole report, nothing is paid through the ledger, the report takes the advance's ledger reference, and the difference is recorded on the advance as owed by the staff member. Either way the advance is settled and the report is paid. An advance can be settled once, only against an approved report by the same staff member in the same period; otherwise Conflict.
- **Budget.** An advance counts against its department's budget for its period while Approved or Paid. Once settled it stops counting, since the report it was settled against counts instead.
- **Outstanding.** An advance paid but not settled within two periods of its period is outstanding: `period + 2 < today`.
- Every state change of an advance is audited like a report's: each approval step, the payment, and the settlement. Requesting one is not audited, as opening a draft is not.

## Interface

**Advance:** id, badge, department, period, amount, status, approvals (as a report's), reference (once paid), owed (once settled; 0 when the report covered it). Status: Requested → Approved → Paid → Settled. Advances are not rejected in this change.

An advance is paid like a report: a closed period does not block it.

New entry points:

```
request_advance(badge, period, amount) → advance id
approve_advance(advance_id, approver) → the advance's status after
pay_advance(advance_id, finance_badge) → ledger reference
pay_against(report_id, advance_id, finance_badge) → ledger reference, or "settled" when nothing was paid
outstanding_advances(today) → list of advance ids, in the store's order
```

**Statement:** spend and remaining include counted advances; after the report rows, one row per counted advance, in the store's order, with `total` and `budgeted` its amount.

**Store** gains `advance(id)`, `advances_for(department, period)` (every advance there, at most 1,000), `paid_advances()` (every Paid advance, at most 1,000), `save_advance(advance)`. `next_id()` supplies advance ids. Audit entries for an advance use the advance's id in the report field.

## Acceptance

The same hidden cases run against both implementations. They check results; every advance and report saved (status, approvals, reference, owed); every audit entry; every ledger call; that spend and the statement include approved and paid advances; and that everything the baseline already does is unchanged.
