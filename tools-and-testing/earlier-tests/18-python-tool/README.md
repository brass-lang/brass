# Python with a keelc-like tool: how much does the tool explain?

**Set up 2026-10-02.** Three Python sessions received a tool and project context similar to Keel's. Their mean cached input fell from 3.48M to 1.90M tokens compared with stage 1's stored Python sessions.

The trial used the name Keel. Its labels are P for Python, PC for Python with the added tool and context, and KC for Keel and `keelc`.

## Why

Keel sessions used much less cumulative input than Python in stage 1. They also received a tool, project map and host contract that Python did not. This trial gave Python a similar tool and the same project information to test how much of the difference those additions could explain.

## The arm: PC

Stage 1's grown task C, Python, plus:

- **`bin/pytool`** (`tools/pytool.py`) provides `show` and `apply`. Stage 1's KC sessions used 22 `show --body`, 15 `apply`, 8 `show` and 4 `check` calls:
  - `show`: every module's source without function bodies, numbered (28.6k characters; keelc's `show` on the Keel tree: 28.5k).
  - `show --body m1 m2`: whole files, numbered.
  - `apply`: keelc's patch format, all or nothing, then compiles the files it wrote.
  - No `check`: the session can already run `python3`.
- **The same prompt material as KC**, rewritten for Python (`materials/`): the tool notes, the host contract (same 37 operations), and the project map (KC's module descriptions; the Python modules' own declarations).

Everything else is stage 1: model, launcher, cap 150, task text, cases.

## What a Python `show` cannot carry

Python's output shows names and types. Keel's declarations also describe authority, contracts and accepted states. Those differences remain in this comparison; it does not isolate their individual effects.

## Predictions (written before any run)

Stage 1 grown, stored: **P** $1.50 to 1.6, read about 3.4M; **KC** about $1.6, read about 1.7M.

| PC reads | Reading |
|---|---|
| Near KC, under about 2.2M | The tool and map do most of the reading saving. Keel's declarations add little to it. |
| Between, 2.2M to 3.0M | Both matter. |
| Near P, over about 3.0M | Keel's declarations are what make `show` enough to edit from. |

Three sessions. A difference smaller than an arm's own spread is not a result. This compares across runs (stage 1 ran 2026-09-30); same model and launcher.

## How to run

These original commands depend on paths in the private repository. They are preserved as a record of the run.

```sh
OUT=/tmp/keel-18-run
python3 tools-and-testing/earlier-tests/18-python-tool/tools/build.py $OUT --cap 150 PC1 PC2 PC3
for s in PC1 PC2 PC3; do sh validation/13-evolution-benchmark/tools/launch.sh $OUT/$s; done
python3 tools-and-testing/earlier-tests/18-python-tool/tools/collect.py $OUT
```

## Results (run 2026-10-02)

“Read” is cached input summed across model calls, including repeated context. It is not a count of distinct source code read. Reasoning is estimated from the transcripts.

| Arm | Cost | Read | Reasoning | Turns | Cases (C / grown / orig) |
|---|---|---|---|---|---|
| P, stage 1 | $1.52 | 3.48M | 26.9k | 53 | all hold, 3 of 3 |
| **PC** | **$1.28** | **1.90M** (2.17, 1.74, 1.80) | 34.8k | 22 | all hold, 3 of 3 |
| KC, stage 1 | $1.62 | 1.42M | 68.9k | 16 | one session missed one C case |

**Python moved close to Keel, as the first prediction described.** Adding the tool and project context reduced mean cached input from 3.48M to 1.90M tokens, recovering about three quarters of the earlier gap. Keel remained 0.48M lower. This comparison does not establish what caused the remaining difference.

- **Cheapest arm: PC.** It used more cached input than KC but about half the estimated reasoning tokens. It cost $0.34 less per session than KC and $0.24 less than Python without the added tool.
- **How PC worked:** one `apply` each, 3 to 7 `show --body`, 1 to 2 `show`; it still ran `python3` 4 to 7 times and made some edits directly.
- **Reasoning:** PC 34.8k against P's 26.9k, a small rise inside P's own spread (18k to 35k). This test did not rerun Keel, so its reasoning figure is unchanged.

*Measured, three sessions, against stage 1's stored sessions from two days earlier; same model, launcher, and task.*
