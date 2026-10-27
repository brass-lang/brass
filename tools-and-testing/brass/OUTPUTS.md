# brass: every kind of output

Real output, generated from a copy of the stage 2 Brass tree (unpublished), which is also the baseline,
so "touched" lists only what a planted fault changed.
Each rejection below comes from one planted fault, named above its block. Long outputs are trimmed.

Two known gaps show here: the effect check misses a write followed by `if … else Err(…)` at the same indent, and
"touched" marks every entry point in an edited file as changed, not only the one edited. Both are in `BRASS.md`.

## Lean mode: what sessions use (`BRASS_LEAN=3`)

### Usage

Any unknown command answers with this.

```text
$ brass help
usage  (several names per call; all your edits in one `apply`; it runs `check` for you)
  brass show                               every module's declarations, numbered: the whole interface in one call
  brass show --body review payment queries the whole files of several modules, in one call
  brass show <module>.<name> [...]         declarations with their bodies
  brass info <module>.<name> [...]         what uses each declaration, and how
  brass apply <<'PATCH' … PATCH            every edit, across every file, in one call; then the full check (format below)
  brass apply --dry <<'PATCH' … PATCH      the same, writing nothing: does each block match?
  brass check                              the completion gate on its own: structure, examples, scenarios, host contract,
                                           effect order, what each touched entry point does. Clean ends with `done`.

patch format: one block per change, any number of blocks and files
  @@@ edit src/desk/review.brass            then @@@ find, the exact text to replace (it must occur once in the file),
  @@@ find                                 then @@@ replace, the new text, then @@@ end
  …
  @@@ replace
  …
  @@@ end
  @@@ new src/desk/advances.brass           a whole new file: its text, then @@@ end
  …
  @@@ end
Blocks for one file apply in order. If any block does not match, nothing is written.
modules: advance_desk  advances  allowances  audit  budget  card_limits  cards  delegation  entities  exceptions  forecasting  host  ids  lines  payment  purchasing  queries  readiness  records  registry  reporting  reports  review  routing  staff  vendors
```

### show: the whole interface

Every module's declarations, numbered, in one call. Trimmed here.

```text
$ brass show
file        src/desk/advance_desk.keel   declarations, lines 1 to 16 of 59   (`show advance_desk --body` for the whole file)
   1  # desk/advance_desk.keel
   2  module desk.advance_desk
   3  import desk.ids as ids
   4  import desk.staff as staff
   5  import desk.advances as advances
   6  import desk.audit as audit
   7  import desk.host as host
   8  import desk.routing as routing
   9  import desk.budget as budget
  10  import desk.review as review
  11  
  12  interface
  13    fn request_advance(store: host.Store, badge: ids.Badge, period: ids.Period, amount: advances.Amount) -> Outcome<ids.ReportId>
  14    fn approve_advance(store: host.Store, advance_id: ids.ReportId, approver: ids.Badge) -> Outcome<advances.AdvanceStatus>
  15  private
  16    fn approve_last(store: host.Store, a: advances.Requested, who: staff.Active) -> Outcome<advances.AdvanceStatus>

file        src/desk/advances.keel   declarations, lines 1 to 36 of 42   (`show advances --body` for the whole file)
   1  # desk/advances.keel
   2  module desk.advances
   3  import desk.ids as ids
   4  import desk.reports as reports
   5  
   6  interface
… (599 more lines)
```

### show several declarations with bodies



```text
$ brass show lines.total payment.pay
file        src/desk/lines.keel
  20    fn total(ls: Lines) -> Int
  21      after result >= 0
  22      example total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
  23  

  41    fn total(ls) =
  42      let sum: Int = 0
  43      for l in ls
  44        sum = sum + l.amount
  45      sum
  46  

file        src/desk/payment.keel
  12    fn pay(store: host.Store, ledger: host.Ledger, report_id: ids.ReportId, finance_badge: ids.Badge) -> Outcome<Text>

  17    fn pay(store, ledger, report_id, finance_badge) =
  18      let who: staff.Staff = store.staff(finance_badge)?
  19      if who is staff.Finance then
  20        let r: reports.Report = store.report(report_id)?
  21        if r is reports.Approved then
  22          let reference: Text = ledger.pay(r.badge, lines.total(r.lines), r.id)?
  23          store.save_report(reports.pay(r, reference))?
  24          store.append_audit(audit.report_entry(who.badge, r.id, reports.ReportStatus.Approved, reports.ReportStatus.Paid, "paid"))?
  25          Ok(reference)
  26        else Err(FailureCode.Conflict, "the report is not approved")
  27      else Err(FailureCode.Unauthorized, "only active finance staff may pay")
  28
```

