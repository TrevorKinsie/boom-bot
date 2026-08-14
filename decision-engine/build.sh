#!/usr/bin/env bash
#
# Build the whole JVM decision engine:
#   1. compile the Rust atomic-logic crate (release) -> build/atomic_cli
#   2. compile the Java middleware (javac)           -> build/classes
#   3. package the jar                               -> build/jvm-decision-engine.jar
#
# The Rust step is optional: if `cargo` is unavailable the build still
# succeeds and the running engine simply uses the in-JVM reference atomic
# logic. The Java step is mandatory.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUST_DIR="$ROOT/rust-atomic-logic"
JAVA_DIR="$ROOT/java-middleware"
BUILD_DIR="$ROOT/build"
CLASSES_DIR="$BUILD_DIR/classes"

echo "==> Building Rust atomic logic (pure primitives)..."
if command -v cargo >/dev/null 2>&1; then
    (cd "$RUST_DIR" && cargo build --release)
    RUST_BIN="$RUST_DIR/target/release/atomic_cli"
    if [ -x "$RUST_BIN" ]; then
        mkdir -p "$BUILD_DIR"
        cp "$RUST_BIN" "$BUILD_DIR/atomic_cli"
        echo "    Rust binary   -> $BUILD_DIR/atomic_cli"
    fi
else
    echo "    [warn] cargo not found; the engine will use the in-JVM reference atomic logic."
fi

echo "==> Compiling Java middleware..."
rm -rf "$CLASSES_DIR"
mkdir -p "$CLASSES_DIR"
find "$JAVA_DIR/src/main/java" -name '*.java' > "$BUILD_DIR/sources.txt"
javac -d "$CLASSES_DIR" @"$BUILD_DIR/sources.txt"

echo "==> Packaging decision engine jar..."
cat > "$BUILD_DIR/MANIFEST.MF" <<'EOF'
Manifest-Version: 1.0
Main-Class: com.boombot.decisionengine.Main
EOF
jar cfm "$BUILD_DIR/jvm-decision-engine.jar" "$BUILD_DIR/MANIFEST.MF" -C "$CLASSES_DIR" .

echo "==> Done."
echo "    jar  -> $BUILD_DIR/jvm-decision-engine.jar"
echo "    rust -> $BUILD_DIR/atomic_cli"
