# Use an official Python runtime as a parent image
FROM python:3.13.3-alpine

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

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

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Make port 8080 available for health checks
EXPOSE 8080

# Define environment variable (optional, can be set via Fly secrets or Kubernetes Secrets/ConfigMaps)
# ENV TELEGRAM_BOT_TOKEN=your_token_here

# Run the bot using the new entry point
CMD ["python", "main.py"]