### show --body: whole files

Several modules in one call. Trimmed here.

```text
$ brass show --body lines audit
file        src/desk/lines.keel   lines 1 to 51 of 51
   1  # desk/lines.keel
   2  module desk.lines
   3  import desk.ids as ids
   4  
   5  interface
   6    type Line   = { category: ids.Category, amount: ids.Money, description: ids.Description, receipt: Bool }
   7    type Lines  = Array<Line> where it.length in 1 to 50
   8    type Policy = { limit: ids.Money, receipt_over: ids.Money, budgeted: Bool }
   9  
  10    fn policy_for(c: ids.Category) -> Policy
  11      example policy_for(ids.Category.Other) == { limit: 50000, receipt_over: 2500, budgeted: true }
  12  
  13    fn line_valid(l: Line) -> Bool
  14      example line_valid({ category: ids.Category.Feed, amount: 2500, description: "hay", receipt: false }) == true
  15      example line_valid({ category: ids.Category.Feed, amount: 2501, description: "hay", receipt: false }) == false
  16      example line_valid({ category: ids.Category.Other, amount: 50001, description: "misc", receipt: true }) == false
  17  
  18    fn all_valid(ls: Lines) -> Bool
  19  
  20    fn total(ls: Lines) -> Int
  21      after result >= 0
  22      example total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
  23  
  24    fn budgeted_total(ls: Lines) -> Int
… (74 more lines)
```

### info: who uses a declaration



```text
$ brass info lines.budgeted_total
declaration fn budgeted_total   desk.lines    interface   src/desk/lines.keel:24
  fn budgeted_total(ls: Lines) -> Int
    after result >= 0
holds       no access; cannot reach outside
direct uses  3 declarations, 3 lines
  call                 budget.spend_of, queries.statement, review.final_approval (private)
      budget.keel:17    if r is reports.Counted then sum = sum + lines.budgeted_total(r.lines)
        in       fn spend_of(rs: reports.Reports, advs: advances.Advances) -> Int
        on path  no enclosing test
      queries.keel:36    rows = rows ++ [{ id: r.id, badge: r.badge, status: st, total: lines.total(r.lines), budgeted: lines.budgeted_total(r.lines) }]
        in       fn statement(store: host.Store, department: ids.DepartmentId, period: ids.Period) -> Outcome<Statement>
        on path  if r is reports.Counted then
      review.keel:146   let within: Bool = spent + lines.budgeted_total(r.lines) <= dept.budget
        in       fn final_approval(store: host.Store, r: reports.Submitted, who: staff.Active) -> Outcome<reports.ReportStatus>
        on path  no enclosing test
searched     src/desk/*.brass (26 modules, declarations and bodies), matched by name; 0 qualified names unresolved
body        5 lines   references: lines.policy_for
```

### check: clean

Structure, examples, scenarios, host contract, converters, effect order, and every entry point touched against the baseline. Ends in `done`.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✓ 26 found, 26 hold, 0 fail
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✓ no write before a possible refusal
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
done        nothing else to run
```

### check: a structural rejection

Planted: a call to `lines.totl`, which does not exist.

```text
$ brass check
check       1 rejection
  payment.keel:22      lines.totl: totl is not declared in desk.lines
                       fix: name a declaration that exists, or declare it there
next        fix these, then run `brass check` again
```

### check: a failing example

Planted: `total`'s example expects 3500; the body gives 3000.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✗ 26 found, 25 hold, 1 fail
  FAILS    lines.total   src/desk/lines.keel:22   total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3500
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✓ no write before a possible refusal
touched     each entry point you added or changed, as it now reads:
  review.approve               changed  refuses Unauthorized, Conflict · calls store.staff → store.report → store.period_closed → store.department → store.save_report → store.append_audit
  payment.pay                  changed  refuses Unauthorized, Conflict · calls store.staff → store.report → ledger.pay → store.save_report → store.append_audit · enters Paid
  payment.pay_against          changed  refuses Unauthorized, Conflict · calls store.staff → store.report → store.advance → ledger.pay → store.save_report → store.append_audit → store.save_advance · enters Paid, Settled
  queries.statement            changed  refuses nothing · calls store.department → store.reports_for → store.advances_for
  entities.cost_center_summary changed  refuses nothing · calls reg.cost_center → reg.entity → reg.departments_of → store.reports_for
  forecasting.forecast         changed  refuses nothing · calls store.department → store.reports_for → reg.pos_for
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
next        fix the items marked ✗ above, then run `brass check` again
```

