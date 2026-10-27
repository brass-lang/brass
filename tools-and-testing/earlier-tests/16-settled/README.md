# Settled puzzle: does deciding the design question cut Keel's reasoning?

**Run 2026-10-02; set up 2026-10-01.** Supplying one state-representation pattern reduced mean estimated reasoning from 60.6k to 42.5k tokens across three sessions. The results are below; the original predictions are preserved.

The trial used the name Keel. Its labels are K for the language alone, KC for the language and `keelc`, and P for Python.

## Why

- Task C sessions in Keel used about 20–35k more estimated reasoning tokens than Python sessions.
- Renaming a symbol and adding a summing function showed no reasoning gap.
- The sessions' own reports name one design question as their costliest work on task C: **how to type a field that must hold a report's state or an advance's state** (the audit entry's `was`/`now`, a statement row's status).

**The test:** stage 1's grown task C again, Keel only, with one change. A short paragraph (`SETTLED.md`) before the task supplies a shared `Step` vocabulary and one converter per machine. Nothing else differs from stage 1: same codebase, materials, model, launcher, cap.

**The pattern omits a subject field.** Stage 1's host contract and cases are frozen with the id in the `report` field, and task C's text says so. The question here is only whether settling the typing choice cuts reasoning.

## Predictions (written before any run)

Stage 1, grown, same estimator: **K 60.6k** mean (57.8 to 63.7), **KC 68.9k** (one session holds a 64k capped turn), **P 26.9k**.

| Outcome for K | Reading |
|---|---|
| Falls toward Python, under about 40k | The design question was most of the gap. Settling such questions in the language is the fix. |
| Falls a little, 45–55k | It was part. Other compositions also cost reasoning. |
| Stays within stage 1's range, 57–64k | The question was not the cost. Look at composition (worked examples) instead. |

Three sessions per arm. A change smaller than stage 1's spread is not a result.

## How to run

These are the original commands. They depend on paths in the private repository. `$OUT` is a directory outside that repository; the launcher starts each session there with a clean context.

```sh
# 1. build: three K sessions (add KC1:KC KC2:KC KC3:KC for the keelc arm too)
OUT=/tmp/keel-16-run
python3 tools-and-testing/earlier-tests/16-settled/tools/build.py $OUT --cap 150 K1:K K2:K K3:K

# 2. launch, one at a time (each about 15 minutes)
for s in K1 K2 K3; do sh validation/13-evolution-benchmark/tools/launch.sh $OUT/$s; done

# 3. collect, score, and compare with stage 1
python3 tools-and-testing/earlier-tests/16-settled/tools/collect.py $OUT
```

Step 3 copies each session into `sessions/`, scores it on task C's cases (122), the grown cases (112), and the original cases (82), and prints its reasoning beside stage 1's.

**Expected cost:** about $1.60 per session, so about $5 for K alone and $10 with KC.

## What to record afterwards

- The launch: date, the manifest's prompt hashes, any failure.
- The table `collect.py` prints, and which prediction row it lands in.
- A measured finding in the private results record, with the three-session sample stated.
- Whether any session still widened a field to `Text` or invented a host operation. A session that ignores the pattern says something too.

## Results (run 2026-10-02)

“Read” counts cached input across model calls, including repeated context. It does not measure how much distinct source code a session opened. Reasoning is estimated from the transcripts using the same method for both runs.

| | Settled (K, this run) | Stage 1 grown K | Stage 1 grown P |
|---|---|---|---|
| Reasoning, same estimator | **42.5k** (39.6, 41.0, 46.9) | 60.6k (57.8 to 63.7) | 26.9k |
| Read | **1.08M** (1.12, 1.26, 0.86) | 3.98M (2.58, 5.88, 3.48) | 3.48M |
| Cost | **$1.16** (1.10, 1.21, 1.17) | $2.11 | $1.52 |
| Cases (C / grown / orig) | all hold, 3 of 3 | two sessions failed the audit field | all hold |

- **Estimated reasoning fell by 18k tokens,** about half the earlier gap over Python. The result lies between the first two prediction ranges.
- **Cached input fell to about a quarter of stage 1's.** Sessions no longer searched the tree for a way to represent the field.
- **Cheaper than Python** ($1.16 against $1.52) and every case held, where two stage 1 Keel sessions failed on exactly this field.
- **Every session used the pattern:** `Step`, `of_report`, `of_advance`. None widened a field to `Text`; each added exactly the four store operations the task names.

*Measured, three sessions, compared with stage 1's stored sessions; same model, launcher, and materials apart from the paragraph.* The paragraph also rules out `Text` and new host operations. The comparison does not separate the benefit of supplying a representation from the benefit of ruling out alternatives.
