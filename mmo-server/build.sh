#!/usr/bin/env bash
#
# Build the boom-bot MMO game service without Maven (JDK only + one vendored
# SQLite JDBC driver bundled inside the jar).
#
#   1. vendor the sqlite-jdbc jar (idempotent; only downloads if missing)
#   2. compile Java sources with javac
#   3. package the game-service jar with static assets and the SQLite driver
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT/src/main/java"
STATIC_DIR="$ROOT/src/main/resources/static"
BUILD_DIR="$ROOT/build"
CLASSES_DIR="$BUILD_DIR/classes"
SQLITE_VERSION="3.43.0.0"
SQLITE_JAR="$BUILD_DIR/sqlite-jdbc-$SQLITE_VERSION.jar"

echo "==> Vendoring sqlite-jdbc $SQLITE_VERSION..."
mkdir -p "$BUILD_DIR"
if [ ! -f "$SQLITE_JAR" ]; then
    URL="https://repo1.maven.org/maven2/org/xerial/sqlite-jdbc/$SQLITE_VERSION/sqlite-jdbc-$SQLITE_VERSION.jar"
    if ! curl -fsSL -o "$SQLITE_JAR" "$URL"; then
        echo "    [warn] could not download sqlite-jdbc from $URL" >&2
        exit 1
    fi
    echo "    driver -> $SQLITE_JAR"
else
    echo "    driver already present -> $SQLITE_JAR"
fi

echo "==> Compiling Java sources..."
rm -rf "$CLASSES_DIR"
mkdir -p "$CLASSES_DIR"
find "$SRC_DIR" -name '*.java' | sort > "$BUILD_DIR/mmo-sources.txt"
javac --release 17 -encoding UTF-8 -cp "$SQLITE_JAR" -d "$CLASSES_DIR" @"$BUILD_DIR/mmo-sources.txt"

echo "==> Compiling TypeScript client..."
if [ ! -x "$ROOT/node_modules/.bin/tsc" ]; then
    echo "    [warn] TypeScript not installed; running 'npm install' (needs network)" >&2
    npm install --no-audit --no-fund
fi
if [ -x "$ROOT/node_modules/.bin/prettier" ]; then
    if ! "$ROOT/node_modules/.bin/prettier" --check "$STATIC_DIR"/*.ts >/dev/null 2>&1; then
        echo "    [warn] client not Prettier-formatted; run: npm run format" >&2
    fi
fi
"$ROOT/node_modules/.bin/tsc" -p "$ROOT/tsconfig.json"
echo "    client js -> $BUILD_DIR/client-js/app.js"

echo "==> Packaging game service jar..."
STAGE="$BUILD_DIR/stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -r "$CLASSES_DIR/." "$STAGE/"
# Bundle static client assets so the server can serve the browser game from
# the jar. app.ts is compiled by tsc above; app.js is the emitted artifact.
cp -r "$STATIC_DIR/." "$STAGE/static/"
cp "$BUILD_DIR/client-js/app.js" "$STAGE/static/app.js"
rm -f "$STAGE/static/app.ts" "$STAGE/static/three.d.ts"

cat > "$BUILD_DIR/MANIFEST.MF" <<EOF
Manifest-Version: 1.0
Main-Class: com.boombot.mmo.MmoServerMain
Class-Path: sqlite-jdbc-$SQLITE_VERSION.jar
EOF
jar cfm "$BUILD_DIR/mmo-server.jar" "$BUILD_DIR/MANIFEST.MF" -C "$STAGE" .

echo "==> Done."
echo "    jar -> $BUILD_DIR/mmo-server.jar"