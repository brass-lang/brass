# Report: rerun opus55-20261017

## Status

```
small-P1   collected              C 122/122  turns 9  $0.5889234  think 2422  leaks 0
grown-K1   collected              C 122/122  turns 24  $1.5269153999999996  think 19800  leaks 0
small-KC1  collected              C 122/122  turns 10  $1.428202  think 17105  leaks 2
grown-P1   collected              C 122/122  turns 10  $0.6988404  think 3412  leaks 0
small-K1   collected              C 122/122  turns 15  $1.1266186000000002  think 13911  leaks 0
grown-KC1  collected              C 122/122  turns 11  $1.7096292  think 20354  leaks 2
small-P2   collected              C 122/122  turns 10  $0.6460520000000001  think 3380  leaks 0
grown-K2   collected              C 114/122  turns 15  $1.0052324  think 9735  leaks 0
small-KC2  collected              C 122/122  turns 9  $1.4219089999999999  think 16657  leaks 0
grown-P2   collected              C 122/122  turns 12  $0.8782374000000001  think 3838  leaks 1
small-K2   collected              C 122/122  turns 14  $1.1657292  think 18079  leaks 0
grown-KC2  collected              C 122/122  turns 7  $1.1232232000000002  think 14297  leaks 0
small-P3   collected              C 122/122  turns 8  $0.5307801999999999  think 2372  leaks 0
grown-K3   collected              C 122/122  turns 13  $1.1962861999999999  think 13457  leaks 0
small-KC3  collected              C 122/122  turns 10  $1.5309104  think 17267  leaks 2
grown-P3   collected              C 122/122  turns 12  $0.8085521999999999  think 3665  leaks 0
small-K3   collected              C 122/122  turns 12  $1.1795988000000002  think 17281  leaks 0
grown-KC3  collected              C 122/122  turns 7  $1.0629032  think 13400  leaks 1
```

## Environment

- Claude Code version (preflight.json): `2.1.302 (Claude Code)`
- Git commit (preflight.json `git_head`): `f2a14c7ea4cdbc7f63db166b0c4136e6f7d2b654`
- Model `claude-opus-5-5`, effort `high`, as fixed in `run.py`.

## Times

- Start: 2026-10-17T06:47:41Z (step 1); preflight at 2026-10-17T06:47:56Z.
- End: 2026-10-17T07:20:51Z (status after group 6 collected).

## Retries

None. No session had `is_error` true, and `collect` reported no session that ended without a result.

## Leaks

| Session | Entry |
|---|---|
| small-KC1 | `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt` |
| small-KC1 | `Write: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt` |
| grown-KC1 | `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-grown-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad` |
| grown-KC1 | `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-KC1-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/bz` |
| grown-P2 | `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-P2-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/b9b` |
| small-KC3 | `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad` |
| small-KC3 | `Bash: /tmp/claude-0/-tmp-rerun-opus55-20261017-small-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/scratchpad/patch.txt` |
| grown-KC3 | `Read: /root/.claude/projects/-tmp-rerun-opus55-20261017-grown-KC3-project/cd57c46f-b481-5b37-9466-887a6d309201/tool-results/bs` |

## Notes

- All 18 sessions: `model_ok` true, `transcript_saved` true, `is_error` false.
- All 18 summaries show the same `session_id`, `cd57c46f-b481-5b37-9466-887a6d309201`, which is also the id of the parent Claude Code session that ran this protocol. Recorded without interpretation.
- The parent session's request to upgrade repository access to push was denied; plain `git push` worked, and every step was pushed.
- Full per-group notes: `NOTES.md`.
