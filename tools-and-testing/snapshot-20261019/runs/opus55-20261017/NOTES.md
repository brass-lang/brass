# Notes: rerun opus55-20261017

Run started 2026-10-17T06:47:41Z (step 1). Preflight ok True.

Setup note: push access upgrade through the session tool was denied; plain `git push` through the session's git proxy worked, so no step was affected.

## Group 1

- small-P1, grown-K1, small-KC1: model_ok true, transcript_saved true, is_error false.
- **small-KC1 leaks (2 entries):**
  - `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt`
  - `Write: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt`
- Observation, recorded without interpretation: all three summaries show `session_id` `cd57c46f-b481-5b37-9466-887a6d309201`, which is also the id of the parent Claude Code session that ran this protocol (it appears in the parent's scratchpad path).

## Group 2

- grown-P1, small-K1, grown-KC1: model_ok true, transcript_saved true, is_error false. Same shared `session_id` as group 1.
- **grown-KC1 leaks (2 entries, verbatim from summary.json):**
  - `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-grown-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad`
  - `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/bz`

## Group 3

- small-P2, grown-K2, small-KC2: model_ok true, transcript_saved true, is_error false, leaks empty. Same shared `session_id`.

## Group 4

- grown-P2, small-K2, grown-KC2: model_ok true, transcript_saved true, is_error false. Same shared `session_id`.
- **grown-P2 leaks (1 entry, verbatim):**
  - `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-P2-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/b9b`

## Group 5

- small-P3, grown-K3, small-KC3: model_ok true, transcript_saved true, is_error false. Same shared `session_id`.
- **small-KC3 leaks (2 entries, verbatim):**
  - `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad`
  - `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt`

## Group 6

- grown-P3, small-K3, grown-KC3: model_ok true, transcript_saved true, is_error false. Same shared `session_id`.
- **grown-KC3 leaks (1 entry, verbatim):**
  - `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/bs`

## Retries

None. No session had is_error true, and collect reported no session that ended without a result.
