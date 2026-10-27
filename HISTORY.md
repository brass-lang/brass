# History

Brass began in early September 2026 with a question: how could a programming language help AI models build context and reason about code more efficiently? By October 25, about 615 commits over seven weeks had brought the specification to v0.3, and on October 27 it was published.

This history follows the decisions, reviews and trials that shaped the language and its tooling, including the questions that remain open.

The author made the language decisions. AI models drafted most of the text, built the trial tooling and took part as trial subjects. The language was originally called Keel, so earlier sections and trial records retain that name.

## In brief

The design puts the facts a model needs in declarations, reducing the need to search for them or work them out from an implementation. Each function says what it needs, promises and may touch. `brass` finds those facts today; the full checker will reject edits that break them.

- **Fewer calls, less repeated context.** In the latest Sonnet trial, Brass took fewer than half as many model calls as Python and sent less than half as much text across them. The average bill was 14 to 24 percent lower.
- **More reasoning.** Sonnet used 1.4 to 1.8 times as many reasoning tokens in Brass. The working explanation is unfamiliarity; that remains to be tested.
- **Tooling matters.** Giving Python a similar tool and project map recovered most of the difference in total context in an earlier trial.

Here, Brass means the language and its tooling. Today, `brass` checks program structure, runs examples and helps models navigate the code. The full checker and a runtime are next.

## Week 1 — The report, the first review, the first trials

Work began with how a model would find its way around unfamiliar code. A broad `keelc info` query would return an index; naming one function would show its declaration, promises and callers.

The first review also settled much of the vocabulary. Authority became `access` and `allow`, promises became `before` and `after`, and a function that could fail had to say so in its return type.

v0.2 was meant to establish the language's essentials. The checker could come later; first, the code and its declarations had to make sense together.

The early trials passed their review checklists, but editing Keel cost more than Python. Reducing the back-and-forth became the tool's next priority. Outside feedback also caught errors in token accounting, which was corrected to count the input sent on every model call.

**Questions at the time**

- What does Brass offer that Python or Go doesn't?
- Will models still need programming languages at all?
- Can a model write an ordinary algorithm without piles of scaffolding?

## Week 2 — Less, not more

Version numbers moved out of source files, and imports settled on one form. The standing rule became: look for something to remove before adding another mechanism.

Contracts stayed optional. A function without a written promise is still checked for types, authority and legal state changes.

Shorter code is not necessarily cheaper to work with. Repeated fields or an explicit type may save a model from searching several files to understand a value. The principle became: judge the work a change requires, not just its token count.

**Questions at the time**

- Should connecting to an independently run system feel as easy as importing a module? How would the two establish trust?
- Does the language need events, independent of how they are delivered?
- Should Brass run on WebAssembly?

## Week 3 — The review closes, v0.2 comes together

Projection settled into its current form. A record explicitly declares which smaller records it can stand in for. The receiving code gets just the fields it needs, without following an inheritance tree, and projections never chain.

Seven blind review passes caught stale rules, duplication and gaps between documents. The list of reasons a call can stop came down to eight. The spec was reordered to introduce the language before its edge cases.

The v0.2 package came together around three complete programs: a refund, a paddock lockdown and a feeding. Outside readers could follow the language, but the READMEs needed to explain each program's promises and what they left unchecked.

**Questions at the time**

- Is projection polymorphism, inheritance, or neither?
- Should interfaces live in their own files, like C headers?

## Week 4 — Where the cost goes

The language adopted familiar spellings where their meanings fit: `?` to pass a failure to the caller, `in` for membership, `is` for type tests, and `Maybe` for a value that can be absent.

The main trial asked a model to add cash advances to an expense-report system. Batching reads, edits and checks reduced the number of calls. In the scale trial, the codebase grew to 2.5 times its size, but the total text sent to the model grew by only 8% for Brass.

