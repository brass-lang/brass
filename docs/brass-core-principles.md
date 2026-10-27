# Brass Core Principles v0.3

This document explains why Brass's rules take the form they do, what the design gives up and what the trials have established.

Claims are labeled **design choice**, **bet**, or **measured** to distinguish decisions and expectations from observed results. The [specification](brass-core-spec.md) defines the rules themselves.

## 1. Intended use and evidence

**Design choice.** Brass targets code written or modified by models and reviewed by humans: payments, transactional systems, authorization, workflows, agent tool layers, sandboxes, provisioning, pipelines, and control-plane networking. User interfaces, heavy numerics, hard real-time systems, kernels, unaudited scripts, and agent orchestration are outside its intended scope.

**Design choice.** Resolve design conflicts in this order: correctness, fail-fast behavior, predictability, simplicity, auditability.

**Bet.** Declaring requirements reduces how much a model must read to make a correct edit. Checker diagnostics reduce repair work. Test both on equivalent tasks with the same correctness requirements, counting work through the accepted patch.

**Measured.** The early understanding-task comparisons reported 39% more attributable tokens than Python without tooling and 6% fewer with an early version of `brass`, excluding references. These are task-token comparisons, not source-read counts. They come from separate trial conditions on a 2,418-line corpus, one model family, and small samples. That tool ran no proofs. These results do not establish the performance of the full checker. The trial records behind this are unpublished.

**Measured.** In run 8, the reviewer found body reading largely unavoidable. The trial records behind this are unpublished.

## 2. Design choices and testable bets

### 2.1 Explicit facts reduce reconstruction

**Design choice.** Prefer explicit local facts over relationships that require tracing abstractions. An inherited member requires tracing its origin. Dynamic dispatch requires identifying the selected implementation. Mutable global state hides an input. These costs motivate the intended exclusions of inheritance, methods, dynamic dispatch, and mutable global state. Their specification coverage is recorded in the private considerations file.

**Design choice.** Use an explicit projection for a smaller record view. The source declaration identifies the target and the fields it can supply, without a class hierarchy to inspect. See spec §7.4. Use function signatures to expose inputs and authority; see spec §4 and §8.

**Bet.** Limited factual redundancy costs less than reconstructing hidden relationships. Compare reasoning, reading, writing, and repair costs at equal correctness. The reported reasoning gap on complex edits, and its absence on simple edits, are consistent with this bet but do not establish its cause. The output analysis and the simple-edit trial records are unpublished.

### 2.2 Reviewed interfaces constrain body replacement

**Design choice.** Review the interface as the set of requirements a replacement body must meet. Spec §11.2 defines what replacement preserves. The [refund example](../examples/refund/README.md) demonstrates an allowed body change that alters effect count.

### 2.3 Authority is explicit

**Design choice.** Require authority to be visible in parameters and grants. See spec §8.1–§8.5. A function cannot reach a service through a global variable or store its access in a record.

### 2.4 Tiers distinguish proof, enforcement, and assumptions

**Design choice.** Label each promise with what supports it. Spec §0 defines the tiers; §12.3 defines how a report combines them.

### 2.5 Checking does not repair source

**Design choice.** Keep checking separate from authoring. A repair that silently changes the source also changes what the author must review. Rejection leaves the author to make that choice. Generating a host adapter from an unchanged declaration is a separate operation. See spec §12 and §8.5.

### 2.6 Prefer one form per meaning

**Design choice.** Prefer removing an equivalent form to documenting a stylistic choice. See spec §15.

**Bet.** Fewer equivalent forms reduce inconsistent generation. Compare syntax errors and repair cost on equivalent tasks.

### 2.7 Reuse familiar forms when their meanings agree

**Design choice.** Reuse familiar forms only where their meaning is compatible. `++` distinguishes joining from the arithmetic handled by the prover. `enters` distinguishes a state transition from the return-type arrow `->`. Separate `in` and `is` so the operation is visible before resolving the right-hand name. See spec §2.1, §7.3, and §9.2.

**Design choice.** Treat forms such as `any … in … where …` as units with defined scope and meaning. Reuse a form only where its meaning fits.

**Bet.** Familiar forms and consistent scope reduce learning cost. A familiar token with a different meaning can instead trigger the wrong form. Whether a model uses a particular form correctly remains a bet. Test accepted and rejected uses, including cases where habits from another language produce the wrong interpretation.

### 2.8 Reject edits that violate declared requirements

**Bet.** A checker can catch consequential edits before human review. Measure rejection of invalid arguments, unproved clauses, and illegal transitions with a conforming checker. Passing examples does not establish this benefit. See spec §11 and [examples](../examples/README.md).

