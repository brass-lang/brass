# Brass test snapshot, 2026-10-19

This folder holds the 40 Sonnet sessions behind the published comparison of Brass and Python. Models made two changes to an expense-report program: adding cash advances, on a small codebase and one 2.5 times larger, and adding trip plans.

Each session's prompt, transcript, finished program, tool log and scores are under `runs/`. Frozen inputs and tools record how the sessions were built. The results appear in *The Token Efficiency of Brass*, with summaries in the repository's README and HISTORY.

The snapshot reran the earlier scale and trip-plan trials on the Brass version frozen here. The original trials remain separate private records.

**Status:** inputs were frozen on 2026-10-19, and all 40 Sonnet sessions ran that day (`runs/sonnet5-20261019` and `-d`). An Opus spot check ran on the 17th. `tools/run.py` selects `claude-sonnet-5` at high effort. The trip-plan trial used the frozen tool in `tools/brass-lean8/`.

Scripts retain the private repository's paths, including the runner's dependency on `validation/tools/`. They document the original run and cannot run unchanged from this public layout. Editing them would invalidate the hashes below.

## The three scenarios

| Scenario | Arm | What the session gets | What it does not get |
|---|---|---|---|
| **Python** | P | the Python codebase and its README; `python3`; may write its own tests | no map, no host contract |
| **Brass, language only** | K | the Brass codebase and its README; the compact and full editing reference (r33) | nothing checks or runs; no map, no host contract, no `bin/brass` |
| **Brass** | KC | the same, plus `bin/brass` at lean 8, the project map, the host contract, and (task D) `converters.txt` | |

All setups used Sonnet 5 at high effort, the same task text and budget line, and the same file tools (`Read, Edit, Write, Glob, Grep, Bash`). Each session started in a cleaned environment with its own tag at the top of the prompt.

KC prompts required edits through `brass apply`. Unlike stage 1, the harness did not prevent edits outside it; it counted them as `edits_outside_apply`.

## Layout

| Task | Sessions | Groups (a group starts when the one before is collected) |
|---|---|---|
| C, small and grown | P, K, KC × 2 sizes × 5 = 30 | ten groups of three, stage 1's order extended |
| D | P, KC × 5 = 10 | five groups of two |

Records live under `runs/<run-id>/<task>/<label>/`. A new run gets a new id and never overwrites an earlier one. A session's record holds its prompt, result, transcript, finished project, the tool's own call log, the environment-variable names before and inside the cleaned environment, and `summary.json`.

## What a session's summary records

- **Identity:** run id, task, label, arm; `session_id`, and `own_instance` (not the launching session's id, not another session's).
- **Provenance:** model, effort, cap, Claude Code version, git commit, the frozen tool's hash, the prompt's hash and length, and the whole freeze table.
- **Cost:** dollars, cache reads, cache writes, uncached input, output and reasoning tokens, turn count, and elapsed time.
- **Model calls:** context size at the first, second and last call, plus the sum across calls and fresh input. The transcript also supplies tool-call counts, shell commands grouped by first word, files read, edits and tool errors.
- **Brass tool use** (KC): commands from the tool log, `apply` calls, edits outside `apply`, reasoning before the first edit, and the final `check` result and warnings.
- **Correctness:** every case table, with failed case ids and counts by kind. Task C: `C.json`, `baseline.json`, and `grown.json` at the grown size. Task D: `D.json` (81, D33 scored), `baseline.json`, `C.json`, `grown.json`.
- **Hygiene:** paths read or written outside the session (`leaks`), with the harness's own scratch and tool-result paths listed apart (`harness_paths`).

## What changed from stage 1

