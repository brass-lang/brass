# Notes: rerun sonnet5-20261019-d

Task D only, run again in full after `sonnet5-20261019`'s task D attempts failed (a usage limit, then the Mac's sleep; that run's notes). Same frozen inputs; only the run id in each prompt's tag differs (author, 2026-10-19). Task C is built here, as the runner builds both tasks, and not run.

Run locally with the Mac held awake (`caffeinate -dimsu`, on mains power), and a watcher that reports every ten minutes and alarms on a connection or rate-limit error or a session past 45 minutes.

## D group 1

- **P1 held every case; KC1 79 of 81, failing D67 and D68** (a repeated reconciliation's audit). KC1 used `apply` once, no direct edit; final check clean. No connection or rate-limit error in either session.

## D groups 2 and 3

- **P2, KC2, P3, KC3 held every case.** No connection or rate-limit error; no read of another session's scratch file.
- **KC3: a partial bypass.** `trips.brass` and `trip_desk.brass` written with Write, one Edit of `trip_desk.brass`, then two `apply` calls; final check clean. The summary's list also names the two `apply` heredocs, the `->` false positive recorded in `sonnet5-20261019`'s notes.

## D group 4

- **P4 and KC4 held every case.** KC4 used `apply` three times and made no direct edit; the summary's three "edits outside apply" are those `apply` heredocs (the `->` false positive).

## D group 5

- **P5 and KC5 held every case. KC5 made no `apply` call:** 5 Write and 6 Edit calls on `src/`, `brass check` three times, the last clean. Run complete; `REPORT.md`.

## The repeat rule (author, 2026-10-19)

The transaction-only repeat (no audit when only the counted transactions change; all five Brass sessions) is set aside as a rule the task did not decide, as D33 was. Scores stand; the habit is reported by arm in REPORT.md. Open: which fields make up a reconciliation's result, to be stated in the task text before task D is used again.