### 2.9 Refuse unproved obligations

**Design choice.** Reject a program when its proof obligations cannot be established. See spec §6 and §11.3. Runtime authority and reply checks are defined separately in spec §8.3.

**Design choice.** A correct program can be rejected when the checker cannot prove it. Investigating or repairing that rejection is an accepted cost of requiring proof. Proof difficulty is not evidence that a body is wrong. It is also not permission to replace the obligation with a weaker check.

### 2.10 Reports use syntax and plain words

**Design choice.** Use a keyword as a report label where one exists; otherwise use plain words. Report semantics are in spec §12.

**Bet.** Labels understandable to humans also reduce model interpretation errors. Compare equivalent report formats for comprehension and repair accuracy.

### 2.11 Queries are structured

**Design choice.** Use structured, reproducible queries. See spec §12. Flag semantics remain open.

### 2.12 Classify changes by consequence

**Design choice.** Classify a change as editorial, a missing definition, or semantic by its consequences. Filling a gap can change behavior, proof requirements, or grant binding without adding a keyword. Record decisions in the private change record.

### 2.13 Keep exclusions explicit

**Design choice.** Require a concrete program or failure before adding a mechanism. Current exclusions are in spec §15. Deferred designs are kept in the private considerations file.

**Design choice.** Grants bound the outside operations a program may perform. An effect system would add another mechanism for controlling effects. Declaration placement replaces visibility modifiers and export lists. A separate marker on access parameters would repeat their type information.

**Design choice.** Explicit comparison grouping avoids depending on competing language conventions. Explicit Boolean grouping exposes the author's choice. Neither establishes that the chosen condition is correct. See spec §2.2.

**Design choice.** Final expressions keep ordinary function completion at the end of the body. Whether nested validation costs more reasoning than early return remains unmeasured.

**Design choice.** Relate separate machine states through record fields and refinements instead of nesting machines or attaching payloads to states. This keeps the transition graph separate from relationships between fields. See spec §9.1 and §9.4.

### 2.14 Prefer explicit programs to shorter spellings

**Design choice.** The 32k-token budget applies to the specification, not to programs. Typed bindings and explicit result types remain the chosen forms; see spec §3 and §5.1.

**Bet.** Their review benefit exceeds their writing cost. Measure review accuracy and total cost through an accepted patch.

**Measured.** The results record reports 2,418 language-source lines against 3,210 Python lines. Run 7 session answers used 25–85% more words. These figures describe those samples, not all Brass programs. The trial records behind this are unpublished.

## 3. Design guidance

Each item is a **design choice**, not an additional language rule.

- Put a requirement on the operation it protects. Body checks can then establish it before the call; see spec §8.5.
- State reusable conditions in declarations. Proof and provenance limits are in spec §6–§7.
- Treat repeated workarounds as evidence for investigating a missing form, not automatic justification for adding one.
- Prefer set membership over `or` when the alternatives are values of one field. Membership semantics are in spec §7.3.
- Prefer names that describe function results and verbs for `allow` operations. Naming legality is defined in spec §2.
- Preserve deferred designs and their reasons.
- Measure total work. Fewer tool calls alone do not establish lower cost.

## 4. Evidence limits

**Measured.** Trials 6–8 reported no invented syntax. This does not establish how a working checker would detect behavioral defects. The trial records behind this are unpublished.

**Measured.** Six sessions split the feeding record and added a storage operation before conditional fields were available. This observation motivated a design investigation; it does not establish the efficiency of the resulting form. The trial records behind this are unpublished.

**Design choice — influences.** The design draws on capability authority from E, refinements from Ada, contracts from Dafny, interface separation from OCaml, and locked dependencies from Cargo. The combination and its intended use are design choices, not measured benefits.

## 5. What the principles predict

Each row is a **design choice** applied to a recurring proposal. The cited spec section defines the rule.

| Question | Consequence |
|---|---|
| Should Brass add traits? | Require a concrete system that needs them before adding another abstraction mechanism; see principles §2.1 and §2.6. |
| Can a body construct an access from a literal? | No. That would bypass the authority assigned by `system`; see spec §8.1. |
| May an unproved function contract become a runtime check? | No. Proof failure may expose a wrong body; a downgrade would let it run. See spec §6 and §11.3. |

The five-system validation and freeze criterion are in [spec §16](brass-core-spec.md#16-open-definitions).

**Bet.** Those systems expose missing mechanisms before the language expands. The experiment must preserve the requirement rather than weakening it to fit the language.