| Input | Stage 1 | Rerun | How |
|---|---|---|---|
| Brass trees (2 baselines, 4 references) | Keel before C25 | current Brass | `tools/respell.py`: C25 `partial fn` → `fn`; C31 `private interface` → `private`; C33 bare `where` fields → `it.field`; C34 `has` → a `when` field; `.keel` → `.brass` |
| Grown references | patch applied at validation time | same patch, then respelled | 17 and 14 hunks for C, 14 and 4 for C-alt, none rejected |
| Compact references (K, KC) | r24 compact, 2,747 / 2,815 words | r33 compact: trial 29's edition (its header corrected), one copy per arm with that arm's run line | `tools/port_materials.py` |
| Full reference | r24, one copy with arm K's run line | r33, one copy per arm with that arm's run line | same script |
| Tool brief and opening | lean 3's | lean 8's, from trial 29 | copied; shared with task D |
| Reference r29 → r30 | | three sentences corrected to the spec, found by the rerun's outside audit | an `is` test, not `in`, gives a named type (spec §7.2); a contract proved from an enforced fact reports enforced (§6); an `allow`'s `after` is checked on every *successful* reply (§8.3). The compact editions carried the last two; r29 the first and third |
| Brief, opening, READMEs, map, host contract | Keel, `keelc` | Brass, `brass` | names only |
| Python trees, case tables, task text, Python READMEs | | unchanged | byte-identical |
| Tool | stage 1's `keelc`, lean 3 | `tools/brass-lean8/`, a frozen copy of the live stand-in at lean 8 | about 350 changed lines: the language decisions, nine audit fixes, `std.text.of`, a refined access counted as an access, converter coverage (inactive here: no tree has `converters.txt`), and an unadvertised `monkey` verb that prints one line |
| Case scorer, builder | stage 1's | ported: 16 and 26 changed lines, the diff hash asserted by the audit | tool path, settings, file names. **The case tables and comparison logic are unchanged; the engine that runs a Brass tree is not.** The current evaluator enforces two rules the frozen one let pass: a `when` field missing from an update that enters its state, and integer overflow. A session's patch that trips either scores lower than it would have in stage 1 |
| Launcher | `claude-sonnet-5` fixed; effort the harness default (high); the launching shell's environment | `claude-sonnet-5` at `--effort high`, passed by `tools/run.py`; a cleaned environment (`env -i` with PATH, HOME, USER, LANG, TMPDIR, TERM, CLAUDE_CONFIG_DIR, ANTHROPIC_*) | |
| Task D inputs | the Stage 2 trial's | `D/`: its start trees, stage 2's cases and reference, trial 29's materials, stage 2's task text with the D33 rule; its evaluator and variants ported | byte-identical where copied; the audit checks each |

## Known differences that affect comparison

