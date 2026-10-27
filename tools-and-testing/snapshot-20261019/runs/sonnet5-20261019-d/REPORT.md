# Report: the rerun, tasks C and D on Sonnet 5

Two run ids, one protocol: task C's 30 sessions are `sonnet5-20261019`; task D's 10 are `sonnet5-20261019-d`, run again after that run's task D attempts failed (a usage limit, then the Mac's sleep). `claude-sonnet-5` at effort high, Claude Code 2.1.302, the frozen inputs of `rerun/README.md`, run locally on 2026-10-19. Every session answered by Sonnet 5 and its own instance. Nothing here is interpreted; the hand-read (`RUBRIC.md`) has not been done.

## By cell (means of five sessions)

| Task, size, arm | Every case held | Cost | Cumulative input | Thinking | Turns |
|---|---|---|---|---|---|
| C small, Python | 5 of 5 | $1.26 | 2.72M | 21k | 47 |
| C small, Brass no tool | 5 of 5 | $1.65 | 3.35M | 39k | 42 |
| C small, Brass with tool | 5 of 5 | $1.03 | 0.98M | 38k | 13 |
| C grown, Python | 5 of 5 | $1.75 | 3.96M | 32k | 62 |
| C grown, Brass no tool | 5 of 5 | $2.13 | 4.62M | 51k | 56 |
| C grown, Brass with tool | 4 of 5 | $1.32 | 1.72M | 43k | 19 |
| D, Python | 5 of 5 | $2.42 | 5.97M | 46k | 68 |
| D, Brass with tool | 4 of 5 | $2.08 | 2.66M | 79k | 23 |

Cumulative input is input tokens summed over every model call, cached included; it is not source read.

## Misses

- **C grown-KC2:** 120 of 122 on task C, V17 and V40 (a report's approval not counting advances against the budget). Its run hit rate-limit replies and retried them.
- **D KC1:** 79 of 81, D67 and D68 (a repeated reconciliation's audit).

## `apply` in the tool arm (15 sessions)

| | Task C small | Task C grown | Task D |
|---|---|---|---|
| `apply` only | 3 | 4 | 3 |
| `apply` and a direct edit of `src/` | 0 | 1 (grown-KC5) | 1 (KC3) |
| no `apply` at all | 2 (small-KC3, small-KC4) | 0 | 1 (KC5) |

Every session with a direct edit ran `brass check` at the end, clean, and held every case. Seven `apply`-only sessions staged their patch in `/tmp` first. The runner's `edits_outside_apply` list over-counts: it reads `->` in a patch heredoc as a redirect, and a write to the session's own scratch file as an edit; this table counts Write and Edit calls on `src/` from the transcripts.

## Hygiene

- No session read a `/tmp` file another session wrote; one (C grown-KC3) reused a leftover name and overwrote it first.
- Task C group 4's three sessions hit rate-limit replies (429) and retried; their time and cost include the retries.
- Task D group 1 in `sonnet5-20261019` is on record as failed: the usage limit, then three hours stalled while the Mac slept.

## Hand-read (RUBRIC.md), 2026-10-19

Forty sessions, read blind by eight reader agents (five each), each session under a random number with only its code; the readers had the task text, rubric, spec, host contract, and starting trees, and none had scores, labels, or costs. Rows: `handread.json` in each run; the key beside them, opened after every row was in. Findings that change a verdict or implicate the tool were checked against the code before the key was opened.

### Legality (Brass, items 1, 2, 4)

| | Sessions failing | Which |
|---|---|---|
| 1. `when` reads under a test that fixes the state | 0 of 25 | every read sits under an `is` or state test; reads of `owed` in an `after` to the right of `status in {Settled} and` counted as tested (§7.2: a test joined by `and` narrows) |
| 2. Literals: no invented non-initial state | 1 of 25 | C grown-K4 (`queries.brass:38-39`): a statement row for an advance built with a report state |
| 4. Loosened declarations | recorded, not failed | every task C Brass session moved the audit states to a shared `Step` vocabulary (C22, C46), the decided pattern, not loosening; real loosening: D KC4 (`Entry.reason` to `Text`), D KC2 (a local reason to `Text`), C small-KC4 (a helper gave up its `reports.Submitted` parameter) |
| 3. New converter registered (task D) | 0 of 5 listed | no session added `audit.of_trip` to `converters.txt`; `check`'s converter coverage never saw it. Nothing told them to |

### Requirements (task D, items 5 to 7; and item 8 for all)

| | Result |
|---|---|
| 5. Overage reason says so | 10 of 10 |
| 6. Early close carries Finance's reason | 10 of 10 |
| 7. Write order on reconcile | 10 of 10 |
| 8. Nothing invented | 39 of 40: C grown-K4 borrows the report machine's states for an advance (the same line as item 2) |

### Beyond the rubric

- **A repeated reconciliation's audit (task D).** Every Python session compares the whole reconciliation, counted transactions included, to decide whether a repeat is audited; every Brass session compares the amount and report (one also the number of transactions), never which transactions. A repeat that changes only the counted transactions is saved and not audited in all five Brass sessions. No case tests it. The task says a repeat "is audited only when its result differs from the one it replaces".
  **Decided 2026-10-19 (author): set aside, as D33 was.** The task does not say what a reconciliation's result contains, so a session that compares the amount and report has not broken a stated rule. Scores stand. The difference is reported as a habit, by arm: Python's comparison of whole values took in the transactions by default; every Brass session chose the fields by hand and left them out. Which fields make up the result is not yet decided; when it is, the task text says so before task D is used again.
- **The statement's row bound (task C).** Several Brass sessions kept `Rows` at 1000 while a statement can now hold 1000 report rows and 1000 advance rows; others raised it to 2000. A prover would reject the unraised bound; no case builds a statement that large.
- **Two gaps in the stand-in, confirmed by running the frozen tool's `check`:** C small-KC4 uses the keyword `as` as a parameter name (spec §2.3), and D KC3 declares `access Ledger` twice; both `check`s are clean. Both trees were written without `apply`.
- **The hand-read and the cases agree where both look:** the reader found, by reading, that C grown-KC2's final approval counts reports only, which is what V17 and V40 failed.
- **Python, one probable defect:** D P1's advance approval lowers a trip's commitment by the advance amount, undercounting spend; no case caught it.
- **The starting tree for task D** builds an advance in `Paid` inside two `example` lines (`advances.brass:35-36`), a non-initial state in a literal; every task D session inherited it and the stand-in never flagged it.
