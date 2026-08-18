#!/bin/sh
# Run the wagering service self-tests.
set -eu

cd "$(dirname "$0")"

./build.sh
./build/wagering-service-tests