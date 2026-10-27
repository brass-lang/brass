# Hand-read rubric

Frozen before the run (author, 2026-10-19). What a reader checks in every session's finished tree that the cases and the stand-in do not check, how each item is scored, and how the results are kept. The reading happens after the run; this page does not change once a session has run.

**Blind, as far as it can be.** The reader works from `project/` alone, with the session's label replaced by a number, and sees no cost, no turn count, no score, and no transcript. The language is visible in the code; that is as blind as this gets.

## Three columns, kept apart

| Column | What it holds | Who decides |
|---|---|---|
| **Cases** | the case tables' counts, as `summary.json` records them | the evaluator |
| **Legality** | rules of the language the stand-in does not check | the reader, items 1 to 4 |
| **Requirements** | explicit requirements of the task text the cases do not test | the reader, items 5 to 8 |

A session's result is reported as three numbers, never one. "Passed" on its own means all three columns clean.

## Legality: Brass sessions only

Every item lists what to find, what passes, and what to write down. A finding is a file and line, never a judgment alone.

**1. `when` field reads.** List every read of a conditional field (`reference`, `actual`, `reconciliation`, and any the session added; find them from each record type's `when` lines). For each read, name the enclosing test. **Passes** when the test on the path establishes a state in which the field exists (spec §9.4). **Fails** when the field is read with no test, or under a test that does not fix the state.

**2. `when` fields in record literals.** List every record literal that names a conditional field or a non-initial state. **Passes** when the literal's state is one the field exists in, and the state is the machine's initial state or a value obtained legitimately (spec §9.2). **Fails** otherwise.

**3. Converter registration (task D, tool arm).** Every new `Step` converter (`of_trip` or its equivalent) must be listed in `converters.txt`, or `check`'s coverage never saw it. **Record** listed or not listed. The task did not say to list it; a not-listed converter is a finding about the brief, not a failure of the session. Report the count.

**4. Loosened declarations.** Any typed field or parameter changed to `Text`, `Int`, or a wider type than the starting tree declared. **Record** each with its old and new type. Lean 8 warns on these; the reader confirms the warning list and adds any it missed.

## Requirements: every session, both languages

**5. The overage reason.** The task: when the actual amount exceeds the committed one, the reconciliation's audit reason says so. **Passes** when a reader can tell from the reason text alone that the actual exceeded the committed. **Record** the text.

**6. A closed trip's reason.** Finance may close a single trip early, with a reason. **Passes** when the audit entry for an early close carries the reason Finance gave. **Record** the text.

**7. Order of writes.** Every check and refusal before the first write; reconciling saves the trip once, then writes its audit entry; a failed save returns the failure with no audit attempted. The cases exercise this; the reader confirms it in the code's order. **Record** pass or fail with the line.

**8. Nothing invented.** No host operation the contract does not list, no state reused from another machine, no `Text` standing in for a state. **Record** each occurrence.

## Task C sessions

Items 1, 2, 4 and 8 apply. Items 5 to 7 do not. Item 3 does not.

## How the sheet is kept

One row per session in `runs/<run-id>/handread.json`, written by the reader:

```json
{"number": 7, "legality": {"when_reads": [], "when_literals": [], "converters_listed": null, "loosened": []},
 "requirements": {"overage_reason": "…", "closed_reason": "…", "write_order": "pass", "invented": []},
 "notes": ""}
```

The mapping from number to label is sealed in `runs/<run-id>/handread-key.json`, written at the start of the reading and opened only after every row is in. An item that cannot be decided from the tree is `"undecidable"` with a note, never a guess.

## What this rubric does not do

It does not rescore a case, and it does not weigh one column against another. Whether a legality finding should have been a rejection is a finding about the stand-in, recorded in the write-up beside the result.
