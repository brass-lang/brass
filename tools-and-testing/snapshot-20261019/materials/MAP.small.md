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
