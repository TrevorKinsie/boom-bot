#!/bin/sh
# Build the wagering service and its self-tests with a bare gcc toolchain.
# Offline: no external crypto or JSON libraries - everything is in src/.
set -eu

cd "$(dirname "$0")"

CC=${CC:-gcc}
CFLAGS=${CFLAGS:--O2 -std=c11 -Wall -Wextra -pedantic -D_POSIX_C_SOURCE=200809L}

mkdir -p build

$CC $CFLAGS -Isrc -o build/wagering-service src/bb_util.c src/bb_json.c \
    src/bb_money.c src/bb_cipher.c src/bb_wallet.c src/bb_store.c \
    src/main.c -lm

$CC $CFLAGS -DBB_TEST -Isrc -o build/wagering-service-tests tests/test_main.c \
    src/bb_util.c src/bb_json.c src/bb_money.c src/bb_cipher.c \
    src/bb_wallet.c src/bb_store.c src/main.c -lm

echo "built: build/wagering-service build/wagering-service-tests"