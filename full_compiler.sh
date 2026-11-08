#!/usr/bin/env bash
set -e

LLC="${LLC:-llc}"
if ! command -v "$LLC" >/dev/null 2>&1; then
    if [ -x "/usr/local/Cellar/llvm@15/15.0.7/bin/llc" ]; then
        LLC="/usr/local/Cellar/llvm@15/15.0.7/bin/llc"
    elif [ -x "/opt/homebrew/opt/llvm@15/bin/llc" ]; then
        LLC="/opt/homebrew/opt/llvm@15/bin/llc"
    fi
fi

SRC="${1:-tests/io/points.txt}"
OUT="${2:-points}"

BASE=$(basename "$SRC" .txt)
DIR=$(mktemp -d)
LL_FILE="$DIR/$BASE.ll"
OBJ_FILE="$DIR/$BASE.o"

python3 compiler.py "$SRC" "$LL_FILE"
"$LLC" -filetype=obj -relocation-model=pic "$LL_FILE" -o "$OBJ_FILE"
clang -fPIE "$OBJ_FILE" -o "$OUT"

rm -rf "$DIR"

