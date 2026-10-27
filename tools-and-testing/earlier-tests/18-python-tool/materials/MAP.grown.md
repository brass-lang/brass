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