One language question kept causing trouble: how should an audit record hold either a report's state or an advance's state? Sessions invented different representations, some of them wrong. The fix was one shared vocabulary with a converter from each machine. In the [follow-up trial](tools-and-testing/earlier-tests/16-settled/), reasoning fell by about 30% and cost came in below Python's. The pattern later became the rule for these fields.

Simple changes, such as a rename or a summing function, showed no extra reasoning cost.

The keyword review removed `partial`, which repeated what `Outcome<T>` already said, and an unused way of loading data. It also clarified `private`, `const` and fields that exist only in particular states. Brass was chosen as the new name.

**Questions at the time**

- Was the saving in the language or the tooling? Giving [Python a similar tool and map](tools-and-testing/earlier-tests/18-python-tool/) recovered most of the context saving.
- Is Keel functional or object-oriented? Its basic approach is functions and data, with projection for sharing fields.
- How much of the extra reasoning comes from the design, and how much from unfamiliarity?

## Week 5 — Keel becomes Brass

The rename happened in one pass: Keel became Brass, `keelc` became `brass`, and `.keel` files became `.brass`. Earlier trial records kept their original names so they would still describe what ran.

The label for unchecked promises changed from *trusted* to *assumed*. The new name makes clear that the program relies on something it cannot check. The rules also required a changed module to be checked again before the program could run.

A `learn` command offered short guides to language patterns. Sessions used it only when the list of guides was shown up front, and putting the guide straight in the prompt cost less. The command was left for later.

The publishing plan settled too: Apache-2.0 for code, CC BY 4.0 for prose, two introductory pages, a short README and detailed reference documents. The point of publishing was to put the design in front of people who had not helped build it.

**Questions at the time**

- How much of a codebase should one edit touch before a person has to look?

## Week 6 — The rerun

The public repository came together, and the trials were rebuilt on current Brass. `apply` began checking patches before writing them.

A new task asked models to manage trip budgets, amendments and reconciliation against actual spending. Its first trial put Brass and Python at similar cost. Python was cheaper on Opus.

The [October 19 rerun](tools-and-testing/snapshot-20261019/runs/sonnet5-20261019-d/REPORT.md) covered 40 Sonnet sessions: cash advances at two codebase sizes, plus trip plans. Brass used fewer calls and cost less, but needed more reasoning. Thirteen of fifteen Brass sessions passed every hidden test, against Python's fifteen. The ten language-only sessions also passed every test, but cost more than Python.

Eight reviewers read the programs without scores or setup labels. They found two language violations the tool had missed and an audit behavior the task had left ambiguous.

**Questions at the time**

- Is the extra reasoning the model working out proofs it cannot ask the tool to check yet?
- Would Python with the same tooling match Brass on trip plans?

## Week 7 — Writing it up

*The AI Token Efficiency of Brass* (first called Tokens in Plain Ink) was rebuilt around the rerun, with new charts and results. The comparison now used “Brass” for the language and tooling together, and “language only” for sessions using ordinary file tools.

Worked through *Welcome to Brass Language* (first called Brass in Plain Ink) line by line. The park examples became a connected story: update a paddock's record, give the code authority to close the door, then show which wrong edits the declarations catch. The page explains the design through code; the spec and grammar hold the detailed rules.

A cheat sheet put the forms in one place, with notes for Python and Rust programmers. The README became a shorter introduction, and the public repository was trimmed to the records behind the published results.

## Week 8 — Publication

The public repository took its final shape: the language documents and the two reader pages under `docs/`, the README, this history and the licenses at the root. Both pages were exported as standalone files, and a site builder renders the README and the documents as GitHub Pages.

The README gained two charts from the write-up, a short FAQ and a request for comments. Two outside reviews prompted the last corrections: licensing stated in one place, CC BY 4.0 for documents and Apache 2.0 for code; references to private notes replaced with what is unpublished; a first command to run in the examples README. Checks now run on every push: the grammar against the spec, and the three examples through `brass`.

