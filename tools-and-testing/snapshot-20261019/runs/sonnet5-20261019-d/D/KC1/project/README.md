# desk

Expense desk for Jurassic Park. Staff file expense reports and request cash advances against their department's budget; approvers sign them off by amount; InGen's ledger pays them. Written in Brass.

- Source: `src/desk/`. `src/system.brass` lists the entry points and the accesses each one is granted; they live in `review`, `payment`, `advance_desk`, `queries`, `delegation`, `purchasing`, `cards`, `allowances`, `entities`, `reporting`, `vendors`, `card_limits`, `readiness`, `exceptions`, `forecasting`.
- The outside services are `Store` and `Ledger`, and `Registry` for the added subsystems, declared as accesses. The host implements them; nothing else reaches outside.
- A refusal is an `Err` with a `FailureCode`.
- The language: `BRASS-REFERENCE.md` (compact). `BRASS-REFERENCE-FULL.md` has every rule, if one is missing.
- `bin/brass` reads, edits, and checks the project.
