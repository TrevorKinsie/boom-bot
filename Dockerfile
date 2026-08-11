# Use an official Python runtime as a parent image.
# Debian's multi-architecture package is available on both amd64 and arm64;
# Alpine 3.22 does not publish a stockfish package.
FROM python:3.13.3-slim

# Stockfish is the native UCI engine used by the Chess Challenge feature.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && ln -s /usr/games/stockfish /usr/local/bin/stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish

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

CMD ["python", "main.py"]
