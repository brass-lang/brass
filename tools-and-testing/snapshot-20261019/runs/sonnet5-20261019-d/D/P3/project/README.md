# desk

Expense desk for Jurassic Park. Staff file expense reports and request cash advances against their department's budget; approvers sign them off by amount; InGen's ledger pays them. Python 3.12, standard library only.

- Source: `src/desk/`. Entry points are the public functions of `review`, `payment`, `queries`, `delegation`, `purchasing`, `cards`, `allowances`, `entities`, `reporting`, `vendors`, `card_limits`, `readiness`, `exceptions`, `forecasting`, each a module under `src/desk/`.
- The outside services are `Store` and `Ledger`, and `Registry` for the added subsystems, declared as protocols and passed to every entry point that uses them. The host implements them; nothing else reaches outside.
- A refusal raises `errors.Failure` with a `FailureCode`.
- The project has no tests. You may run `python3` and write your own tests anywhere under this directory.