### check: a write before a possible refusal

Planted: `pay` saves the paid report, then refuses a payment over a limit; the save stays behind.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✓ 26 found, 26 hold, 0 fail
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✗ 3 writes before a possible refusal
  warning   payment.keel:22  ledger.pay(…) writes before Err(Conflict) at line 25, which can refuse; an Err undoes nothing. Check what can refuse before you act.
  warning   payment.keel:23  store.save_report(…) writes before Err(Conflict) at line 25, which can refuse; an Err undoes nothing. Check what can refuse before you act.
  warning   payment.keel:24  store.append_audit(…) writes before Err(Conflict) at line 25, which can refuse; an Err undoes nothing. Check what can refuse before you act.
touched     each entry point you added or changed, as it now reads:
  payment.pay                  changed  refuses Unauthorized, Conflict · calls store.staff → store.report → ledger.pay → store.save_report → store.append_audit · enters Paid
  payment.pay_advance          changed  refuses Unauthorized, Conflict · calls store.staff → store.advance → ledger.pay → store.save_advance → store.append_audit · enters Paid
  payment.pay_against          changed  refuses Unauthorized, Conflict · calls store.staff → store.report → store.advance → ledger.pay → store.save_report → store.append_audit → store.save_advance · enters Paid, Settled
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
next        fix the items marked ✗ above, then run `brass check` again
```

### check: a write before a refusal the check misses (known gap)

Planted: `pay` saves the report, then `if r is reports.Approved then … else Err(Conflict)` refuses. The check reads that `else` as another path and stays silent. Recorded in `BRASS.md`; not fixed.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✓ 26 found, 26 hold, 0 fail
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✓ no write before a possible refusal
touched     each entry point you added or changed, as it now reads:
  payment.pay                  changed  refuses Unauthorized, Conflict · calls store.staff → store.report → store.save_report → ledger.pay → store.append_audit · enters Paid
  payment.pay_advance          changed  refuses Unauthorized, Conflict · calls store.staff → store.advance → ledger.pay → store.save_advance → store.append_audit · enters Paid
  payment.pay_against          changed  refuses Unauthorized, Conflict · calls store.staff → store.report → store.advance → ledger.pay → store.save_report → store.append_audit → store.save_advance · enters Paid, Settled
… (2 more lines)
```

### check: an operation the host does not provide

Planted: `Store.append_audit` removed from the host contract.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✓ 26 found, 26 hold, 0 fail
scenarios   none under scenarios/
host        ✗ 1 operation the host does not provide
  host.keel:22  allow Store.append_audit is not a host operation: host-contract.txt lists what the host implements. Use one of Store.advance, Store.advances_for, Store.close_period, Store.department, Store.next_id, Store.paid_advances, Store.period_closed, Store.report, Store.reports_for, Store.save_advance, Store.save_report, Store.staff, Store.submitted_reports.
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✓ no write before a possible refusal
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
next        fix the items marked ✗ above, then run `brass check` again
```

### check: converter coverage

Planted: `of_advance` loses its example for `Paid`; one `of_report` example expects the wrong step.

```text
$ brass check
check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✗ 25 found, 24 hold, 1 fail
  FAILS    audit.of_report   src/desk/audit.keel:21   of_report(reports.ReportStatus.Rejected) == Step.ChangesRequested
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✗ coverage not established
  ✗ audit.of_report (ReportStatus): 1 example fail (line 21)
  ✗ audit.of_advance (AdvanceStatus): no direct example for Paid
effects     ✓ no write before a possible refusal
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
next        fix the items marked ✗ above, then run `brass check` again
```

### apply --dry

Matches every block, writes nothing.

```text
$ brass apply --dry <<'PATCH' … PATCH
apply       ✓ dry run: all 1 blocks match, 1 file; nothing written
  block 1   ✓ edit src/desk/lines.keel:41  (2 lines → 2)