On October 27 the repository went public at [github.com/brass-lang/brass](https://github.com/brass-lang/brass), with a fresh history, and the site went live at [brass-lang.github.io/brass](https://brass-lang.github.io/brass/). Brass v0.3 is out for comment.

## Still to decide

- **How Brass runs.** Compile directly, perhaps to WebAssembly, or translate to a language with a mature compiler.
- **Memory.** Values do not change in place, and each task has a memory limit. The implementation still needs to decide how those values are stored, shared and freed.
- **The full checker.** How to prove the declared promises quickly enough to support repeated edits.
- **Python with tooling like `brass`.** Early tests included some preliminary testing of Python with context tooling similar to `brass`. Not investigated further due to time constraints; worth revisiting.

## Ideas from other languages

When ideating Brass, a bunch of languages were looked at through the lens of what might work well in an AI context. A few ideas were borrowed from this research.

### Rust

`?` passes a failure to the caller. Rust's typestate pattern also offers a way to make a value's state part of its type; Brass makes states and their allowed moves explicit through `machine` and `enters`.

### Kotlin and Swift

Kotlin's `in` and `is` separate membership from type tests. Swift's `!` and Kotlin's `!!` suggest “fail if absent,” which made `!` a poor choice for passing an ordinary error to a caller.

Brass's `Maybe<T>` keeps absence in the type: a value is either a `T` or `None`. The caller checks before using it.

### Python

Open brackets let a declaration continue across lines, and `any` and `all` express questions about a collection. Brass keeps missing arguments explicit: a caller supplies `None` rather than relying on a default.

### Java and C#

Brass leaves out classes, inheritance and dynamic dispatch. A record declares its fields in full, and projection lets it supply a smaller record without inheriting behavior. Integers are signed only; “never negative” is a condition on the type, not an unsigned type.

### C

C and Python give `a < b < c` different meanings. Brass requires both comparisons to be written out rather than guess which meaning was intended.

### Dafny, SPARK and Eiffel

Dafny and SPARK prove contracts; Eiffel checks them while the program runs. Brass's design uses both proof and runtime checks, with a label showing what supports each promise. `before` and `after` put the conditions at the two ends of a call.

### OCaml and Ada

Separating an interface from its implementation lets callers work from a declaration. Brass keeps both in one file, with each function's types and promises together above its body.

### Object-capability languages (E, Pony)

Authority travels through a value a function holds. In Brass, it arrives as a parameter: no database connection or door controller is available just because the function knows its name.

### WebAssembly

The Component Model is a candidate for connecting Brass programs to the software around them. Not yet part of Brass, but a strong directional consideration as a runtime platform.

## What's unique to Brass

Most of these ideas exist somewhere else. What's unique is the combination, and who it's for: a model writing the code and a person reviewing it.

- **Every rule pays two costs.** Each one is judged by what it costs a model to make a change, and what it costs a person to check that change.
- **One line does two jobs.** On an access operation, the part of a `before` that names one of its bounds is the authority check, enforced when the program runs. Everything else in a `before` is a promise the checker must prove. Same form, read the same way.
- **Every promise says how far to trust it.** Proven by the checker, enforced when the program runs, or assumed with nothing checking it. The reviewer sees the label and knows what to trust.
- **A field can exist only in some states.** A delivered feeding has a signer. A planned feeding has no such field, and the checker refuses any code that reads it there.
- **Projection instead of inheritance.** A record lists the smaller records it can stand in for. Passing it copies those fields and nothing else: no behavior comes along, and a projection never chains. To understand a type, you read one declaration, not a chain of parents.
- **The interface is what gets reviewed.** A body can be rewritten as long as its promises hold. Behavior the promises don't cover still needs a test or a look.
- **The tool is part of the language.** `brass` answers the questions a model would otherwise search for: what a function may reach, who calls it, what an edit breaks.
- **An `example` is a built-in test.** One call and the answer it must give. It runs at every check and is reported as tested, never as proven.
