Complete the task using the supplied project at `/private/tmp/keel-18-run/PC1/project`. Everything you may read is under that directory; do not read, search, or list anything outside it. You may run `python3`, and write and run your own tests under that directory. The project has no tests of its own. Read the code you need with `bin/pytool show` and `show --body` (several modules per call), then write every edit in one `bin/pytool apply`. Fix anything it marks with another `apply`. Make the change by modifying files under that directory. Budget: at most 150 tool calls and sixty minutes. When you are done, answer briefly: (1) the information that was missing or unclear; (2) the part of the task that caused the most unnecessary work; (3) every assumption you made that the task did not settle.

## `bin/pytool`

Put several modules in one call.

```
pytool show                               every module's declarations: the source without function bodies, in one call
pytool show --body review payment queries the whole files of several modules, in one call
pytool apply <<'PATCH'                    every edit, across every file, in one call; then compiles what changed
@@@ edit src/desk/review.py               a block: the exact text to find (once in the file) and its replacement
@@@ find
…
@@@ replace
…
@@@ end
@@@ new src/desk/advances.py              a block: a whole new file
…
@@@ end
PATCH
```

If any block does not match, nothing is written and each block is marked ✓ or ✗.

## `host-contract.txt`: the operations the host implements

Only these exist at run time.

```
# The operations the host implements for this change.
# The host publishes these; the program does not add to them.
Store.staff
Store.report
Store.department
Store.reports_for
Store.submitted_reports
Store.period_closed
Store.next_id
Store.save_report
Store.append_audit
Store.close_period
Ledger.pay
Store.advance
Store.advances_for
Store.paid_advances
Store.save_advance
Registry.vendor
Registry.po
Registry.pos_for
Registry.txn
Registry.txns_for
Registry.delegation
Registry.delegations_from
Registry.cost_center
Registry.departments_of
Registry.entity
Registry.allowance
Registry.pos_of_vendor
Registry.card_limit
Registry.departments
Registry.exception
Registry.exceptions_for
Registry.save_po
Registry.save_txn
Registry.save_delegation
Registry.save_vendor
Registry.save_card_limit
Registry.save_exception
```


## Project map

Entry points are the public functions of the entry-point modules named in `README.md`. Modules under `src/desk/`, with their declarations:

| Module | What it holds | Declarations |
|---|---|---|
| `allowances` | entry points: per diem and mileage lines | MAX_DAYS MAX_KM add_per_diem add_mileage; _editable |
| `audit` | audit entries | Entry |
| `budget` | spend against a department's budget | spend_of |
| `card_limits` | entry points: card limits | set_card_limit over_limit |
| `cards` | entry points: corporate card transactions | MATCHABLE import_txn match_txn dispute_txn unmatched; _own_open |
| `checks` | shared refusals: who may act | active_staff finance_staff |
| `delegation` | entry points: delegating approval authority | MAX_SPAN grant_delegation revoke_delegation |
| `entities` | entry points: cost-center summaries | CostCenterSummary cost_center_summary |
| `errors` | the failure type and its codes | FailureCode Failure |
| `exceptions` | entry points: policy exceptions | request_exception decide_exception |
| `forecasting` | entry points: spend forecasts | Forecast forecast |
| `host` | the services the host implements | Store Ledger |
| `ids` | value types | Money Period Badge ReportId DepartmentId MONEY_MAX PERIOD_MAX Role Category |
| `lines` | expense lines and category policy | MAX_LINES Line Policy POLICIES policy_for line_valid all_valid total budgeted_total |
| `payment` | entry points: paying, closing periods | pay close_period; _finance |
| `purchasing` | entry points: purchase orders | raise_po approve_po reject_po receive_po close_po po_commitments accepted_for; _gate |
| `queries` | entry points: read-only views | spend Row Statement statement pending_for |
| `readiness` | entry points: period readiness | Readiness period_readiness |
| `records` | records and machines for the added subsystems | VendorId PoId TxnId DelegationId CostCenterId EntityId ExceptionId MAX_TEXT MAX_PO_APPROVALS Region Vehicle PoStatus CardStatus ExceptionStatus PER_DIEM MILEAGE PO_TRANSITIONS CARD_TRANSITIONS EXCEPTION_TRANSITIONS Vendor PurchaseOrder CardTxn Delegation Entity CostCenter CardLimit PolicyException advance_po add_po_approval advance_txn settle_exception in_force committed commitments_of text_ok; _move |
| `registry` | the access for the added subsystems' data | Registry |
| `reporting` | entry points: period summaries | PeriodSummary period_summary |
| `reports` | the report record and its state machine | MAX_LINES MAX_APPROVALS ReportStatus TRANSITIONS Report editable add_line submit add_approval approve reject request_changes resubmit pay counts_as_spend; _enter |
| `review` | entry points: drafting, submitting, approving | open_draft add_line submit resubmit approve reject request_changes may_act; _own _open_and_valid _gate _required_for _stand_in _final_approval |
| `routing` | who approves at which step | SUPERVISOR_ONLY_UP_TO DIRECTOR_UP_TO STEP_ROLES steps_for role_for |
| `staff` | staff and departments | Staff Department is_finance |
| `vendors` | entry points: vendor management | onboard_vendor deactivate_vendor vendor_spend |


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
