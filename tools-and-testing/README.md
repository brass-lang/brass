# Tools and testing

This folder contains the `brass` tool and the records behind the published results. The [language specification](../docs/brass-core-spec.md) is one level up.

| Folder | What it is |
|---|---|
| [`brass/`](brass/) | The `brass` tool: checks a program's structure, runs its examples and answers questions about the code. `bin/brass` is the command; `BRASS.md` documents it. The README's "Try it" starts here. |
| [`snapshot-20261019/`](snapshot-20261019/) | The 40-session Sonnet comparison: cash advances at two codebase sizes, plus trip plans, in Brass and Python. Includes prompts, transcripts, finished programs and scores. Frozen on 2026-10-19. |
| [`earlier-tests/`](earlier-tests/) | Two earlier comparisons: supplying a shared state vocabulary (`16-settled`), and giving Python a similar tool and project map (`18-python-tool`). |
| [`reference/`](reference/) | The editing reference for models. Frozen copies in the snapshot show what each setup received. |
| [`measurement/`](measurement/) | How tokens were counted, per request, from a session's transcript. |
| [`checks/`](checks/) | Two self-checks on this repository: the grammar's examples against the spec, and the example programs through `brass`. |

Trial inputs, scripts and session records are preserved as they ran. Their scripts use paths from the private repository and cannot run unchanged from this layout. The surrounding READMEs explain the records; the freeze tables identify the original inputs.
