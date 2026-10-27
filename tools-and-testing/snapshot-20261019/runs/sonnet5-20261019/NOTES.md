# Notes: rerun sonnet5-20261019

Run locally on the author's Mac, driven by the Claude Code session that built the rerun, at the author's request (2026-10-19); the protocol is RUNBOOK.md's.

## C group 1

- **small-KC1: the summary's 5 "edits outside apply" and 6 "leaks" are one false positive of the detectors, not a bypass or a read outside the project.** The session wrote its patch in five parts with `cat > /tmp/patchN.brass`, joined them into `/tmp/fullpatch.brass`, and applied the whole patch in one `bin/brass apply`; every change to `src/` went through `apply` (transcript). The bypass detector matched a shell redirect and `src/` inside the patch text; the leak scan matched the session's own scratch files under `/tmp`, which it wrote and read back. Nothing outside the project was read. `run.py` is frozen for the run and is not changed; the analysis reclassifies from the transcripts, which keep every call. Whether a session's own `/tmp` scratch counts against the standing leak rule is for the author; recorded here, not acted on.

## C group 2

- **grown-KC1: the same false positive as small-KC1.** Five patch parts staged with `cat > /tmp/patchN.txt`, joined, applied through `bin/brass apply` (two `apply` calls); no Edit or Write call; nothing outside the project read. Recorded, not acted on.

## C groups 3 to 5

- **Every tool-arm session staged its patch in `/tmp` before `apply` except one,** and the stray scratch files stay in `/tmp` between groups (author, 2026-10-19: no cleanup during the run). After every group, every transcript is checked for a read of a `/tmp` file the session did not write itself; none so far.
- **grown-KC2 (group 4): 120 of 122 on task C, failing V17 and V40,** a report's approval that does not count advances against the budget, stage 1's "missed site" variant. Final check clean; one `apply`; no direct edit.
- **small-KC3 (group 5): the first bypass of `apply`.** Seven files written with Write and `system.brass` changed with Edit; no `apply` call; one `brass check` at the end, clean. Held every case. Recorded, as decided (author, 2026-10-19): `apply` recommended, a bypass documented.

## C group 6

- **grown-KC3: a near miss with a leftover scratch file, no contamination.** It built its patch in `/tmp/patch.txt`, a name small-KC2 (group 3) had already used and left behind. Its first write was `cat > /tmp/patch.txt` (overwrite; 45 lines, all its own), then six appends of its own blocks, two `apply` calls (the first rejected 33 lines, the second written). The leak scan's `/tmp` entry is a `cd /tmp` to edit that same file. Had its first write been an append, small-KC2's patch would have been prepended unseen. Recorded, not acted on (author, 2026-10-19).

## C group 7

- **small-KC4: the second bypass of `apply`.** Files written with Write and Edit; no `apply` call; `brass check` at the end, clean. Held every case.

## C groups 8 to 10

- **grown-KC5 (group 10): a partial bypass.** Three `apply` calls, then one direct Edit of `queries.brass`; final check clean; held every case. The summary also lists the three `apply` heredocs as edits outside `apply`: a false positive of the shell-write check, which reads the `->` arrows in the patch text as a redirect. The analysis counts direct Edit and Write calls on `src/` from the transcript, not this list.
- **Task C complete:** 30 sessions, 29 held every case (grown-KC2, V17 and V40). Tool arm: two full bypasses (small-KC3, small-KC4) and one partial (grown-KC5) in ten sessions; the other seven used `apply` alone, six of them staging the patch in `/tmp` first. No session read a `/tmp` file another session wrote.

## D group 1: stopped

- **D/P1 and D/KC1 ended in an error result after 33 and 10 turns ($0.37 each), 10 of 81 on task D:** a harness failure, not a result. Both are retry candidates under the protocol (one retry each). The run was stopped here when the driving session's usage limit was reached, 2026-10-19; task D groups 2 to 5 have not run.

## D group 1, retry: stopped (author, 2026-10-19)

- **Both retries (attempt 2) were stuck for three hours and were stopped, not completed.** Launched 12:53Z. From 13:03Z on, the Mac went to sleep; each session's stream was cut ("Connection lost while your computer was asleep", watchdog `StreamSuspended`) and retried roughly every sixteen minutes without progress: P1 reached 33 tool calls, KC1 9. The author stopped the watch at about 15:58Z; the two processes were ended at 16:02Z. Their transcripts are kept under `attempt-2/`. Neither is a result. Under RUNBOOK.md each session has used its one retry; whether task D group 1 runs again is the author's call.
- **Task C, group 4, for the analysis:** grown-P2, small-K2, and grown-KC2 each hit rate-limit replies (429) during the run and retried them; all three finished. grown-KC2 is the one task C session that missed cases (V17, V40). Their elapsed time and cost include the retries.
- **Why there was no update for two hours:** the watcher reported only on completion and had no ceiling. A session that stalls looks the same as one still working.

## Task D moved to its own run (author, 2026-10-19)

Task D is run again in full under `sonnet5-20261019-d`, on the same frozen inputs; only the run id in each prompt's tag differs. This run keeps task C's 30 sessions as its result, and task D's failed attempts as records. No session of task D in this run is a result.

## Report

The combined report for both run ids is `../sonnet5-20261019-d/REPORT.md`.