- **The prompt is longer.** K and KC prompts grew about 5% (20,655 → 21,707 characters; 24,082 → 25,137 small KC), from the rules added since r24.
- **The tool is not the same tool.** Lean 3's verbs, patch format, and check sections are unchanged (verified); its rules and some outputs are not.
- **The build path.** Stage 1 built sessions under a path containing the repository's name, and each prompt carried it. Build the rerun in a neutral folder: `/tmp/rerun-<date>/`.
- **r30 predates C44.** Its sentence "Only `x is T` gives a value a named type" is C20 (b)'s older wording; C44 rewrote it in the spec without changing behavior. The references keep r30's words.
- **C34 restricts what a new program may write** (a `when` field's controller must be unconditional and its type named). The starting trees satisfy it; a session's new code must too, where stage 1's did not have to.
- **Cache conditions affect dollar cost** even when the program is unchanged. Each session's cost is recorded beside its tokens; compare arms within the rerun, and tokens before dollars.
- **The model is stage 1's, pinned.** Stage 1 ran `claude-sonnet-5` at effort high on Claude Code 2.1.285 (from its transcripts), with effort the harness default; the rerun passes `--effort high`. The Opus run of 2026-10-17 (`runs/opus55-20261017/`) is a spot check, not an arm. The rerun's arms compare with each other; comparisons with stage 1's numbers carry every difference in this list. `runs/<run-id>/preflight.json` records the Claude Code version, platform, Python version, and git commit; each summary carries them.
- **The scoring engine for task D** is the Stage 2 evaluator after its three scoring-only fixes, and D33 is scored (the task text now decides it); the Stage 2 trial set D33 aside.
- **Task D is a reused task.** It was held out for the Stage 2 trial; since then its sessions were diagnosed and the reference changed in response (r32, r33). The write-up says so.
- **The references are r33, three revisions past the Stage 2 trial's r31**: `std.text`'s `of`, the facts that prove a range (C47), and the three r30 corrections.
- **Thinking is measured.** The harness now reports `thinkingTokens` per session; stage 1's reasoning was estimated as output minus visible output.

## The hand-read

`RUBRIC.md` was frozen before the run. It covers checks the behavioral cases and stand-in miss: conditional-field reads and literals, converter registration, weakened declarations, the two audit reasons, write order and invented operations.

Reviewers scored three categories separately without seeing setup labels or costs. Their scores are recorded in `runs/<run-id>/handread.json`.

## Not isolated by this design

Sessions do not inherit the launching session's identity or settings. The records detect shared session ids, identify the model that answered, and flag absolute paths outside the session in tool inputs.

This does not establish complete isolation. A tools-and-system prompt prefix may still share a cache between sessions. The leak scan also cannot detect every file or network read made inside a script. It inspects recorded calls after execution; it does not block access.

## How to run

The original runner, `tools/run.py`, records the protocol under `runs/<run-id>/`. `RUNBOOK.md` contains the instructions for the cloud session that drove it. The commands below retain private-repository dependencies. The build comment says 18 sessions; the completed protocol above ran 40.

```sh
# from pub-repo/
python3 tools-and-testing/snapshot-20261019/tools/run.py preflight <run-id>    # tools, sign-in, model, audit, freeze
python3 tools-and-testing/snapshot-20261019/tools/run.py build <run-id>        # the 18 sessions, in /tmp/rerun-<run-id>/
python3 tools-and-testing/snapshot-20261019/tools/run.py launch <run-id> C 1   # a group, in the background; D 1 to D 5 after C 1 to C 10
python3 tools-and-testing/snapshot-20261019/tools/run.py wait <run-id> 8       # up to eight minutes; repeat until none is running
python3 tools-and-testing/snapshot-20261019/tools/run.py collect <run-id>      # record, score, check each finished session
```

Task C uses stage 1's group order: first small-P1, grown-K1 and small-KC1; then grown-P1, small-K1 and grown-KC1. The pattern repeats for sessions 2 to 5, followed by task D's five groups. Each group starts after the previous group is collected.

A session ending in a harness failure may be retried once (`run.py retry`). A completed session counts as a result regardless of its score.

Task C sessions are scored on `C.json` and `baseline.json`, plus `grown.json` at the grown size. Task D sessions are scored on `D.json`, `baseline.json`, `C.json` and `grown.json`. The private repository's `tools/scrub-public.py` prepares `runs/` for publication.

## Validation

`python3 tools/audit.py` regenerates every input from its frozen source and re-runs every check, twelve sections. 2026-10-19: **PASS, 0 failures.**

| Check | Result |
|---|---|
| Every Brass tree, grown reference, and material regenerates byte for byte | yes |
| Python trees, cases, task text identical to stage 1 | yes |
| No retired spelling left in the Brass trees; bare `where` fields are the tool's to find (see the control row) | none |
| Current `brass check`, lean 3, host contract, all six trees | clean; every `example` holds |
| Control: the current tool on stage 1's grown tree | rejects 49 `partial`, 4 `private interface`, 1 `has`, 31 bare fields |
| Case tables | 22 runs, 11 per language, every case holds: 82, 112, 122 as stage 1 |
| Planted-wrong variants | 22 of 22 caught |
| Agreement with stage 2's hand respelling | exactly the 22 modules stage 2 left alone, named in the audit, identical |
| Ported tools | the diff from stage 1 has the approved hash; every deleted line is a name, path, setting, or comment |
| Built sessions | no old name in any prompt; every prompt opens with its session tag; each KC project's own check clean |
| The frozen tool | byte-identical to the live stand-in it was frozen from |
| Task D | start trees, cases, task text, materials identical to their sources; both references hold 81, 82, 122, 112; 14 of 14 planted variants caught |

## Frozen 2026-10-19

The table shows the first 16 hexadecimal characters of each SHA-256 hash. Folder hashes cover sorted paths and contents. A change after the first session must be recorded as a protocol event.

| What | Path | Hash |
|---|---|---|
| live stand-in | `tools-and-testing/brass/bin/brass` | `1e611b1327ba33d3` |
| live evaluator | `tools-and-testing/brass/bin/brasseval.py` | `c6936b3bfc179282` |
| case evaluator | `tools-and-testing/snapshot-20261019/tools/evaluate.py` | `753e74281565ae52` |
| session builder | `tools-and-testing/snapshot-20261019/tools/build.py` | `215a37b0764cb9d0` |
| launcher | `tools-and-testing/snapshot-20261019/tools/launch.sh` | `72d3b2edcc748c25` |
| runner | `tools-and-testing/snapshot-20261019/tools/run.py` | `854a93192a38d849` |
| variants | `tools-and-testing/snapshot-20261019/tools/variants.py` | `15295894f63c7312` |
| respeller | `tools-and-testing/snapshot-20261019/tools/respell.py` | `9af47db8a46e5511` |
| material port | `tools-and-testing/snapshot-20261019/tools/port_materials.py` | `df257bb6eeff9b60` |
| frozen tool lean 8 | `tools-and-testing/snapshot-20261019/tools/brass-lean8` | `3a2d086df0fcc20b` |
| task d builder | `tools-and-testing/snapshot-20261019/tools/build_d.py` | `9401f9a2b2624d68` |
| task d evaluator | `tools-and-testing/snapshot-20261019/tools/evaluate_d.py` | `1c0627a9b48a60c1` |
| task d variants | `tools-and-testing/snapshot-20261019/tools/variants_d.py` | `b3e201eab181c8a1` |
| cases | `tools-and-testing/snapshot-20261019/cases` | `eed967342bfa8c3b` |
| materials | `tools-and-testing/snapshot-20261019/materials` | `234607275a4e57bc` |
| baselines | `tools-and-testing/snapshot-20261019/baseline` | `37e9e7815c64d173` |
| references | `tools-and-testing/snapshot-20261019/reference` | `e96c7d75cebcc572` |
| task d inputs | `tools-and-testing/snapshot-20261019/D` | `90d0403c71563f04` |
