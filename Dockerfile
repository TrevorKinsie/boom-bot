# Use an official Python runtime as a parent image.
# Debian's multi-architecture package is available on both amd64 and arm64;
# Alpine 3.22 does not publish a stockfish package.
FROM python:3.13.3-slim

# Stockfish is the native UCI engine used by the Chess Challenge feature.
# openjdk-17-jdk-headless + rustc/cargo are the toolchain for the JVM Decision
# Engine: the decision fabric delegates game outcomes to the JVM, which asks
# the Rust atomic-logic layer for pure randomness.
# nodejs/npm/curl build the MMO game service: its client is TypeScript and its
# build vendors the sqlite-jdbc driver over HTTPS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
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

# The JVM decision engine ships with the container (mode=auto engages it).
ENV DECISION_ENGINE_MODE=auto

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -m nltk.downloader punkt wordnet averaged_perceptron_tagger stopwords

# Copy the rest of the application code into the container at /app
COPY . .

# Install the package in development mode
RUN pip install -e .

# Compile the JVM decision engine (jar + Rust atomic_cli binary)
RUN ./decision-engine/build.sh

# Compile the MMO game service (jar + browser client + vendored sqlite-jdbc)
RUN ./mmo-server/build.sh

# Run the Telegram bot and the MMO game service (HTTP website) together.
CMD ["bash", "start.sh"]
