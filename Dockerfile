# syntax=docker/dockerfile:1.7
# BuildKit enables the RUN --mount=type=cache lines below. Fly's remote
# builder honours it (and our deployability check builds with --remote-only),
# so dependency downloads and compile artifacts persist between deploys.

# Debian's multi-architecture packages are available on both amd64 and arm64.
# Toolchain: g++ builds the C++20 Telegram bot; gobjc + libobjc build the
# in-house Objective-C chess engine (chess-objc/); openjdk-17 + rustc/cargo
# build the JVM decision engine; node/npm/curl build the MMO game service (its
# HTTP client is TypeScript and its build vendors the sqlite-jdbc driver over
# HTTPS).
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        gobjc \
        libobjc-12-dev \
        openjdk-17-jdk-headless \
        rustc \
        cargo \
        nodejs \
        npm \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV CHESS_ENGINE_PATH=/app/chess-objc/build/chess-objc

# Set the working directory in the container
WORKDIR /app

# Copy the application source into the container at /app
COPY . .

# Compile the C++20 Telegram bot and run its self-tests (794 checks).
RUN ./bot-cpp/build.sh && ./bot-cpp/build/boombot-tests > /tmp/boombot-tests.log && tail -1 /tmp/boombot-tests.log

# Compile the Objective-C chess engine (builds build/chess-objc).
RUN make -C chess-objc all

# Compile the JVM decision engine (jar + Rust atomic_cli binary).
# Cache mounts keep the cargo registry and the incremental target dir warm
# across deploys; the crate is dependency-free, so this is near-instant anyway.
RUN --mount=type=cache,target=/root/.cargo \
    --mount=type=cache,target=/app/decision-engine/rust-atomic-logic/target \
    ./decision-engine/build.sh

# Compile the MMO game service (jar + browser client + vendored sqlite-jdbc).
# Cache mounts persist the vendored 13 MB sqlite-jdbc jar and the compiled TS
# client; build.sh still recompiles all Java sources and re-packages the jar,
# but skips re-downloading the driver and re-running tsc.
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/app/mmo-server/build \
    ./mmo-server/build.sh

# Run the Telegram bot and the MMO game service (HTTP website) together.
CMD ["bash", "start.sh"]
