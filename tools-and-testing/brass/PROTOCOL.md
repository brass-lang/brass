
## Phase 2: fewer steps, smaller conversation (added 2026-10-01, before any phase 2 session)

**Why.** Phase 1 found that cost tracks model calls times context, not what tools return: keelc calls each took their own model call (63 of 64), and the 11k-token reference is re-read on every call. Phase 2 changes what is in our control and measures the effect on the same three tasks.

**Changes.**
- **Compact reference** (`materials/KEEL-REFERENCE.K2.md`, `KC2.md`): the same rules as r24 in about 40% of the words; the full reference stays in the project as `KEEL-REFERENCE-FULL.md` for lookups.
- **Lean keelc** (`KEELC_LEAN=1`; guide `materials/KEELC.lean.md`): `check` runs structure, every example, and every scenario in one call and ends with `done` or what to fix; `show <module> …` prints declarations only, several modules per call, `--body` for the whole file; the program summary moves to `keelc summary`; no query trailer; the usage text leads with multi-name calls and "one `check` when you are done".
- **One line in the README and prompt:** read what you need first, then make the change in a few edits; for KC2, run `check` once when done.

**Arms.** K2: compact reference, no tool. KC2: compact reference and lean keelc. Python is not rerun; phase 1's P sessions are the comparison. Everything else as phase 1: tasks, hidden tables, evaluator, launcher, model `claude-sonnet-5`, cap 110, clean context.

**Sessions: 6,** A-K2, A-KC2, B-K2, B-KC2, C-K2, C-KC2, launched in two groups of three (K2 first, then KC2).

**What is measured.** As phase 1, plus: model calls, tool calls per model call, keelc calls per model call, keelc calls after the last edit, and the reference's share of input (11k × calls in phase 1, about 4.5k × calls here).

**What would count.** K2 against phase 1's K: the reference effect alone. KC2 against phase 1's KC and against K2: whether the lean tool closes the gap. Correctness must not drop: a K2 or KC2 session failing more hidden cases than its phase 1 counterpart is the first thing reported.
