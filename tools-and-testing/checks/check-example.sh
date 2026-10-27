#!/bin/sh
# Run brass on one example: tools-and-testing/checks/check-example.sh <paddock|feeding|refund>
# brass reads a project laid out as <root>/src/; this links the example as src/ in a temporary folder
# and runs `brass check` in the recommended mode (BRASS_LEAN=8). Exits 0 when the check ends with `done`.
# Known limit: brass reads one source folder, so refund (payments/ and support/) reports one false rejection.
set -eu
[ $# -eq 1 ] || { echo "usage: tools-and-testing/checks/check-example.sh <paddock|feeding|refund>" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EX="$ROOT/examples/$1"
[ -f "$EX/system.brass" ] || { echo "no example named '$1' under examples/" >&2; exit 2; }
T="$(mktemp -d)"
trap 'rm -rf "${T:?}"' EXIT
ln -s "$EX" "$T/src"
OUT="$(BRASS_LEAN=8 BRASS_PROJECT="$T" python3 "$ROOT/tools-and-testing/brass/bin/brass" check)"
printf '%s\n' "$OUT"
printf '%s\n' "$OUT" | grep -q '^done' || exit 1
