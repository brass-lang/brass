You are running a frozen trial, unattended. Nobody will answer questions. Follow these steps exactly, record everything, and stop and report rather than improvise. Your job is to run the protocol correctly, not to improve it.

**What this is.** `pub-repo/tools-and-testing/snapshot-20261019/` holds 40 headless Claude sessions: 30 make one change ("task C") to a codebase in Python or in the Brass language at two sizes, and 10 make a second change ("task D") to a larger codebase. `pub-repo/tools-and-testing/snapshot-20261019/README.md` describes it. `pub-repo/tools-and-testing/snapshot-20261019/tools/run.py` does every step; you drive it and check its output. You do not write code, edit inputs, or judge the sessions' work.

## Rules

- **Change nothing** under `pub-repo/` except new files in `pub-repo/tools-and-testing/snapshot-20261019/runs/<RUN_ID>/`. Never edit a tool, input, case table, or the README. A preflight that fails on a freeze mismatch means something changed; stop.
- **Never rerun a session that finished,** whatever it scored. A low score is a result.
- **Never change the model, effort, cap, or group order.** They are fixed in `run.py`.
- **Do not open, read, or touch the session projects under `/tmp/rerun-<RUN_ID>/` while sessions run,** and do not use subagents.
- **Stay active until the run is done.** Never end your turn while a session is running. Each `wait` call returns within eight minutes; call it again.
- **Scrub, then commit and push after every step that writes to `runs/`,** so nothing lives only on this machine and no transcript carries the account's email or home path:
  `python3 tools/scrub-public.py pub-repo/tools-and-testing/snapshot-20261019/runs/<RUN_ID> && git add pub-repo/tools-and-testing/snapshot-20261019/runs && git commit -m "rerun <RUN_ID>: <step>" && git push`
  The scrub must print `0 with a form remaining`; if it does not, stop and report.
- **When you stop early,** write `pub-repo/tools-and-testing/snapshot-20261019/runs/<RUN_ID>/NOTES.md` saying what happened, with the exact output, then commit, push, and end with that summary.

## Steps

All commands run from the repository root.

**1. Set the run id and check the tools.** `RUN_ID=sonnet5-$(date -u +%Y%m%d)`. If `claude --version` fails, install it with `npm install -g @anthropic-ai/claude-code`, then check again.

**2. Preflight.** `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py preflight $RUN_ID`. It checks the tools, signs in a one-line test session on `claude-sonnet-5` in the cleaned environment and confirms it is its own instance, runs the full input audit, and compares the freeze table. Commit and push. Then:
- `ok True`: go on.
- `auth_ok False`: stop. Report the `auth_error` text and say the environment probably needs `ANTHROPIC_API_KEY` set for the nested sessions.
- `model_ok False`: stop. Report which model answered.
- `probe_own_instance False`: stop. The test session carried this session's id; report `parent_session_id` and `probe_session_id`.
- `audit_pass False` or `freeze_match False`: stop. Report `runs/<RUN_ID>/audit.txt` and the mismatched rows.

**3. Build.** `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py build $RUN_ID`. It must print 40 sessions, 30 under C and 10 under D. Commit and push.

**4. Run the groups, in order: task C's ten groups, then task D's five.** For task `T` in C then D, and `G` from 1 to 10 (C) or 1 to 5 (D):
1. `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py launch $RUN_ID T G`. It must print three launches for C, two for D.
2. Repeat `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py wait $RUN_ID 8` until no session shows `running`. A session may take up to an hour.
3. `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py collect $RUN_ID`.
4. For each of the group's sessions, read `runs/<RUN_ID>/<T>/<label>/summary.json` and check:
   - `model_ok` true, `transcript_saved` true, `own_instance` true. If any is false, note it in `NOTES.md` and go on.
   - `leaks` empty. A non-empty list means the session read or wrote a path outside its project (the harness's own scratch paths are listed separately under `harness_paths` and are fine); note every entry in `NOTES.md` and go on.
   - `is_error` false. If true, or if `collect` said a session "ended without a result", run `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py retry $RUN_ID T <label>` once, then wait and collect again. If it fails again, note it and go on. Never retry a second time.
5. Commit and push: `rerun <RUN_ID>: T group G`.

**If the machine restarted** and `/tmp/rerun-<RUN_ID>/` is gone, run `build` again (prompts are identical for the same run id), write in `NOTES.md` which sessions were running when it stopped, and relaunch the current group. `launch` skips sessions already collected.

**5. Report.** Run `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py status $RUN_ID`. Also run `python3 pub-repo/tools-and-testing/snapshot-20261019/tools/run.py collect $RUN_ID` one last time. Write `runs/<RUN_ID>/REPORT.md` with:
- the status table
- the Claude Code version and git commit from `preflight.json`
- start and end times
- every retry, leak, and note

Do not interpret the results. Commit and push, then end with the status table and the list of anything noted.
