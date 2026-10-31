# Brass documentation

Every Brass document in one place, grouped by what you're looking for.

## Start here

The two essays: what Brass is, and what the trials found.

- [Welcome to Brass Language](https://brass-lang.github.io/brass/welcome-to-brass-language.html): a getting-to-know-you tour of the language, set in a dinosaur park.
- [The AI Token Efficiency of Brass](https://brass-lang.github.io/brass/ai-token-efficiency-of-brass.html): what forty coding sessions tell us about language, tooling and cost.

## Reference

For looking things up. When two documents disagree, the specification wins.

- [Specification](brass-core-spec.md): which programs are valid, what checking establishes and how programs behave when they run.
- [Grammar](brass-core-grammar.md): how each construct is written and how its operators group.
- [Cheat sheet](brass-cheat-sheet.md): every common form on one page, with notes for Python and Rust programmers.
- [Principles](brass-core-principles.md): why the rules take the form they do, what the design gives up and what the trials established.

## Code

Brass at work, from small programs to complete systems.

- [Everyday code](brass-everyday-code.md): six ordinary programs, from FizzBuzz to retrying a call, each with a verdict on how Brass handles it.
- [Three examples](../examples/README.md): complete programs that follow permissions, promises and state changes.
  - [Refund](../examples/refund/README.md): a merchant refunds a customer on an open support case.
  - [Paddock lockdown](../examples/paddock/README.md): a staff member asks to lock a paddock down.
  - [Feeding delivery](../examples/feeding/README.md): a keeper delivers a paddock's pending feeding.

## Design notes

Companions to the specification: how the `brass` tool reports what it finds, and what a full checker has to handle.

- [Brass Info Report](design/brass-report-design.md): how `brass` shows what a function requires, what it can affect and what depends on it.
- [Brass Checker](design/brass-checker-design.md): the cases a full checker must accept and reject, its proof limits and its messages.

## Background

- [History](../HISTORY.md): how Brass went from a question to v0.3, week by week.
