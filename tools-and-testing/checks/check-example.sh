#!/bin/sh
# Run the brass stand-in's check on one example: tools/check-example.sh <refund|paddock|feeding>
# The stand-in reads a project laid out as <root>/src/; this links the example as src/ in a temporary folder.
# Known limit: the stand-in reads one source folder, so refund (payments/ and support/) reports names as undeclared.
set -eu
[ $# -eq 1 ] || { echo "usage: tools/check-example.sh <refund|paddock|feeding>" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EX="$ROOT/examples/$1"
[ -f "$EX/system.brass" ] || { echo "no example named '$1' under examples/" >&2; exit 2; }
T="$(mktemp -d)"
trap 'rm -rf "${T:?}"' EXIT
ln -s "$EX" "$T/src"
BRASS_PROJECT="$T" python3 "$ROOT/tools-and-testing/brass/bin/brass" check