```

### apply: a block that does not match

All or nothing: one block misses, so nothing is written.

```text
$ brass apply <<'PATCH' … PATCH
apply       ✗ 1 of 2 blocks does not match; nothing was written
  block 1   ✓ edit src/desk/lines.keel:41  (2 lines → 2)
  block 2   ✗ edit src/desk/payment.keel: the find text occurs 0 times, not once; its first line appears nowhere
next        fix the blocks marked ✗ (copy the find text from the file exactly) and run `brass apply` again
```

### apply: a patch that is not closed



```text
$ brass apply <<'PATCH' … PATCH
apply       ✗ cannot read the patch: block not closed: expected @@@ replace
nothing was written. The format:
  @@@ edit <file>      then @@@ find, the exact text (once in the file), @@@ replace, the new text, @@@ end
  @@@ new <file>       then the whole file, then @@@ end
next        fix the patch and run `brass apply` again
```

### apply: written, then the full check



```text
$ brass apply <<'PATCH' … PATCH
apply       ✓ 1 block written to 1 file
  block 1   ✓ edit src/desk/lines.keel:41  (2 lines → 2)

check       ✓ structure: names, imports, declarations and bodies, call arity, `?` under Outcome, holes, typed lets, grants
examples    ✓ 26 found, 26 hold, 0 fail
scenarios   none under scenarios/
host        ✓ every host operation is in host-contract.txt
converters  ✓ every designated converter covers its machine
  ✓ audit.of_report: a passing direct example for every state of ReportStatus (6)
  ✓ audit.of_advance: a passing direct example for every state of AdvanceStatus (4)
effects     ✓ no write before a possible refusal
not checked contracts, refinements beyond the boundary, state edges, argument types: the real checker will
done        nothing else to run
```

### summary

Each entry point in check order: refusals, host calls, states entered. Trimmed here.

```text
$ brass summary
summary     each granted entry point: the refusals, host calls, state changes, and results found in its source, in
            source order, each with the conditions enclosing it; a refusal written in an else is placed at the if that
            decides it; helpers are followed one level. Read from the text, not executed; it proves nothing.
review.open_draft holds store
      boundary  badge: ids.Badge   checked before the body runs; a failing argument is refused as InvalidInput
      boundary  period: ids.Period   checked before the body runs; a failing argument is refused as InvalidInput
    35  call     store.staff(badge)   failure passes up;   reply checked by after result.badge == badge
    36  refuse   Unauthorized   "staff member is not active"   when not who is staff.Active
        within who is staff.Active
    37    call     store.period_closed(period)   failure passes up;   reply taken on trust
    38    refuse   Conflict       "the period is closed"   when closed
          within not closed
    39      call     store.next_id()   failure passes up;   reply taken on trust
    40      call     store.save_report({ id: id, badge: badge, department: who.department, period: period, lines: [first_line], status: reports.ReportStatus.Draft, approvals: [] })   failure passes up;   reply taken on trust
    41      succeed  Ok(id)
review.add_line holds store
      boundary  badge: ids.Badge   checked before the body runs; a failing argument is refused as InvalidInput
    46  via      review.own
      87  call     store.staff(badge)   failure passes up;   reply checked by after result.badge == badge
      88  refuse   Unauthorized   "staff member is not active"   when not who is staff.Active
          within who is staff.Active
      89    call     store.report(report_id)   failure passes up;   reply checked by after result.id == id
      90    refuse   Unauthorized   "only the submitter may act on this report"   when not r.badge == badge
            within r.badge == badge
      90      succeed  Ok({ r: r, who: who })
    47  refuse   Conflict       "the report is not editable"   when not o.r is reports.Editable
        within o.r is reports.Editable
          within o.r.lines.length < 50
    48      call     store.save_report(reports.add_line(o.r, line))   its result is the branch's value, failure included;   reply taken on trust
    48    refuse   InvalidInput   "a report holds at most 50 lines"   when not o.r.lines.length < 50
… (571 more lines)
```

## Full mode: the older query commands (no `BRASS_LEAN`)

Still there; trials since lean mode do not use them.

### brass info

The system map.

```text
$ brass info
brass (proxy: static rendering from source, no proofs run; tiers follow the declared form)
system      expenses
size        26 modules  1331 lines including system.brass

