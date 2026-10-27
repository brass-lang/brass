# Using `brass`

The starting tree passes `bin/brass check`. Put several names in one call.

```
brass show                               the index: every module, its length, declaration names, and imports
brass show review payment budget         those modules' declarations with their contracts; several per call
brass show --for audit.Entry queries.Row what an edit of these needs: each declaration with its body, then every declaration that uses it, with its body
brass show --body review payment queries the whole files of several modules, in one call
brass info <module>.<name> [...]         what uses each declaration, and how
brass apply <<'PATCH'                    every edit, across every file, in one call; checked before anything is written
@@@ edit src/desk/review.brass            a block: the exact text to find (once in the file) and its replacement
@@@ find
…
@@@ replace
…
@@@ end
@@@ new src/desk/advances.brass           a block: a whole new file
…
@@@ end
PATCH
brass check                              the completion gate on its own; `apply` already runs it
```

If any block does not match, nothing is written and each block is marked ✓ or ✗. `check` covers structure, examples, scenarios, the host contract (`host-contract.txt`), the order of writes against refusals, and what each entry point you touched now does; a clean check ends with `done`.
