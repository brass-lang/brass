# desk

Expense desk for Jurassic Park. Staff file expense reports against their department's budget; approvers sign them off by amount; InGen's ledger pays them. Written in Brass.

- Source: `src/desk/`. `src/system.brass` lists the entry points and the accesses each one is granted; they live in `review`, `payment`, `queries`, `delegation`, `purchasing`, `cards`, `allowances`, `entities`, `reporting`, `vendors`, `card_limits`, `readiness`, `exceptions`, `forecasting`, `advancing` (cash advances; the records are in `advances`).
- The outside services are `Store` and `Ledger`, and `Registry` for the added subsystems, declared as accesses. The host implements them; nothing else reaches outside.
- A refusal is an `Err` with a `FailureCode`.
- The language: `BRASS-REFERENCE.md` (compact). `BRASS-REFERENCE-FULL.md` has every rule, if one is missing.
- Nothing compiles, checks, or runs in this project.