grants and limits   (src/system.brass)
  system expenses
    grants desk.review.open_draft: store = Store
    grants desk.review.add_line: store = Store
    grants desk.review.submit: store = Store
    grants desk.review.approve: store = Store
    grants desk.review.reject: store = Store
    grants desk.review.request_changes: store = Store
    grants desk.review.resubmit: store = Store
    grants desk.payment.pay: store = Store, ledger = Ledger
    grants desk.payment.close_period: store = Store
    grants desk.payment.pay_advance: store = Store, ledger = Ledger
    grants desk.payment.pay_against: store = Store, ledger = Ledger
    grants desk.advance_desk.request_advance: store = Store
    grants desk.advance_desk.approve_advance: store = Store
    grants desk.queries.outstanding_advances: store = Store
… (106 more lines)
```

### brass info --names



```text
$ brass info --names
advance_desk request_advance  approve_advance
advances    AdvanceStatus  Amount  Advance  Advances  Requested  Approved  PaidAdvance  Counted  add_approval  approve  pay  settle  outstanding
allowances  add_per_diem  add_mileage
audit       Subject  Step  Entry  report_entry  advance_entry  of_report  of_advance
budget      spend_of  department_spend
card_limits set_card_limit  over_limit  spent_by
cards       TxnIds  import_txn  match_txn  dispute_txn  unmatched
delegation  grant_delegation  revoke_delegation  delegate_in_force
entities    CostCenterSummary  cost_center_summary
exceptions  request_exception  decide_exception
forecasting Forecast  forecast
host        Store  Ledger
ids         Money  Period  Badge  Reason  Description  ReportId  DepartmentId  Role  Category
lines       Line  Lines  Policy  policy_for  line_valid  all_valid  total  budgeted_total
payment     pay  pay_advance  pay_against  close_period
purchasing  raise_po  approve_po  reject_po  receive_po  close_po  po_commitments
queries     Ids  Row  Rows  Statement  statement  spend  outstanding_advances  pending_for
readiness   Readiness  period_readiness
records     VendorId  PoId  TxnId  DelegationId  CostCenterId  EntityId  Region  Vehicle  Amount  PoStatus  CardStatus  Vendor  PurchaseOrder  POs  PoRequested  PoApproved  PoReceived  CardTxn  Txns  OpenTxn  Delegation  Delegations  CostCenter  Entity  DeptIds  CardLimit  ExceptionId  ExceptionStatus  PolicyException  Exceptions  PendingException  Badges  commitments  in_force  per_diem_rate  mileage_rate  add_po_approval  approve_po  reject_po  receive_po  close_po  decide  match_txn  dispute_txn
registry    Registry
… (7 more lines)
```

### brass info --holds



```text
$ brass info --holds
open_draft           desk.review    holds  store: host.Store
                     grant  store = Store
add_line             desk.reports   holds  no access
                     grant  store = Store
submit               desk.reports   holds  no access
                     grant  store = Store
approve              desk.advances  holds  no access
                     grant  store = Store
reject               desk.reports   holds  no access
                     grant  store = Store
request_changes      desk.reports   holds  no access
                     grant  store = Store
resubmit             desk.reports   holds  no access
                     grant  store = Store
pay                  desk.advances  holds  no access
                     grant  store = Store, ledger = Ledger
close_period         desk.payment   holds  store: host.Store
                     grant  store = Store
pay_advance          desk.payment   holds  store: host.Store  ledger: host.Ledger
                     grant  store = Store, ledger = Ledger
… (67 more lines)
```

### brass info lines

A module's interface with tiers.

```text
$ brass info lines
module      desk.lines    src/desk/lines.keel  51 lines  interface 20  private 0  body 25
imports     desk.ids  as ids
used_by     desk.allowances  desk.budget  desk.entities  desk.forecasting  desk.payment  desk.queries  desk.reports  desk.review
tiers       before/after: proven by brass before run.  type where: checked at each `in` test.  machine edges: proven.  access bounds, allow after: enforced by runtime.

