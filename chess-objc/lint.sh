#!/bin/sh
# lint.sh — run clang-tidy over every Objective-C/C source file with the
# strictest checks (see .clang-tidy). Exits nonzero on the first failing
# file. Requires clang-tidy (Arch: clang-tools-extra).
set -e

SRC=src
TESTS=tests
OBJC_INC="$(gcc -print-file-name=include)"
COMMON="-std=gnu11 -pthread -I$SRC -isystem $OBJC_INC -O1 -Wno-unknown-warning-option"

files=""
for f in "$SRC" "$TESTS"; do
    for m in "$f"/*.m; do
        [ -e "$m" ] || continue
        files="$files $m"
    done
done

status=0
for f in $files; do
    echo "== clang-tidy: $f"
    clang-tidy "$f" -- $COMMON "$@" || status=1
done

if [ "$status" -eq 0 ]; then
    echo "lint: clean"
else
    echo "lint: FAILURES (see above)"
fi
exit "$status"