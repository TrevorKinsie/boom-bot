# Use an official Python runtime as a parent image
FROM python:3.13.3-alpine

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

# Make port 8080 available to the world outside this container (if needed for health checks, though Telegram bots usually poll)
# EXPOSE 8080 # Fly.io might require an exposed port for health checks, uncomment if needed.

# Define environment variable (optional, can be set via Fly secrets)
# ENV TELEGRAM_BOT_TOKEN=your_token_here

# Run bot.py when the container launches
CMD ["python", "bot.py"]
