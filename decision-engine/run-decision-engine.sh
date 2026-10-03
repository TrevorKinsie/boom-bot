#!/usr/bin/env bash
#
# Run the JVM decision engine as a long-lived JSON-lines process.
# Reads one JSON request per line on stdin, writes one JSON response per line
# on stdout. Point DECISION_ENGINE_RUST_BIN at the built atomic_cli binary to
# enable the Rust atomic-logic path.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR="$ROOT/build/jvm-decision-engine.jar"

if [ ! -f "$JAR" ]; then
    echo "decision engine not built; run ./build.sh first" >&2
    exit 1
fi

: "${DECISION_ENGINE_RUST_BIN:=$ROOT/build/atomic_cli}"
if [ ! -x "$DECISION_ENGINE_RUST_BIN" ]; then
    echo "[warn] rust atomic binary not found at $DECISION_ENGINE_RUST_BIN; using in-JVM reference atomic logic" >&2
fi
export DECISION_ENGINE_RUST_BIN

exec java -jar "$JAR"
