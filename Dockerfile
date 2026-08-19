# Debian's multi-architecture packages are available on both amd64 and arm64.
# Toolchain: g++ builds the C++20 Telegram bot; openjdk-17 + rustc/cargo build
# the JVM decision engine; node/npm/curl build the MMO game service (its client
# is TypeScript and its build vendors the sqlite-jdbc driver over HTTPS).
# stockfish is the retained Chess Challenge reference engine.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        stockfish \
        openjdk-17-jdk-headless \
        rustc \
        cargo \
        nodejs \
        npm \
        curl \
    && ln -s /usr/games/stockfish /usr/local/bin/stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish

# Set the working directory in the container
WORKDIR /app

# Copy the application source into the container at /app
COPY . .

# Compile the C++20 Telegram bot and run its self-tests (751 checks).
RUN ./bot-cpp/build.sh && ./bot-cpp/build/boombot-tests > /tmp/boombot-tests.log && tail -1 /tmp/boombot-tests.log

# Compile the JVM decision engine (jar + Rust atomic_cli binary)
RUN ./decision-engine/build.sh

# Compile the MMO game service (jar + browser client + vendored sqlite-jdbc)
RUN ./mmo-server/build.sh

# Run the Telegram bot and the MMO game service (HTTP website) together.
CMD ["bash", "start.sh"]