interface
  type Line   = { category: ids.Category, amount: ids.Money, description: ids.Description, receipt: Bool }
  type Lines  = Array<Line> where it.length in 1 to 50
  type Policy = { limit: ids.Money, receipt_over: ids.Money, budgeted: Bool }

  fn policy_for(c: ids.Category) -> Policy
    example policy_for(ids.Category.Other) == { limit: 50000, receipt_over: 2500, budgeted: true }

  fn line_valid(l: Line) -> Bool
    example line_valid({ category: ids.Category.Feed, amount: 2500, description: "hay", receipt: false }) == true
    example line_valid({ category: ids.Category.Feed, amount: 2501, description: "hay", receipt: false }) == false
    example line_valid({ category: ids.Category.Other, amount: 50001, description: "misc", receipt: true }) == false

  fn all_valid(ls: Lines) -> Bool

… (9 more lines)
```

### brass info lines.total --if-changed



```text
$ brass info lines.total --if-changed
declaration fn total   desk.lines    interface   src/desk/lines.keel:20
  fn total(ls: Lines) -> Int
    after result >= 0
    example total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
holds       no access; cannot reach outside
direct uses  6 declarations, 7 lines
  call                 entities.cost_center_summary, forecasting.forecast, payment.pay, payment.pay_against, queries.statement, review.approve
      entities.keel:23    if r.status in {reports.ReportStatus.Approved, reports.ReportStatus.Paid} then total = total + lines.total(r.lines)
        in       fn cost_center_summary(store: host.Store, reg: registry.Registry, cost_center_id: records.CostCenterId, period: ids.Period) -> Outcome<CostCenterSummary>
        on path  no enclosing test
      forecasting.keel:22    if r.status in {reports.ReportStatus.Approved, reports.ReportStatus.Paid} then committed = committed + lines.total(r.lines)
        in       fn forecast(store: host.Store, reg: registry.Registry, department: ids.DepartmentId, period: ids.Period) -> Outcome<Forecast>
        on path  no enclosing test
      forecasting.keel:23    else if r.status in {reports.ReportStatus.Submitted} then pending = pending + lines.total(r.lines)
        in       fn forecast(store: host.Store, reg: registry.Registry, department: ids.DepartmentId, period: ids.Period) -> Outcome<Forecast>
        on path  no enclosing test
      payment.keel:22    let reference: Text = ledger.pay(r.badge, lines.total(r.lines), r.id)?
        in       fn pay(store: host.Store, ledger: host.Ledger, report_id: ids.ReportId, finance_badge: ids.Badge) -> Outcome<Text>
        on path  if who is staff.Finance then  |  if r is reports.Approved then
      payment.keel:49    let due: Int = lines.total(r.lines) - a.amount
… (12 more lines)
```

### brass info review.may_act --established-by



```text
$ brass info review.may_act --established-by
declaration fn may_act   desk.review
requires    no before clause   parameter types: store: host.Store, r: reports.Submitted, who: staff.Active
caller      queries.pending_for
  call      59: let verdict: Outcome<Bool> = review.may_act(store, r, who)
  on path   56: if who is staff.Active then  |  58: if r is reports.Submitted and r.badge != who.badge then
caller      review.gate
  call      108: let allowed: Bool = may_act(store, r, who)?
  on path   102: if who is staff.Active then  |  104: if r is reports.Submitted then  |  106: if not closed then  |  107: if who.badge != r.badge then
Static reading of the enclosing tests; whether they discharge the requirement is the checker's call.
query       q:f493dafe   cite this id; `brass verify q:f493dafe` re-runs the query and says whether the answer still holds
```

### brass info payment.pay --at 21

Facts in scope at a body line.

```text
$ brass info payment.pay --at 21
declaration fn pay   desk.payment   at 21: if r is reports.Approved then
in scope
  store: host.Store   (parameter)
  ledger: host.Ledger   (parameter)
  report_id: ids.ReportId   (parameter)
  finance_badge: ids.Badge   (parameter)
  who: staff.Finance   (narrowed from staff.Staff (test on path))
  r: reports.Report   (let at 20)
holds       store: host.Store  ledger: host.Ledger
on path     19: if who is staff.Finance then
Static reading; the checker decides what these facts prove.
query       q:931f7220   cite this id; `brass verify q:931f7220` re-runs the query and says whether the answer still holds
```

### brass info payment.pay --effects



```text
$ brass info payment.pay --effects
declaration fn pay   desk.payment
holds       store: host.Store  ledger: host.Ledger
effects     in body order; guard is every `if` test enclosing the line
  1    18  store.staff                                  unconditional
  2    20  store.report                                 if who is staff.Finance then
  3    22  ledger.pay                                   if who is staff.Finance then  |  if r is reports.Approved then
  4    23  store.save_report                            same
  5    24  store.append_audit                           same
