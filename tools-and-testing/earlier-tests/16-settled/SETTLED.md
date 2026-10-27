PATTERN: A FIELD THAT HOLDS A STATE OF ONE OF SEVERAL MACHINES

Keel has no type for "a state of either of these machines". When one field must record a state from more than one machine, declare a shared vocabulary of state names and one converter per machine into it. Keep the record's other fields as they are.

```keel
# desk/audit.keel — the pattern
type Step = Draft | Submitted | Approved | Rejected | ChangesRequested | Paid | Requested | Settled

fn of_report(s: reports.ReportStatus) -> Step
  example of_report(reports.ReportStatus.Paid) == Step.Paid
fn of_advance(s: advances.AdvanceStatus) -> Step
  example of_advance(advances.AdvanceStatus.Settled) == Step.Settled
```

A field that held one machine's state now holds a `Step`. Callers convert at the call site: `audit.of_report(reports.ReportStatus.Approved)`. Do not widen the field to `Text`, and do not add a host operation; the host's operations and record fields stay as they are.
