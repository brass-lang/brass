## `bin/pytool`

Put several modules in one call.

```
pytool show                               every module's declarations: the source without function bodies, in one call
pytool show --body review payment queries the whole files of several modules, in one call
pytool apply <<'PATCH'                    every edit, across every file, in one call; then compiles what changed
@@@ edit src/desk/review.py               a block: the exact text to find (once in the file) and its replacement
@@@ find
…
@@@ replace
…
@@@ end
@@@ new src/desk/advances.py              a block: a whole new file
…
@@@ end
PATCH
```

If any block does not match, nothing is written and each block is marked ✓ or ✗.

## `host-contract.txt`: the operations the host implements

Only these exist at run time.

```
@@CONTRACT@@
```
