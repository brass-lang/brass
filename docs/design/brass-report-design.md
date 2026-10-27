Status: companion to `brass-core-spec.md` §11. Defines the `brass` report and error format. The spec states what `brass` is and the two rules a report obeys; this file states every row, phrase, and flag. Where they disagree, the spec wins. **§0 below is the v0.2 amendment, written 2026-09-25 at assembly; §1 to §14 are the v0.1 design and stand only where §0 does not replace them.** A full rewrite is scheduled for the tool pass that follows the language firming (review E44's standing direction).

# Brass Info Report

## 0. The v0.2 amendment

**Normative, from the spec.** `brass` queries a program state recorded in `lock` and returns the requested information with enough provenance to identify that state. A question is a structured query: a verb, a named thing, flags. The answer is a pure function of the question, the interface declarations it reaches, `lock`, the checker build, and the checker configuration that can change an answer. A report shows only facts the checker has and never advises; an error says what is wrong and what to change.

**Design goal, unverified.** Related information should be retrievable together, so that a declaration, its contracts, and its callers are not three discovery calls. The trials motivate this (runs 4 to 8, a private record); they do not verify it. A measurement rule for the next run: fewer calls is not success if each response returns substantially more.

**Hashes: two jobs, two forms.** Full hashes are identity, verification, and `lock`. A 12-character prefix is display. A prefix that matches more than one record is a rejection asking for a longer one; the tool never picks the newest. A short citation verifies a prefix match; verifying full identity needs the full hash, which `--provenance` prints. This replaces §2's "all 64 hex characters, no display truncation".

**A query id is a checkable citation, not a retrieval key.** No report archive is kept. A citation carries its question with its id (`q:9b31e0c72a54 info feeding.deliver`); `brass` recomputes that question from the tree as it stands and compares the received report's content with the recomputed one, not the id alone. `brass check` refuses a repair whose cited reports no longer match: cited reports are the ones read before the edit, compared against the tree the edit was made on; a mismatch means something changed underneath. A report whose tree is gone cannot be rebuilt, and the tool says so. The "identifies facts, not rendered bytes" rule (§2) stands.

**The default report** is the declaration, its `used_by`, its holds and grants where it has them, and a body-references line:

```
info feeding.deliver  q:9b31e0c72a54
  fn deliver(f: PendingFeeding, by: Deliverer) -> DeliveredFeeding      proven
    after result.paddock == f.paddock and result.grams == f.grams and result.delivered_by == by.badge
  used_by   control.deliver_as
  body      1 line   references: feeding.FeedingStatus
end q:9b31e0c72a54
```

Removed from the default: the four provenance rows (`interfaces_id`, `module`, `lock`, `checker`; now `--provenance`), the command echo, `re-check`, and every zero-count line. `if_changed` is behind a flag and is a per-declaration query, never a module dump. The banner stays on a bare `brass info` alone. The `end` trailer is kept in short form; it detects a missing tail and nothing more, and completeness is established by recomputation, never by the trailer. The bare `brass info` system report is the short form: header, `size`, `grants`, `requires`, `modules` with imports by name, `differs from lock`; about twenty lines plus three per module. `brass info <module>` must be smaller than the module: the interface with tier labels, no per-declaration repetition.

**Tiers.** Three: `proven`, `enforced`, `assumed`. The measured tier left with evidence. The tier *word* prints on every declaration line; the sentence explaining each word prints once per report as a legend, and a legend explains labels, it does not assign them. The declaration line prints the weakest tier among its obligations; each obligation's own tier prints on its row. A bound nothing enforces prints `assumed`; there are no waivers in v0.2, so §8's phrase "waived by <signer> until <date>" is gone, and a `assumed` row no longer fails `check`. §8's bound table is superseded by the spec: a bound named by the `allow`'s own `before` is an authority check, enforced; `budget_<unit>` and `deadline_ms` are enforced over the call; a bound no `before` names is assumed; a contract clause is proven or the program is rejected, and a clause proven from an `allow`'s `after` reports enforced.

**Renames since v0.1**, applied wherever §1 to §14 use the old word: `cap` and `op` are `access` and `allow`; `expects` and `ensures` are `before` and `after`; `capabilities` under `access` is the list of access parameters; `ops/bounds` keeps its job under whatever label the rewrite chooses; `gates`, `evidence`, `eval`, `waiver`, and every measured row are gone; there is no replay row; `if_changed` counts interfaces and modules, never evals; `unbounded` sites no longer exist, so the `unbounded` row is gone and the inventory is functions that return `Outcome` only (C25 removed `partial`); hashes are `q:<12 hex>` in reports.

**Error lines decided in the review**, each `fault <what is wrong>` then facts, then a `fix:` line (proposed; the rule is R8's "what to change"): `caller must establish: <clause>`; `divisor not shown nonzero: <name>`; `edge not established: <expr> enters <State>` with the source states not covered; `narrowing has no values: <Type> on <param>`; `argument type: expected <T>, found <U>`; `mixed and/or requires parentheses: group the intended condition explicitly`; `field not present on this path: <field> needs status in {<State>}`; `<Type> does not project to <Target>: declare it on <Type>, or supply a <Target>`; `after not established: <clause>` with a counterexample where the checker has one. A failed `is` test at a boundary names the refinement and the failed clause and does not print field values unless asked. A hole prints `hole <file>:<line> @@<name> : <Type>`, the bindings in scope with their narrowings, and what would have to be established for each candidate. A `#` comment directly above a declaration is shown with it.

**Open here.** The flag set as one design question, and principle 2.11 with it (review E52): which flags exist, which add facts, which change the question, and how the query-id rule decides. "Protection moved" as one report line for a loosened obligation (E47) waits in E52. Attribution on enforced rows (who asserted the value) is a detail on the row, not a tier. How a `when` field prints on a type block.

---


## 1. What a report is

`brass info <thing>` answers "what is true about this thing" by projecting facts the checker already holds. It adds nothing, summarizes nothing, and gives no advice (R8). A report is a pure function of five inputs: the question, the interface declarations reached from it, the named thing's module including its body, the `lock`, and the checker build. No clock: dates appear as facts, never as judgments about the present. Same inputs, same bytes.

Two readers, one format. A model reads it instead of loading bodies, the system file, and the lock. A human reads it to review a change. Every label is either a Brass keyword or plain English; nothing in a report needs the spec to decode.

**Spider rule.** A bare verb lists; a named thing answers; no output is ever the sum of the level below it. `brass info` lists modules, `brass info <module>` lists functions, `brass info <module>.<fn>` answers for one. `brass show` lists files, `brass show <module>` returns one. The model goes deeper by naming, never by asking for more. The one exception is `info <module> --detailed`, which shows a module's blocks in one response. It is a presentation choice, not a different question (§10).

## 2. Header and footer

> **Synchronization flag (2026-09-18). This section is amended by review E42 (`keel-review.md`, a private record); read E42's Decided blocks with it, and where they differ E42 wins.** The five-row header and the `end` trailer are not the default any more. Full hashes are identity, verification, and `lock`; a 12-character prefix is display, and an ambiguous prefix is a rejection asking for a longer one. `interfaces_id`, `module`, `lock`, and `checker` move to `--provenance`. The `end` trailer is kept, in short form `end q:<12 hex>`; documented with its limit, which is that it detects a missing tail and nothing more, completeness being established by recomputation. A query id is a checkable citation, not a retrieval key — no report archive is kept, `brass` recomputes from the tree, and a report whose tree is gone cannot be rebuilt. The "identifies facts, not rendered bytes" rule below stands. Rewritten at assembly, not now.

Every report opens with hashed header rows and closes with `end`. Three rows are standard in every verb; the rest are per verb.

```
info rates.fetch v1
  query_id       sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371
  ...
end sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
```

| Row | What it identifies | How it is computed |
|---|---|---|
| `query_id` | The facts this report answers: the question and the state it was asked of. | Hash of the question text plus every header input beneath it (`interfaces_id`, `module`, `lock`, `checker`). Derived, not random: the same question of the same state gives the same id, so a reader can tell it already has this answer. It identifies facts, not rendered bytes: presentation flags (`--detailed`, `--add-help-comments`, `--embed-timestamp`) never change it, because they change how the same facts are shown, not which facts are answered. Two reports with one `query_id` agree on every fact; one may show more rows than the other. |
| `interfaces_id` | The facts the answer was read from. | A hash of hashes. Start at the named thing and follow every name it mentions (parameter types, return type, capabilities and their ops, contract clauses, machine states, contexts) across imports until nothing new appears; that is the semantic surface (spec §12.1). Take the `interface` hash `lock` pins for each module reached, the thing's own module included, sort them, hash the list. At system level the list is every module in `lock`. Verifiable from `lock` alone without parsing Brass; one construction at every level. Editing a body never changes it; editing any interface in a reached module does, including declarations the thing does not use, which is a false stale and the right direction to be wrong in. |
| `module` | The named thing's module, body included. | The content hash of the module file, the same value `lock` pins for it. Needed because `ops/bounds` reads the body (which ops are called; whether a `get` argument is a literal), so a body edit can change a report without moving `interfaces_id`. |
| `lock` | The pinned system. | System name, version, and the hash of its `lock` file. Grant values and waivers come from here. |
| `checker` | The build of `brass` that produced the report. | The binary's own build hash. A proof is only as good as the prover; this names the prover. If it differs from the `checker` pinned in `lock`, the report was computed by a different build than the one that validated the system. |
| `end` | Completeness. | Repeats `query_id`. A missing or mismatched `end` means the report was cut off in transit. |

**Header rule.** A header row is an input that determines the facts, or an identity of them; nothing else. Presentation is not an input. `query_id`, `interfaces_id`, and `module` appear in every verb. `info` and `diagnostic` add `lock` and `checker`. `show` (§14) adds `file` and `line_location` and omits `lock` and `checker`, since neither changes a file's bytes. `query_id` hashes the question plus every header row beneath it, so the rule is the same for every verb.

**Freshness.** Three different questions, three different checks. None of them needs a diff.

| Question | Check |
|---|---|
| Can I reuse this report? | Same `query_id`. It hashes every header input, so it matches only if every input matches: interfaces, module, lock, checker. A lock or checker change alone invalidates it, since grants, waivers, and tier judgments come from there. A summary and a detailed report of the same thing share it; the detailed one has more rows of the same facts. |
| Are my interface assumptions current? | Same `interfaces_id`. If it moved, a contract in the surface changed and everything in `if_changed` is suspect, including an edit in progress. |
| Am I editing the body I inspected? | Same `module`. If it moved and `interfaces_id` did not, a body changed inside a stable contract. Callers' contract assumptions hold; behavioral substitutability holds only as far as interface, examples, and evals capture behavior (R7). Another agent's body edit is caught here and nowhere else. |

**Staleness at `check`.** A model cites the `query_id` of the reports it read when it proposes an edit. `brass check` recomputes each and refuses a repair whose cited reports no longer match.

**Hashes.** Every hash carries the `sha256:` prefix and all 64 hex characters, in reports and in `lock`. No display truncation: a shortened hash invites guessing at which of two near-identical values a reader is looking at, and a report exists to remove guesswork. A label ending in `_id` holds exactly one such value and nothing else.

**Timestamps.** None by default; a timestamp is volatile and would make identical reports differ. `--embed-timestamp` adds one row after `checker`, excluded from every hash:

```
  timestamp      2026-09-09T18:04:11Z
```

## 3. Naming rule

A label is a Brass keyword when one exists: `expects`, `ensures`, `const`, `unbounded`, `imports`, `fn`. Otherwise it is one or two plain English words. No coined words, no abstract nouns. The same rule applies to values: `enforced - by runtime on every call`, not `invariant`.

Sections are lowercase and indented, like every other Brass section. There are no rules, symbols, or capitals.

**Column rule.** Three things sit at column 0: the report head (`info ...`, `show ...`, `diagnostic ...`), the source markers `source_start` / `source_end`, and `end`. Every report row is indented two spaces. Between `source_start` and `source_end` nothing belongs to the report, so whatever columns appear there are the file's own. A reader never has to ask whether a line is frame, report, or source: column 0 is frame, two spaces is report, and inside the markers it is the file.

## 4. Four levels

| Command | What it emits | Size for the §9 sample |
|---|---|---|
| `brass info` | The system: grants, limits, waivers, three lines per module (name, imports, exposure), system `exposure`, gates. | 21 lines |
| `brass info <module>` | Summary: module `access`, two lines per function (signature, exposure), module `exposure`, `dependencies`. | 28 lines |
| `brass info <module> --detailed` | Same header, module `access`, and footer; every function expanded to its full block. | 72 lines |
| `brass info <module>.<declaration>` | One declaration, full block, its own `dependencies`. | 26 lines |

`brass show` (proposed, §14) has the same ladder for source: bare lists files, a module or declaration returns its file, a declaration plus `interface` or `body` returns that segment.

The summary is the default because it is the cheapest read that lets a model choose what to inspect next; blocks are opened one at a time. It is not enough to call a function: preconditions and the definitions of the types named are in the blocks (§7, §8). The value of a report grows with what it replaces: imports, the system file, the lock, and runtime knowledge. For one module with no imports it replaces little.

### Cost

Measured on the §9 sample (2026-09-09, chars / 3.4 as the token estimate): a block is 11 to 17 lines and 60 to 115 tokens, about 90 on average; a summary entry is 2 lines and about 25 tokens; header, module `exposure`, `dependencies`, and `end` together are about 100 tokens. Source runs about 9.4 tokens per line. The sample's bodies are one line each, which is the report's worst case: there the detailed report is 1.35x the source.

Projected with 6 to 10 line bodies, about 12 source lines per function:

| | 80-line module | 500-line module | 2500-line module |
|---|---|---|---|
| Functions | 5 | 33 | 165 |
| Source tokens | 750 | 4,700 | 23,500 |
| Summary tokens | 225 | 925 | 4,200 |
| `--detailed` tokens | 540 | 3,000 | 14,600 |
| Summary + 3 blocks | 780 | 1,480 | 4,750 |

Three readings. Below about 100 lines, read the source. From 500 lines up, the summary-first path costs a fifth to a third of the source. `--detailed` costs 60 to 70 percent of the source at every size and carries facts the source does not hold; at 2500 lines that is 14k tokens, so choose it when several related functions are in play and the summary would mean opening them one by one anyway. These are projections; `brass bench` measures the real thing against a real system, and should count what the source column omits: the system file, the lock, imported interfaces, and enforcement knowledge.

**Subset rule.** A declaration's block is rendered by one function and is byte-identical wherever it appears: standalone, or inside `--detailed`. A module summary and its `--detailed` form share one `query_id`; the standalone declaration report has its own, because the question names a different thing. `interfaces_id` may differ too: a module reaches every interface its declarations reach, a declaration only its own; in the §9 sample they coincide because the module has no imports. `dependencies` is scoped to the question: at module level, `used_by` lists who depends on the module; at declaration level, it includes callers inside the module.

## 5. The system report

`brass info` with nothing named reports the system in the working tree. It is the top of the ladder (system, module, declaration) and the natural first command in an unfamiliar repo.

```
info rates v1
  query_id       sha256:6d2f9a80c31e4b5769a1ff1efda9dd179eb30610a8b0fadfaa5ba224c7ea8c65
  interfaces_id  sha256:b04c7e19f2a8d635221a7710d3e4df119184b1e9136e0c2b73a18aa176b810ae
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371

  grants
    main         EcbNet { budget: 50MB, deadline: +30s }, CacheFs
  limits
    impact       modules 4
  waivers
    EcbNet.budget  signed pcn until 2026-12-01

  modules
    rates.fetch v1
      imports      none
      exposure     assumed - nothing checks it, waived by pcn until 2026-12-01

  exposure       assumed - nothing checks it, waived by pcn until 2026-12-01
  gates          none

end sha256:6d2f9a80c31e4b5769a1ff1efda9dd179eb30610a8b0fadfaa5ba224c7ea8c65
```

- No `module` header row: a system has no single module, and the header rule admits only inputs and identities. `interfaces_id` covers every interface in the system.
- Rows are the `system` file's own keywords (`grants`, `limits` for the `limit` lines, `gates`) plus `waivers` from the evidence section. `gates` lists each gate with its eval's `measured` phrase when present, `none` otherwise.
- `modules` is three lines per module: name, `imports`, `exposure`. The `imports` lines together are the system's complete dependency graph, one edge list per node; `lock` holds the nodes, this holds the edges. It stays within the spider rule because edges are a fact about the system level, not the content of the modules. `used_by` is the same edges read backward and is left to the module report; `if_changed` is a count over a specific change and stays per node. System `exposure` is the lowest module.
- Resolution: one `system` in the tree is the system. More than one requires `--system <name>`. None is an error, not a guess.
- Size grows with module count only, about 20 lines plus three per module.

### 5a. The system report as a map (proposed 2026-09-12; cut to the short form the same day)

**Purpose.** A model asked to work on a system it has not seen must decide what to read before it reads much. The root report is the map for that decision: what the system may touch, which interfaces to read first, and identities that say whether an earlier reading still holds. It is computed from source and `lock`, with no runtime and no model in the loop.

**Rules, all inherited.** Facts the checker has, never advice or judgment (R8). Byte-stable for the same source and `lock`; no clock. Rows are named by the `system` file's keywords where one exists (`grants`, `requires`), plain words otherwise (§3). Ordering by a count with a name tie-breaker is a fact. Full tier phrases from §8 wherever a tier appears. The report ends with `end`. Below the system level a thing is a name or a count here and a report of its own one level down (the spider rule).

**Identity and provenance.** The header keeps its §2 shape: inputs and identities only. `interfaces_id` is the hash of the locked interfaces and says whether a model's earlier reading of them holds. `source_id` is a hash over every current source input the report reads (all `.brass` files in the tree), so `query_id` changes whenever any fact below could change, including a body edit no lock has seen. A `facts` row states which version the `exposure` phrases describe: `lock` when every module in the tree matches `lock` and the phrases come from the evidence `lock` records, `current source` when the checker ran on the tree as it stands. When the tree differs from `lock` and no fresh check has run, `exposure` reads `not computed for current source` rather than showing a stale value. `source_id` covers every current source input that can change any row of this report: every `.brass` file in the tree, and the `system` file. The `checker` row names the build rendering the report; the checker that produced the evidence in `lock` is named there, and the two can differ (§2).

**Sections, in order.** This is the whole report.

| Section | Rows | What it establishes |
|---|---|---|
| header | `system`, `query_id`, `interfaces_id`, `source_id`, `lock`, `checker`, `facts` | identities and provenance; nothing derived |
| `size` | modules; interface lines (public); private lines; body lines | whether reading every public interface is feasible |
| `grants` | the `system` file's `grants` lines, each followed by the entry point's qualified declaration name | the authority available to each entry point and its bounds; not everything the system does, and not proof that the authority is exercised, which the declarations and bodies show. Bounds stay on the grant that carries them (S2). The qualified name lets a model ask `brass info park.control.run_day` at once |
| `requires` | each role and the module that fills it | what is chosen outside the source tree |
| `modules` | one entry each, ordered by `used_by` descending then name: name, public interface lines, private lines, body lines, `used_by`, `imports` by name (a second line when long), `exposure` in its full §8 phrase | the dependency graph in full, with sizes, as context for choosing what to read. The task decides the choice: a widely imported module is widely referenced, not necessarily the first read; zero importers does not make a module an execution root, `grants` and calls do. Whether a change affects dependents is `if_changed`'s answer |
| `differs from lock` | modules whose current source hash is not the one in `lock`, modules present in the tree and absent from `lock`, and modules in `lock` absent from the tree, each labelled `changed`, `added`, or `removed`; or `none` | whether the tree is mid-edit, including additions and deletions |

**Counting rules.** Three line counts, each non-blank, non-comment lines within its section, headings excluded, and none includes another: `interface` is the public section only; `private` is the `private` section; `body` is the body. The same three rules give the `size` totals. `interface 16   private 6` means sixteen public lines and six private ones, twenty-two in all. *`used_by`* counts modules that import this module; a `grants` line does not make `system` a user.

**Example.** The park, thirty-five modules, tree matching `lock`.

```
info park v4
  query_id       sha256:…
  interfaces_id  sha256:…
  source_id      sha256:…
  lock           park v4 sha256:…
  checker        brass sha256:…
  facts          lock

  size
    modules 35   interface 1,610   private 230   body 18,200

  grants
    run_day      doors = Doors { paddocks: {Raptor, Rex}, budget: 100 }        park.control.run_day
    classify     net = VendorNet { hosts: {api.vendor-a.com}, budget: 200MB }  park.classify.classify
    move         banking = Banking                                              bank.move
    ...  (6)

  requires
    image.search = vendor_a.search v3

  modules
    park.gates       interface 16   private 6   body 410   used_by 9
                     imports park.paddocks
                     exposure enforced - by runtime on every call
    park.paddocks    interface 31   private 0   body 120   used_by 7
                     imports none
                     exposure proven - by brass before run
    park.control     interface 9    private 0   body 640   used_by 0
                     imports park.gates, park.paddocks, park.feeding, park.classify, std.console, bank.transfer
                     exposure enforced - by runtime on every call
    ...  (35)

  differs from lock   none

end sha256:…
```

**Reading it.** Keep `interfaces_id` and `source_id`. `grants` says what authority each entry point holds and where its declaration is. `modules` gives sizes and the dependency graph as context; the task decides which interface to open first. Read interfaces first; inspect bodies when implementation detail is needed, which includes debugging and review, not only editing. `differs from lock` and `facts` say which version `exposure` describes.

**Not in the map.** Access holders by type, machine names, `limits`, contract counts, inventory counts, unreferenced declarations: each was considered on 2026-09-12 and set aside for the root report. They serve a reviewer or a model that already knows the system, not one building context for the first time; the module and declaration reports carry the same facts where they are used. Cyclomatic complexity is excluded outright: with one branch form and one loop form the number tracks body length, already shown. Comment ratios, timestamps, and status symbols per §12. `waivers` and `gates` return with evidence, deferred out of v0.2.

**Cost.** About twenty lines plus three per module. The token count is to be measured on a fully expanded report, not estimated.

## 6. The module summary

```
  access
    capabilities EcbNet, CacheFs
    data         none
    unbounded    none

  functions
    fn newest(a: RateTable, b: RateTable) -> RateTable
      exposure     proven - by brass before run
    fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
      exposure     assumed - nothing checks it, waived by pcn until 2026-12-01
    fn cache(fs: CacheFs, table: RateTable) -> Outcome<Done>
      exposure     enforced - by runtime on every call
    fn main(net: EcbNet, fs: CacheFs) -> Outcome<Done>
      exposure     assumed - nothing checks it, waived by pcn until 2026-12-01

  exposure       assumed - nothing checks it, waived by pcn until 2026-12-01
```

The summary opens with the module's `access`: the same three rows as a block, rolled up. `capabilities` is the union of every function's capability types, `const` the union of constants read, `unbounded` the union of unbounded sites. It answers "what can this module reach" before "what is in it".

Then two lines per function: the declaration exactly as written in the interface, then its exposure with the full phrase. The signature line is the source text, so it is one form (R3). It tells a reader which function to inspect; preconditions and type definitions are in the blocks. The module `exposure` is the lowest of its functions. The summary is a strict projection of the blocks: each function's two lines are the first line and the `exposure` line of its block, module `access` is the union, module `exposure` the minimum.

## 7. A declaration block

Headed by the declaration's signature line exactly as written in the interface (`fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>`), never a bare name. That line is source text. Everything under it is a projection: the contract rows are labeled, one clause per line, with `none` added where the source has no clause. Then three sections and `exposure`, always present, `none` where empty. A missing section can only mean truncation.

```
  fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
    expects      none
    ensures      result.currency_count > 0
    states       none
    access
      capabilities net: EcbNet
      data         none
      unbounded    none
    ops/bounds
      net.get -> Outcome<Bytes>
        hosts        in {ecb.europa.eu}   proven - by brass before run
        deadline     +30s                 enforced - by runtime on every call
        budget       50MB                 assumed - nothing checks it, waived by pcn until 2026-12-01
    exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  dependencies
    imports      none
    used_by      rates.fetch.main
    if_changed   interfaces 0, modules 1, evals 0
```

### heading and contracts

| Row | Meaning |
|---|---|
| heading | The declaration as written: keyword, name, parameters with types, return type. `Outcome<T>` means it can fail; nothing else marks it. |
| `expects` | Preconditions, one per line. The caller must make these true. |
| `ensures` | Postconditions, one per line. The body must make these true. Stated here once; see `ops/bounds`. |
| `states` | Machine states a parameter must be in, as the refinement that requires it. Derived from the parameter types. |

### access

What the function can reach beyond its inputs.

| Row | Meaning |
|---|---|
| `capabilities` | Authority held: each capability parameter as `name: Type`. Holding is not exercising; what the body does with it is `ops/bounds`. `none` states purity in one word (R4). |
| `const` | The constants it reads (§2.1). |
| `unbounded` | Loops or waits declared `unbounded`. `none` means every loop and wait has a limit. |

### ops/bounds

Authority exercised, and every obligation on it. Two kinds of row group.

**Direct operations.** Each op the body itself calls, written as `<parameter>.<op> -> <return type>` with the return type copied from the op declaration (`net.get -> Outcome<Bytes>`; `fs.write -> Outcome<Done>`). Beneath it, every bound of that parameter's declared type: the bound's name, its value, and its tier phrase. The value is written in the refinement's own form (`in {ecb.europa.eu}`, `in 0 to $500`) when it comes from a type, and as the grant literal (`+30s`, `50MB`) when it comes from the `system`; either way it is source text. Keying on the parameter name, not the type, keeps two parameters of one type distinct when their grants differ.

**Calls that pass authority.** Each callee the body hands a capability to, written as `via <callee>` with the parameters passed and the callee's own `exposure`. This is how obligations propagate: a caller does not inherit its callees' rows, it records that it delegated and what the delegate's weakest obligation is. Within the module the callee's exposure is computed directly; for an imported callee the checker has its module too (`lock` is complete, spec §10.2), so the same computation runs there.

- A pure function reads `ops/bounds none`.
- `ensures` is stated under the heading and appears here only when its tier is not `proven`. The contract fragment is decidable by design (§2.2), so that means an `extern` body, where it reads `ensures  enforced - by runtime on every call`.

### exposure

The weakest assurance tier among the obligations this block reports: the bound rows under direct operations, the `exposure` of each `via` callee, and the contracts. Nothing more. It does not say the function is correct, safe, or complete: a function can have every stated obligation proven and still do the wrong thing because its contracts say too little (`fetch_ecb` ensures only what `RateTable` already implies). `exposure none` when there are no obligations, as for a pure function with `ensures none`.

### dependencies

| Row | Meaning |
|---|---|
| `imports` | Modules whose interfaces this reads. |
| `used_by` | Who depends on this. Module level: other modules and systems. Declaration level: also callers inside the module. |
| `if_changed` | The impact set (spec §12.2) if this interface changes: interfaces that must change, modules that must re-check, evals invalidated. Read before editing. |

## 7a. Blocks for types, capabilities, machines, and contexts

A function summary names types and capabilities; a model has to be able to follow those names without opening the file. Same shape as a function block: the declaration's first line verbatim as heading, projected rows beneath, `dependencies` last. These are the minimum; more rows wait for a real system to ask for them.

```
  type RateTable = { currency_count: Int64 where it in 1 to 200, as_of: Instant }
    kind         record
    fields       currency_count  Int64 in 1 to 200
                 as_of           Instant

  dependencies
    used_by      rates.fetch.newest, rates.fetch.fetch_ecb, rates.fetch.cache
    if_changed   interfaces 0, modules 1, evals 0
```

```
  type EcbNet = Net where it.hosts in {ecb.europa.eu}
    kind         capability refinement of Net
    bounds       hosts        in {ecb.europa.eu}
                 budget       from grant
                 deadline     from grant
    ops          get(url: Url) -> Outcome<Bytes>

  dependencies
    granted_in   system rates v1
    used_by      rates.fetch.fetch_ecb, rates.fetch.main
    if_changed   interfaces 0, modules 1, evals 0
```

```
  machine TicketStatus
    states       Open, Escalated, Resolved, Closed
    edges        Open enters Escalated | Resolved
                 Escalated enters Resolved
                 Resolved enters Closed

  dependencies
    used_by      support.refund.issue
    if_changed   interfaces 1, modules 2, evals 0
```

- `kind` says what the declaration is in one or two words: `record`, `refinement of Int64`, `capability refinement of Net`, `capability`. For a refinement the base type is named so a reader can follow it.
- `bounds` on a capability type lists every bound of the base `cap`, with the refinement's value where it fixes one and `from grant` where the `system` supplies it. That is where the values in a function's `ops/bounds` rows come from.
- `ops` on a capability type copies the op declarations from the base `cap`.
- `edges` on a machine copies the edge lines verbatim.
- `granted_in` names each `system` whose `grants` mention the type.
- A `context` block is the `admits`, `retains`, and `gate` lines verbatim; nothing is projected yet.

## 8. Tiers

Every rule in `ops/bounds` carries one of four phrases: a one-word tag, a hyphen, and a fixed description. The two halves always travel together; the tag alone is not a form.

| Phrase | Spec tier | Who holds the rule | When | If broken |
|---|---|---|---|---|
| `proven - by brass before run` | proof | The checker, once | Compile time | Cannot happen; the program would not have compiled |
| `enforced - by runtime on every call` | invariant | The runtime, every time | While running | The call fails and the transcript records it |
| `measured - by eval <name>, <score> of <bar> needed, expires <date>` | measured | A named `eval` with a judge and samples | On a schedule; the result expires | The eval fails and the system cannot be promoted. The expiry date is reported as a fact; whether it has passed is `check`'s question at promotion, not `info`'s, since `info` has no clock |
| `assumed - nothing checks it, waived by <signer> until <date>` | none | Nobody | Never | Nothing happens |

**Measured means `eval` and nothing else.** The measured tier has one source: an `eval` declaration (§5), whose result the harness writes into `lock`. Bench numbers, transcript statistics, and comments never appear on a tier row. Today the only measured row is a gate's `evidence`; attached evals are deferred (§13), and until they are in scope measured rows do not participate in `exposure`.

**How each row is decided.** `proven` means the checker discharged the obligation. A decidable fragment guarantees the checker always reaches yes or no; it does not guarantee yes.

| Bound | Rule | Typical result |
|---|---|---|
| `expects`, `ensures` | The obligation is discharged in the contract fragment (§2.2) against the body. Discharged: proven. Not discharged: the program is rejected (R1); there is no `enforced` fallback for a contract. An `extern` body cannot be examined, so its contracts are enforced at the boundary (§2.1). | proven, or a rejection |
| `hosts` | Coverage (§2.4): proven when the fragment places the operation's target inside the bound, whether the argument is a literal or has a refined type that implies membership. Otherwise enforced at the call. A first checker may discharge literals only; that is a limitation to state, not the definition. | proven for literals and refined types |
| `root` | Enforced. A lexical prefix check on a path literal proves nothing about runtime path resolution (links, `..`); confinement is the host's job (`design/brass-runtime-design.md`). | enforced |
| `mode` | The op kind is static (`write` needs `rw`). Always decidable. | proven |
| `deadline` | A remote server's speed is not in the source. Always enforced. | enforced |
| `budget` | No runtime mechanism today. | assumed, with waiver |
| `evidence` on a gate | Always measured, by the named eval. | measured |

**Fail closed on `assumed`.** A grant bound that nothing enforces is a `check` error unless a `waiver` (§5) covers it. An unwaived `assumed` row cannot appear in a passing system, so the phrase always names a signer and an expiry. This is R5's "tolerance is a signed, expiring waiver" applied to enforcement gaps, not only to evidence.

## 9. Sample

One module, three working functions plus `main`, and the system that grants authority.

```brass
# Fetch ECB exchange rates, pick the newer of two tables, cache to disk.

module rates.fetch v1
interface
  type Host      = Text
  type Url       = Text
  type Path      = Text
  type Bytes     = Int64 where it in 0 to 1073741824
  type Instant   = Int64
  type FsMode    = Text where it in {ro, rw}

  cap Net { hosts: Set<Host>, budget: Bytes, deadline: Instant }
    op get(url: Url) -> Outcome<Bytes>
  cap Fs { root: Path, mode: FsMode }
    op write(path: Path, body: Bytes) -> Outcome<Done>

  type EcbNet    = Net where it.hosts in {ecb.europa.eu}
  type CacheFs   = Fs where it.root in {/var/rates} and it.mode in {rw}

  type RateTable = { currency_count: Int64 where it in 1 to 200, as_of: Instant }

  fn newest(a: RateTable, b: RateTable) -> RateTable
    ensures result.as_of >= a.as_of
    ensures result.as_of >= b.as_of

  fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
    ensures result.currency_count > 0

  fn cache(fs: CacheFs, table: RateTable) -> Outcome<Done>

  fn main(net: EcbNet, fs: CacheFs) -> Outcome<Done>

body
  fn newest(a, b) = if a.as_of >= b.as_of then a else b

  fn fetch_ecb(net) =
    let raw: Bytes = net.get("https://ecb.europa.eu/rates.xml")?
    parse(raw)

  fn cache(fs, table) = fs.write("/var/rates/latest.tbl", encode(table))

  fn main(net, fs) = cache(fs, fetch_ecb(net)?)

  # parse and encode: body-local helpers, omitted
```

```brass
system rates v1
  grants   main: EcbNet { budget: 50MB, deadline: +30s }, CacheFs
  limit    impact modules 4

waiver EcbNet.budget until 2026-12-01
  because runtime byte counter not built yet
  signed  pcn
```

### brass info rates.fetch v1

```
info rates.fetch v1
  query_id       sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371

  access
    capabilities EcbNet, CacheFs
    data         none
    unbounded    none

  functions
    fn newest(a: RateTable, b: RateTable) -> RateTable
      exposure     proven - by brass before run
    fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
      exposure     assumed - nothing checks it, waived by pcn until 2026-12-01
    fn cache(fs: CacheFs, table: RateTable) -> Outcome<Done>
      exposure     enforced - by runtime on every call
    fn main(net: EcbNet, fs: CacheFs) -> Outcome<Done>
      exposure     assumed - nothing checks it, waived by pcn until 2026-12-01

  exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  dependencies
    imports      none
    used_by      system rates v1
    if_changed   interfaces 0, modules 1, evals 0

end sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
```

### brass info rates.fetch v1 --detailed

```
info rates.fetch v1
  query_id       sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371

  access
    capabilities EcbNet, CacheFs
    data         none
    unbounded    none

  fn newest(a: RateTable, b: RateTable) -> RateTable
    expects      none
    ensures      result.as_of >= a.as_of
                 result.as_of >= b.as_of
    states       none
    access
      capabilities none
      data         none
      unbounded    none
    ops/bounds     none
    exposure       proven - by brass before run

  fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
    expects      none
    ensures      result.currency_count > 0
    states       none
    access
      capabilities net: EcbNet
      data         none
      unbounded    none
    ops/bounds
      net.get -> Outcome<Bytes>
        hosts        in {ecb.europa.eu}   proven - by brass before run
        deadline     +30s                 enforced - by runtime on every call
        budget       50MB                 assumed - nothing checks it, waived by pcn until 2026-12-01
    exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  fn cache(fs: CacheFs, table: RateTable) -> Outcome<Done>
    expects      none
    ensures      none
    states       none
    access
      capabilities fs: CacheFs
      data         none
      unbounded    none
    ops/bounds
      fs.write -> Outcome<Done>
        root         in {/var/rates}      enforced - by runtime on every call
        mode         in {rw}              proven - by brass before run
    exposure       enforced - by runtime on every call

  fn main(net: EcbNet, fs: CacheFs) -> Outcome<Done>
    expects      none
    ensures      none
    states       none
    access
      capabilities net: EcbNet, fs: CacheFs
      data         none
      unbounded    none
    ops/bounds
      via fetch_ecb  net: EcbNet    exposure assumed - nothing checks it, waived by pcn until 2026-12-01
      via cache      fs: CacheFs    exposure enforced - by runtime on every call
    exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  dependencies
    imports      none
    used_by      system rates v1
    if_changed   interfaces 0, modules 1, evals 0

end sha256:9b31e0c7f24a68d53df3b2be6f1ee1e44aca6170ec16b753b3db06549f7b8a95
```

### brass info rates.fetch.fetch_ecb

```
info rates.fetch.fetch_ecb
  query_id       sha256:2c8fa4d1b7e039655edf3f5f39cb56567642cf1feec90c3cd4236113cad2d82e
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371

  fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>
    expects      none
    ensures      result.currency_count > 0
    states       none
    access
      capabilities net: EcbNet
      data         none
      unbounded    none
    ops/bounds
      net.get -> Outcome<Bytes>
        hosts        in {ecb.europa.eu}   proven - by brass before run
        deadline     +30s                 enforced - by runtime on every call
        budget       50MB                 assumed - nothing checks it, waived by pcn until 2026-12-01
    exposure       assumed - nothing checks it, waived by pcn until 2026-12-01

  dependencies
    imports      none
    used_by      rates.fetch.main
    if_changed   interfaces 0, modules 1, evals 0

end sha256:2c8fa4d1b7e039655edf3f5f39cb56567642cf1feec90c3cd4236113cad2d82e
```

Three things to notice. The summary and the `--detailed` report share `query_id`: same question, same facts, more rows. `interfaces_id` is identical across all three because this module imports nothing; with imports, a module's would differ from a declaration's. The `fn fetch_ecb` block is byte-identical in the second and third reports. `main` exercises no operation itself; its two `via` rows say what it delegated and carry its callees' exposure, and its own `exposure` is the lower of the two. When the runtime gains a byte counter, `fetch_ecb`, `main`, and the module move up together without a source change.

## 10. Flags

| Flag | Effect |
|---|---|
| `--detailed` | On a module: expand every function to its full block. Adds rows, never different facts; the summary's two lines per function are the first and last lines of each block, and `query_id` is unchanged. On a declaration: no effect. Useful when several related functions are under review together and one response beats several; the cost is the token count in §4, which is the only reason it is not the default. |
| `--add-help-comments` | Append a fixed `#` comment to every row saying what the value means, under twelve words. On `ops/bounds` rows the comment says why the row got its tier, the one place the text varies. Roughly 150 tokens per report, so off by default. Because the comments are fixed strings, this flag is also the documentation of the format. Never placed on the `end` line's hash, only after it. |
| `--embed-timestamp` | Add a `timestamp` row after `checker`, excluded from every hash. |
| `--system <name>` | Which `system` to read grants and waivers from. Required when the working tree holds more than one; two or more systems and no flag is an error, never a guess. The header's `lock` row names the system used. |

### brass info rates.fetch.fetch_ecb --add-help-comments

```
info rates.fetch.fetch_ecb
  query_id       sha256:2c8fa4d1b7e039655edf3f5f39cb56567642cf1feec90c3cd4236113cad2d82e    # this report; same question + same state = same id
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f    # every interface declaration this was read from; bodies excluded
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01    # content hash of this module's file, body included
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3    # the pinned versions of everything in the system
  checker        brass sha256:7e01d4a8c3f2b9153aed271c13c10436a860501cae41bd3bdd509fff12c4e371       # the build of brass that computed this report

  fn fetch_ecb(net: EcbNet) -> Outcome<RateTable>    # the declaration, as written in the interface
    expects      none                         # what the caller must make true
    ensures      result.currency_count > 0    # what the body must make true
    states       none                         # machine states a parameter must be in
    access       # what the function can reach beyond its inputs
      capabilities net: EcbNet                  # the authority it holds; not what it does with it
      data         none                         # pinned files it reads
      unbounded    none                         # loops or waits with no declared limit
    ops/bounds   # authority exercised, and every obligation on it
      net.get -> Outcome<Bytes>                 # a direct op call; return type as declared
        hosts        in {ecb.europa.eu}   proven - by brass before run             # every get target is a literal in the allowed set
        deadline     +30s                 enforced - by runtime on every call      # a timer the runtime starts per call
        budget       50MB                 assumed - nothing checks it, waived by pcn until 2026-12-01    # no byte counter yet; a signed waiver covers it
    exposure       assumed - nothing checks it, waived by pcn until 2026-12-01    # the function is only as safe as this row

  dependencies
    imports      none                 # modules this reads interfaces from
    used_by      rates.fetch.main     # who depends on this
    if_changed   interfaces 0, modules 1, evals 0    # what must be re-checked if this interface changes

end sha256:2c8fa4d1b7e039655edf3f5f39cb56567642cf1feec90c3cd4236113cad2d82e    # matches query_id, or the report was cut off
```

## 11. Rendering and tests

Render is a pure function from a report value to text. All impure work (reading source, lock, and waivers) happens before it. That function is the single place the format is tested:

- Fixed inputs render to fixed bytes.
- `query_id` is stable across runs, changes when any header input changes, and is unchanged by `--detailed`, `--add-help-comments`, and `--embed-timestamp`.
- `interfaces_id` is unchanged by any body edit and changed by any reached interface edit.
- A declaration block is byte-identical standalone and inside `--detailed`.
- A block's heading equals the interface signature line, whitespace normalized; contract rows are labeled projections of its clauses.
- `exposure` equals the minimum over the block's bound rows, `via` exposures, and contracts, and is `none` when there are none.
- No output depends on the current date.
- Every section is present in every block; `none` is rendered, never omitted.
- The `end` hash equals `query_id`.
- Each of the four tier phrases appears with exactly the fixed text.

## 12. Not in a report

Status symbols (ok / warning / error): that is judgment, and "wrong" lives in `diagnostic`. Environment details: the runtime's business, pinned in `lock`. Recent events: the transcript (spec §10.3). Timestamps, unless asked for. Anything the checker did not compute.

## 13. Open

- **`unbounded` placement.** It is a limit, not an access. Under `ops/bounds` a `none` would read as "all loops bounded"; under `access` it reads as an empty list.
- **`imports` at declaration level.** A function does not import. Either omit the row there, or have it name where each capability type is declared.
- **`diagnostic` output** should carry the same header, `end`, and naming rule. Not yet reshaped beyond the header.
- **Attached evals.** An `eval ... for <function>` is a rule on the function held by a judge, which is what an `ops/bounds` row is; it would read `summary_faithful  measured - by eval summary_faithful, 0.98 of 0.95 needed, expires 2026-12-01`. Whether it then participates in `exposure` alongside enforcement tiers, or stays a separate answer, is open; until decided, measured rows do not. Deferred with evals' v1 scope.
- **Declared things other than functions in the summary.** A module summary lists functions only. Names for `cap` and `machine` declarations and a count of `type` declarations would tell a reader what else the module defines. Not yet added; the blocks themselves are in §7a.
- **Validation.** The token table in §4 shows the report can answer particular maintenance questions in less context than the source. It does not show that a model completes changes more cheaply or more correctly. Test that with the payment workflow from §9.5: ask a model to locate a function, understand its preconditions, modify a body, and assess an interface change. Count everything it reads (type blocks, repeated headers, diagnostics, any `show`), and check the changes. Do this before further work on wording, delimiters, or flags.
- **Transitions performed.** `states` says which state a parameter must be in; nothing says which state a function moves it to (`o enters Paid`). A row for the edge taken is a surface fact (spec §9.2) a reviewer wants. Form open, given the `->` history.

## 14. `brass show` (proposed, `keel-core-considerations.v0.1.md` §25)

`info` answers "what is true"; `show` answers "what does the source say". Different question, so a different verb, not a flag. Same header rows, same column rule, same spider rule: bare lists, named answers, nothing dumps.

### The ladder

| Command | Returns | Locator rows |
|---|---|---|
| `brass show` | A listing of the system's files: kind, name, path, length, hash where `lock` has one. Never source. | none |
| `brass show system` / `brass show lock` | That file. | `file` |
| `brass show <module>` | The module's whole file. | `file` |
| `brass show <module>.<declaration>` | The whole file containing the declaration. A body rarely edits cleanly without the module's types, caps, and body-local helpers, so the file is the unit. | `file` |
| `brass show <module>.<declaration> interface` / `body` | Just that segment of the declaration. `interface` and `body` are the file's own section keywords, not report sections. For re-reading one body when the file's context is already in hand. | `file`, `line_location` |

There is no `show --detailed`. A whole-tree dump is the sum of the level below, which the spider rule forbids; a human who wants a bundle scripts `show` over the listing.

### Header

`query_id` and `interfaces_id` as everywhere. `module` when a module or declaration is named. `lock` on the listing, since the lock decides which files are in the system. No `checker`, and no `lock` on file output: neither changes a file's bytes.

### Locator rows

- `file`: path and line count of the whole file, in every form that returns source. Paths appear in `show` and nowhere else in Brass output.
- `line_location`: only when a segment is shown. The segment's position as file lines, counted from 1, inclusive at both ends, in the language's own range form (`31 to 33`). Not report lines. The same range form is used for `at` in a `diagnostic`.
- `byte_location`: only with `--show-bytes`, beneath `line_location`. The same single range as byte offsets into the file on disk: zero-based, UTF-8, start inclusive, end exclusive. For patch tools that slice without parsing. Off by default; a model or human counts lines.

### Source markers

`source_start` and `source_end` sit at column 0, like `end`. Everything between them is the file's bytes at their original columns; no report indentation is applied, so a model can copy a segment back into the file without re-spacing it. Neither word is a Brass keyword and no valid Brass line begins with either. For whole-file output the lines between the markers equal the count on `file` and `module` is the hash of exactly those bytes; for a segment they equal the span of `line_location`.

### Examples

The listing:

```
show rates v1
  query_id       sha256:8c3d1e07a5b94f26efd1458fc16842910d49e08a3aff6fcdce6091ea2247f3cb
  interfaces_id  sha256:b04c7e19f2a8d635221a7710d3e4df119184b1e9136e0c2b73a18aa176b810ae
  lock           rates v1 sha256:c3f08a17e59d2b40f6bb464bf04be447bb4a35bfe3fffe77cb2b0f66f0a47ec3

  files
    system   rates v1          rates/system.brass   7 lines
    lock     rates v1          rates/lock.brass     12 lines
    module   rates.fetch v1    rates/fetch.brass    38 lines   sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
    module   rates.store v2    rates/store.brass    61 lines   sha256:4b7a90c1d2e8f3562f2a381d91b389351013910f12c42e70b5266a5ec8de0649

end sha256:8c3d1e07a5b94f26efd1458fc16842910d49e08a3aff6fcdce6091ea2247f3cb
```

A whole file, reached by naming a declaration in it:

```
show rates.fetch.fetch_ecb
  query_id       sha256:77c1d0a94e2b6f387ebf2bb02a9ea3c8b923932f0f463a1145f5e51fcc6ad2e9
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  file           rates/fetch.brass  38 lines

source_start
# Fetch ECB exchange rates, pick the newer of two tables, cache to disk.

module rates.fetch v1
interface
  ...
body
  ...
source_end

end sha256:77c1d0a94e2b6f387ebf2bb02a9ea3c8b923932f0f463a1145f5e51fcc6ad2e9
```

One segment:

```
show rates.fetch.fetch_ecb body
  query_id       sha256:a4e19c07d3b52f685de1bbf38fd723860c60c46d218f58737f546097f14881cf
  interfaces_id  sha256:41d7a9e2c08b53f6a5d5e3f685237fa0276b5659b0753a3ffd0c8c634741e85f
  module         rates.fetch v1 sha256:e3d2a09b17c4f5602c68252b7c9c3473214d03ef853980be3caef167907b6b01
  file           rates/fetch.brass  38 lines
  line_location  31 to 33

source_start
  fn fetch_ecb(net) =
    let raw: Bytes = net.get("https://ecb.europa.eu/rates.xml")?
    parse(raw)
source_end

end sha256:a4e19c07d3b52f685de1bbf38fd723860c60c46d218f58737f546097f14881cf
```

### Rejected while designing it

`<<<` / `>>>` delimiters (merge-conflict prior); `#` comment markers (indistinguishable from source comments); a line count on the segment (redundant with `file` and `line_location`); a locator listing both interface and body positions (the output shows one segment, so one range); indenting source under the markers (a model would carry the indent back into the file); `lock` and `checker` rows on file output; `show --detailed`.

### Cost and place in the workflow

R8: bytes untouched, no summary, no advice. On a 2500-line module a whole-file `show` costs the 23k tokens the report path saved, so it is the last step of an edit, taken once after `info` has narrowed the target to one module and one function. The model path is `info`, `info <module>`, `info <module>.<fn>`, then `show <module>.<fn> body`.

## 15. `brass propagate` (proposed 2026-09-29; built in the proxy as `brass-propagate-r1`)

The one verb that writes. After an interface edit, it compares the tree with the baseline (`$BRASS_BASELINE`, else git `HEAD`) and applies the consequences the language rules fix, and only those:

| Interface change | What is written | Where |
|---|---|---|
| parameter added to a function | `@@<name>` as the new argument | every call whose argument count still matches the old signature |
| parameter removed | the argument dropped | the same calls |
| `when` field added | `, <field>: @@<field>` inside the `with { … enters State }` | every expression entering a state in the clause's set |
| plain field added to a record | `, <field>: @@<field>` | every literal of the old shape |

Everything else the change reaches is reported, not written: a retyped parameter, a narrowed refinement, a removed declaration, a changed contract. The tool never chooses a value, never moves a lookup, and never decides whether another declaration sharing a type should change.

**Output.** `propagate against <baseline>`; `interface changes`, one line per changed declaration in `changes`' words; `written N edits, M applied` with each edit as `- old` / `+ new` and the reason; `holes N` with each hole's type, the bindings in scope, and the `if` tests on its path, in the form §0 already defines for a hole; then the `changes` report on the result. `--dry` prints the plan and writes nothing. A second run reports `mechanical nothing`. An edit whose line has moved since the baseline was read is skipped and named.

**How it stays inside R8.** R8 forbids the checker to rewrite. `propagate` is not the checker: it writes holes, and a hole is a rejection with an address (spec §3.2), so no tree it touches passes `check` until the author has supplied every value. The diff a reviewer sees shows the holes the tool placed and the values the author wrote, both attributable. A query's answer stays a pure function of the tree (§0): `propagate` changes the tree and then answers about the new one.

**Open.** Whether an `allow` gaining a parameter should propagate to its callers through the access parameter (`registry.staff(badge)`); today only `fn` calls are rewritten. Whether a removed parameter should leave a hole naming the dropped argument, so the author sees what the call lost. Both wait for a trial that needs them.


## 16. `brass check`, level 1, and the program summary (built in the proxy 2026-09-30; audited the same day)

**What level 1 rejects.** Structure only: an import or qualified name that does not resolve; a body without a declaration or a declaration without a body; a body whose parameter names differ from its declaration; a call with the wrong number of arguments; `?` outside a function that returns `Outcome`; `partial`, removed by C25; an unfilled `@@hole`; an untyped `let`; a removed form written as a form (`return`, `while`, `match`, `loop`, `unbounded` at the start of a line, `Some(…)`); a `grants` line that names no function or does not name exactly the entry point's access parameters. A removed word used as a name (`max`, `slot`) is legal, as grammar §13 says. Each rejection prints `file:line`, what is wrong, and a `fix:` line. The report opens by saying what it checked and what it did not.

**The summary.** When nothing is rejected, the report ends with each granted entry point: the refusals, host calls, state changes, and results found in its source, in source order, grouped by the conditions enclosing them (a `within c` line opens a group, indented; `within not c` is the else-branch); a refusal written in an `else` is placed at the `if` that decides it. It is read from the text, not executed, and says so:

```text
<entry>      holds <access params>
      boundary  <param>: <refined type>   checked before the body runs; a failing argument is refused as InvalidInput
  <line>  refuse   <FailureCode>   <text>   when <condition> | when not: <condition>
  <line>  stores   <FailureCode>   <text>   in <name>, an error value; whether it is returned depends on later lines
        within <condition>              (opens a group; what follows, indented, happens only under it)
  <line>  call     <access>.<op>(<args>)   failure passes up | failure kept as a value | its result is the branch's value, failure included   [repeated: for … in <bound>]
  <line>  state    enters <State>
  <line>  via      <helper>            (its own lines, indented, one level only)
  <line>  succeed  Ok(…)
```

Rules: a refusal in an `else` sorts at the `if` that decides it; `let last: Outcome<…> = Err(…)` is a seeded value only when the name is reassigned below, otherwise it is reported as a stored error; inline and block forms of one `if` report alike (tested); a one-line body is read after its `=`; a helper's accesses are found by parameter type, not name. It is built from the text and proves nothing; the header says so. It exists so a session compares its program with the requirements in one call instead of asking `info`, `--holds`, and `--effects` about code it just wrote (payments test, `validation/11-payments/`: four to nine such calls per session).

**Under a trial gate**, the bare `brass` usage lists only the verbs and flags the run allows.

## 17. `brass check --scenarios`: an entry point against a scripted host (built in the proxy 2026-09-30)

A scenario file names an entry point, its arguments as Brass literals by parameter name, the host's scripted replies per operation in call order, and what to expect: the result (a failure by code, a success by value) and the trace of host calls (operation, or operation with exact arguments). The runner binds every access parameter to the scripted host, runs the body as written, records each host call, and reports the first step that differs. An operation with no reply left answers `Err(FailureCode.Unavailable)`. Output: one line per scenario, `holds` with the result and trace, or `FAILS` with the differing step or the result mismatch.

It exists because the properties the payments test cared about are about order, authorize before reading, check everything before the processor, save before audit, never re-call the processor, and no declaration states them; the reviewer read bodies to establish them. A scenario checks them by execution. It is a test, not a proof: one input, one script, no contract checked, and the summary's header says so. Eight scenarios on one payments program hold (`validation/11-payments/scenarios/K-B1/`); planted faults, audit before save and a single retry, fail on the differing step (fixture suite).

What the evaluator gained for it: `with { field: v, status enters S }`, `length` on `Text`, a `let` whose value is the indented block beneath it, and running functions that return `Outcome` when a host is bound. It still runs nothing that reaches outside without a script.

## 18. The lean shape: answers sized to the step, not the question (built in the proxy 2026-10-01; measured)

**Finding.** An agent's cost is model calls times context, not what a tool returns (`validation/13-evolution-benchmark/results.md`). Each brass call in the first benchmark phase took its own model call (63 of 64), so brass doubled Brass's cost while returning small answers. Reshaping the tool, not the language, removed the gap: Brass with brass went from 3.47M mean input to 2.09M (lean v1) to 1.31M (lean v2), the lowest of any arm, with correctness unchanged.

**The shape** (`tools-and-testing/brass/BRASS.md`, "Lean mode"): several names per call; one `check` that runs everything and ends with `done` or what to fix; `show` of declarations only, whole files on request, several modules at once; no trailer on every answer; `apply` writing every edit in one call and checking in the same call. Two checks earned their place there by catching real defects from the benchmark: effect order (a write before a possible refusal: five of six Brass sessions on one task) and the host contract (an invented host operation).

**For the real brass.** The report format in §§1–17 says what each answer contains. This section says how answers should be sized and bundled: the agent pays per call, so one call should answer what the agent will ask next, and a clean gate should say nothing but `done`. The query id (§3) was never used by any session across three trials (0 of 262 calls); it belongs in a session's final report for a human reviewer, not under every answer.