query       q:acc5e94d   cite this id; `brass verify q:acc5e94d` re-runs the query and says whether the answer still holds
```

### brass info --if 'lines.total = fn total(ls: Lines) -> Int where it >= 1'

A static what-if.

```text
$ brass info --if lines.total = fn total(ls: Lines) -> Int where it >= 1
declaration fn total   desk.lines
today       fn total(ls: Lines) -> Int after result >= 0 example total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
proposed    fn total(ls: Lines) -> Int where it >= 1

used_by     entities.cost_center_summary  forecasting.forecast  payment.pay  payment.pay_against  queries.statement  review.approve
reaches     6 declarations in 5 modules: everything that names this or names a user of it, transitively. References, not required edits; by name, not by proof.
              entities    cost_center_summary
              forecasting forecast
              payment     pay  pay_against
              queries     statement
              review      approve

clauses to re-check   (every where/before/after in the impact set; marked by how each reaches the change)

0 clauses listed, 0 reach the change by name or through a field; the rest are in the set by reference only. This proxy does not decide which fail.
query       q:cee45991   cite this id; `brass verify q:cee45991` re-runs the query and says whether the answer still holds
```

### brass info --forms



```text
$ brass info --forms
forms       one example per form, from this project; a form absent here is not used by this code
  module header                        not used
  import with alias                    not used
  record refinement on a field         not used
  constant                             not used
  access with bounds                   not used
  enters in an expression              not used
  for over a range                     not used
  break                                not used
  interface section                    advance_desk.keel:12   interface
  private section                      advance_desk.keel:15   private
  body section                         advance_desk.keel:17   body
  type alias                           ids.keel:10   type ReportId     = Text
  type refinement (where)              advances.keel:14   type Amount  = Int where it in 1 to 1000000000
  refinement over it (numeric range)   advances.keel:14   type Amount  = Int where it in 1 to 1000000000
  record type                          advances.keel:15   type Advance = { id: ids.ReportId, badge: ids.Badge, department: ids.DepartmentId, period:
  machine                              advances.keel:7    machine AdvanceStatus
  machine states                       advances.keel:8    states  Requested, Approved, Paid, Settled
  machine initial                      advances.keel:9    initial Requested
  machine edge                         advances.keel:10   Requested enters Approved
… (22 more lines)
```

### brass review payment



```text
$ brass review payment
review      desk.payment   read in this order
1  authority   no access or allow changed
2  contracts   no signature or clause changed
3  types       no type, data, or machine changed
4  bodies      no body changed
importers   none   (brass propagate payment lists what moves)
query       q:fb443ca6   cite this id; `brass verify q:fb443ca6` re-runs the query and says whether the answer still holds
```

### brass changes

Against the baseline tree.

```text
$ brass changes
changes     none against $BRASS_BASELINE
searched     src/desk/*.brass (26 modules, declarations and bodies), matched by name; 0 qualified names unresolved
query       q:ddce3d9c   cite this id; `brass verify q:ddce3d9c` re-runs the query and says whether the answer still holds
```

### brass run lines.total '[{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }]'



```text
$ brass run lines.total [{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }]
run         lines.total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }])
result      1000 : Int
after       result >= 0   holds
One input, evaluated; not a proof. `example` clauses make an input part of the interface.
query       q:c12d2d83   cite this id; `brass verify q:c12d2d83` re-runs the query and says whether the answer still holds
```

### brass check

Level 1 structure, with the program summary when clean.

```text
$ brass check
check       src/desk/*.brass and src/system.brass: parsed, imports and qualified names resolved, declarations and bodies paired,
            calls match parameters, `?` only in fns returning `Outcome`, no `partial`, no holes, every `let` typed,
            each grant names an entry point and exactly its access parameters
not checked has-field access, state edges, contracts, refinements, argument types, termination, unused lets
result      no rejections at this level

summary     each granted entry point: the refusals, host calls, state changes, and results found in its source, in
            source order, each with the conditions enclosing it; a refusal written in an else is placed at the if that
            decides it; helpers are followed one level. Read from the text, not executed; it proves nothing.
review.open_draft holds store
      boundary  badge: ids.Badge   checked before the body runs; a failing argument is refused as InvalidInput
      boundary  period: ids.Period   checked before the body runs; a failing argument is refused as InvalidInput
    35  call     store.staff(badge)   failure passes up;   reply checked by after result.badge == badge
    36  refuse   Unauthorized   "staff member is not active"   when not who is staff.Active
        within who is staff.Active
    37    call     store.period_closed(period)   failure passes up;   reply taken on trust
    38    refuse   Conflict       "the period is closed"   when closed
          within not closed
    39      call     store.next_id()   failure passes up;   reply taken on trust
    40      call     store.save_report({ id: id, badge: badge, department: who.department, period: period, lines: [first_line], status: reports.ReportStatus.Draft, approvals: [] })   failure passes up;   reply taken on trust
… (588 more lines)
```

### brass check --examples



```text
$ brass check --examples
examples    26 found, 26 hold, 0 fail
  holds    advances.outstanding   src/desk/advances.keel:35   outstanding({ id: "a", badge: "b", department: "d", period: 2, amount: 1, status: AdvanceStatus.Paid, approvals: [], owed: 0, reference: "x" }, 5) == true
  holds    advances.outstanding   src/desk/advances.keel:36   outstanding({ id: "a", badge: "b", department: "d", period: 3, amount: 1, status: AdvanceStatus.Paid, approvals: [], owed: 0, reference: "x" }, 5) == false
  holds    audit.of_report   src/desk/audit.keel:18   of_report(reports.ReportStatus.Draft) == Step.Draft
  holds    audit.of_report   src/desk/audit.keel:19   of_report(reports.ReportStatus.Submitted) == Step.Submitted
  holds    audit.of_report   src/desk/audit.keel:20   of_report(reports.ReportStatus.Approved) == Step.Approved
  holds    audit.of_report   src/desk/audit.keel:21   of_report(reports.ReportStatus.Rejected) == Step.Rejected
  holds    audit.of_report   src/desk/audit.keel:22   of_report(reports.ReportStatus.ChangesRequested) == Step.ChangesRequested
  holds    audit.of_report   src/desk/audit.keel:23   of_report(reports.ReportStatus.Paid) == Step.Paid
  holds    audit.of_advance   src/desk/audit.keel:25   of_advance(advances.AdvanceStatus.Requested) == Step.Requested
  holds    audit.of_advance   src/desk/audit.keel:26   of_advance(advances.AdvanceStatus.Approved) == Step.Approved
  holds    audit.of_advance   src/desk/audit.keel:27   of_advance(advances.AdvanceStatus.Paid) == Step.Paid
  holds    audit.of_advance   src/desk/audit.keel:28   of_advance(advances.AdvanceStatus.Settled) == Step.Settled
  holds    lines.policy_for   src/desk/lines.keel:11   policy_for(ids.Category.Other) == { limit: 50000, receipt_over: 2500, budgeted: true }
  holds    lines.line_valid   src/desk/lines.keel:14   line_valid({ category: ids.Category.Feed, amount: 2500, description: "hay", receipt: false }) == true
  holds    lines.line_valid   src/desk/lines.keel:15   line_valid({ category: ids.Category.Feed, amount: 2501, description: "hay", receipt: false }) == false
  holds    lines.line_valid   src/desk/lines.keel:16   line_valid({ category: ids.Category.Other, amount: 50001, description: "misc", receipt: true }) == false
  holds    lines.total   src/desk/lines.keel:22   total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
  holds    records.in_force   src/desk/records.keel:63   in_force({ id: "d", delegator: "a", delegate: "b", first: 2, last: 4, revoked: false }, 4) == true
  holds    records.in_force   src/desk/records.keel:64   in_force({ id: "d", delegator: "a", delegate: "b", first: 2, last: 4, revoked: true }, 3) == false
… (8 more lines)
```

### brass show lines.total



```text
$ brass show lines.total
file        src/desk/lines.keel
  20    fn total(ls: Lines) -> Int
  21      after result >= 0
  22      example total([{ category: ids.Category.Feed, amount: 1000, description: "a", receipt: false }, { category: ids.Category.Travel, amount: 2000, description: "b", receipt: false }]) == 3000
  23  

  41    fn total(ls) =
  42      let sum: Int = 0
  43      for l in ls
  44        sum = sum + l.amount
  45      sum
  46  
query       q:9eafa5d6   cite this id; `brass verify q:9eafa5d6` re-runs the query and says whether the answer still holds
```
