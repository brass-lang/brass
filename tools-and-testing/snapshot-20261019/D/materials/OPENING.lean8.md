## `bin/brass`

The starting tree passes `bin/brass check`. Put several names in one call.

```
brass show                               the index: every module, its length, declaration names, and imports
brass show review payment budget         those modules' declarations with their contracts; several per call
brass show --for audit.Entry queries.Row what an edit of these needs: each declaration with its body, then every declaration that uses it, with its body
brass show --body review payment queries the whole files of several modules, in one call, verbatim (copy find text from it as is)
brass info <module>.<name> [...]         what uses each declaration, and how
brass apply <<'PATCH'                    every edit, across every file, in one call; checked before anything is written
@@@ decl src/desk/payment.brass pay       a block: a declaration by name; `@@@ interface` then its interface lines, and/or `@@@ body` then its body, each replaced whole; a name the file does not declare is added
@@@ interface
…
@@@ body
…
@@@ end
@@@ edit src/desk/review.brass            a block: the text to find (once in the file; a wrong indent is forgiven and reported) and its replacement
@@@ find
…
@@@ replace
…
@@@ end
@@@ new src/desk/advances.brass           a block: a whole new file (on a file that exists, it replaces the whole file and says so)
…
@@@ end
PATCH
brass check                              the completion gate on its own; `apply` already runs it
```

`apply` checks before it writes. If every block matches and the check finds nothing new to reject, it writes and the answer ends with how many declarations changed. Otherwise nothing is written, the blocks that matched are held, and the answer names each ✗ block and each rejected line. Then send only what changes: a block with the same file and find text, the same new file, or the same declaration replaces the held one; any other block applies on top of what is held. `brass apply --drop` discards a held patch. An answer longer than about 26k characters stops at a module boundary and names what it left out; ask for those in the next call. `check` covers structure, examples, scenarios, the host contract (`host-contract.txt`), the order of writes against refusals, machine states passed to calls, declared types loosened to a builtin, and what each entry point you touched now does; a clean check ends with `done`, and `⚠` lines are for you to read before you finish.

## `host-contract.txt`: the operations the host implements

Only these exist at run time; `check` rejects any other `allow`.

```
@@CONTRACT@@
```
