## Project map

Entry points are the `grants` lines of `src/system.brass`. Modules under `src/desk/`, with their declarations:

| Module | What it holds | Declarations |
|---|---|---|
| `ids` | value types | Money Period Badge Reason Description ReportId DepartmentId Role Category |
| `lines` | expense lines and category policy | Line Lines Policy policy_for line_valid all_valid total budgeted_total |
| `staff` | staff and departments | Staff Active Finance Department |
| `reports` | the report record and its state machine | ReportStatus Approvals Report Reports Draft Submitted Approved AwaitingChanges Counted Editable; add_line submit add_approval approve reject request_changes resubmit pay |
| `audit` | audit entries | Entry entry |
| `host` | the accesses the host implements | Store Ledger |
| `routing` | who approves at which step | Step steps_for role_for |
| `budget` | spend against a department's budget | spend_of |
| `review` | entry points: drafting, submitting, approving | open_draft add_line submit approve reject request_changes resubmit; may_act |
| `payment` | entry points: paying, closing periods | pay close_period |
| `queries` | entry points: read-only views | spend statement pending_for; Ids Row Rows Statement |
| `records` | records and machines for the added subsystems | VendorId PoId TxnId DelegationId CostCenterId EntityId ExceptionId Region Vehicle Amount PoStatus CardStatus ExceptionStatus Vendor PurchaseOrder POs PoRequested PoApproved PoReceived CardTxn Txns OpenTxn Delegation Delegations CostCenter Entity DeptIds CardLimit Badges PolicyException Exceptions PendingException; commitments in_force per_diem_rate mileage_rate add_po_approval approve_po reject_po receive_po close_po decide match_txn dispute_txn |
| `registry` | the access for the added subsystems' data | Registry |
| `delegation` | entry points: delegating approval authority | grant_delegation revoke_delegation; delegate_in_force |
| `purchasing` | entry points: purchase orders | raise_po approve_po reject_po receive_po close_po po_commitments |
| `cards` | entry points: corporate card transactions | import_txn match_txn dispute_txn unmatched; TxnIds |
| `allowances` | entry points: per diem and mileage lines | add_per_diem add_mileage |
| `entities` | entry points: cost-center summaries | cost_center_summary; CostCenterSummary |
| `reporting` | entry points: period summaries | period_summary; PeriodSummary |
| `vendors` | entry points: vendor management | onboard_vendor deactivate_vendor vendor_spend |
| `card_limits` | entry points: card limits | set_card_limit over_limit; spent_by |
| `readiness` | entry points: period readiness | period_readiness; Readiness |
| `exceptions` | entry points: policy exceptions | request_exception decide_exception |
| `forecasting` | entry points: spend forecasts | forecast; Forecast |
