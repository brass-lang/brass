## Project map

Entry points are the `grants` lines of `src/system.brass`. Modules under `src/desk/`, with their declarations:

| Module | What it holds | Declarations |
|---|---|---|
| `advance_desk` | entry points: cash advances | request_advance approve_advance |
| `advances` | the advance record and its state machine | AdvanceStatus Amount Advance Advances Requested Approved PaidAdvance Counted add_approval approve pay settle outstanding |
| `allowances` | entry points: per diem and mileage lines | add_per_diem add_mileage |
| `audit` | audit entries for reports and advances: a subject, a shared state vocabulary, a converter per machine (C22) | Subject Step Entry report_entry advance_entry of_report of_advance |
| `budget` | spend against a department's budget | spend_of department_spend |
| `card_limits` | entry points: card limits | set_card_limit over_limit spent_by |
| `cards` | entry points: corporate card transactions | TxnIds import_txn match_txn dispute_txn unmatched |
| `delegation` | entry points: delegating approval authority | grant_delegation revoke_delegation delegate_in_force |
| `entities` | entry points: cost-center summaries | CostCenterSummary cost_center_summary |
| `exceptions` | entry points: policy exceptions | request_exception decide_exception |
| `forecasting` | entry points: spend forecasts | Forecast forecast |
| `host` | the accesses the host implements | Store Ledger |
| `ids` | value types | Money Period Badge Reason Description ReportId DepartmentId Role Category |
| `lines` | expense lines and category policy | Line Lines Policy policy_for line_valid all_valid total budgeted_total |
| `payment` | entry points: paying, closing periods | pay pay_advance pay_against close_period |
| `purchasing` | entry points: purchase orders | raise_po approve_po reject_po receive_po close_po po_commitments |
| `queries` | entry points: read-only views | Ids Row Rows Statement statement spend outstanding_advances pending_for |
| `readiness` | entry points: period readiness | Readiness period_readiness |
| `records` | records and machines for the added subsystems | VendorId PoId TxnId DelegationId CostCenterId EntityId Region Vehicle Amount PoStatus CardStatus Vendor PurchaseOrder POs PoRequested PoApproved PoReceived CardTxn Txns OpenTxn Delegation Delegations CostCenter Entity DeptIds CardLimit ExceptionId ExceptionStatus PolicyException Exceptions PendingException Badges commitments in_force per_diem_rate mileage_rate add_po_approval approve_po reject_po receive_po close_po decide match_txn dispute_txn |
| `registry` | the access for the added subsystems' data | Registry |
| `reporting` | entry points: period summaries | PeriodSummary period_summary |
| `reports` | the report record and its state machine | ReportStatus Approvals Report Reports Draft Submitted Approved AwaitingChanges Counted Editable add_line submit add_approval approve reject request_changes resubmit pay |
| `review` | entry points: drafting, submitting, approving | open_draft add_line submit approve reject request_changes resubmit may_act may_act_on |
| `routing` | who approves at which step | Step steps_for role_for |
| `staff` | staff and departments | Staff Active Finance Department |
| `vendors` | entry points: vendor management | onboard_vendor deactivate_vendor vendor_spend |
| `query` |  | q:cbfcef2b cite this id; `brass verify q:cbfcef2b` re-runs the query and says whether the answer still holds |
