#!/bin/sh
# Launch one rerun session headless, as its own instance: from inside its own project directory, so its context holds
# no git status, no CLAUDE.md, and no memory (the working directory is outside every repository, and only project and
# local settings load; there are none), and in a cleaned environment, so it inherits nothing from the session that
# launched it: no CLAUDECODE or CLAUDE_CODE_* identity, no settings overrides. What passes through: PATH, HOME, USER,
# LANG, TMPDIR, TERM, CLAUDE_CONFIG_DIR (where the sign-in lives), and ANTHROPIC_* (an API key or endpoint, when the
# environment signs in that way). Every other variable is dropped.
#
# usage: RERUN_MODEL=<model id> RERUN_EFFORT=<level> launch.sh <session-dir>
#        the directory a builder made: <session-dir>/project and <session-dir>/prompt.md
set -eu
: "${RERUN_MODEL:?set RERUN_MODEL to the model every session of this rerun uses}"
: "${RERUN_EFFORT:?set RERUN_EFFORT to the effort every session of this rerun uses}"
S="$(cd "$1" && pwd)"
cd "$S/project"
KEEP="PATH=$PATH HOME=$HOME USER=${USER:-} LANG=${LANG:-C.UTF-8} TMPDIR=${TMPDIR:-/tmp} TERM=${TERM:-dumb}"
[ -n "${CLAUDE_CONFIG_DIR:-}" ] && KEEP="$KEEP CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR"
for v in $(env | grep -E '^ANTHROPIC_[A-Z_]+=' | cut -d= -f1); do
  KEEP="$KEEP $v=$(printenv "$v")"
done
env | cut -d= -f1 | sort > "$S/env-before.txt"                  # names only: a value may be a key
# shellcheck disable=SC2086
env -i $KEEP sh -c 'env' | cut -d= -f1 | sort > "$S/env-session.txt"
# shellcheck disable=SC2086
env -i $KEEP claude -p --model "$RERUN_MODEL" --effort "$RERUN_EFFORT" --setting-sources project,local \
  --allowed-tools "Read,Edit,Write,Glob,Grep,Bash" --permission-mode acceptEdits \
  --output-format json "$(cat "$S/prompt.md")" > "$S/result.json" 2> "$S/stderr.txt"
