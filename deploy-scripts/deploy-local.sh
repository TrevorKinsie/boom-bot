#!/bin/bash

# Script to build and deploy the boom-bot to local Kubernetes (Docker Desktop)

set -e # Exit immediately if a command exits with a non-zero status.

# Determine the script's directory and the project root directory
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd ) # Assumes script is one level down

# Define paths relative to the project root
IMAGE_NAME="local-test/boom-bot:latest"
DEPLOYMENT_NAME="boom-bot-deployment"
SECRET_FILE="$PROJECT_ROOT/secrets/secret.yaml"
SECRET_EXAMPLE_FILE="$PROJECT_ROOT/secrets/secret.ex.yaml"
DEPLOYMENT_FILE="$PROJECT_ROOT/deployment.yaml"
DOCKER_CONTEXT="$PROJECT_ROOT" # Docker build context is the project root

# --- Prerequisites Check ---

echo "Checking prerequisites..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker does not seem to be running. Please start Docker Desktop." >&2
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl command could not be found. Please install kubectl." >&2
    exit 1
fi

# Check kubectl context
CURRENT_CONTEXT=$(kubectl config current-context)
if [ "$CURRENT_CONTEXT" != "docker-desktop" ]; then
    echo "Warning: kubectl context is not set to 'docker-desktop'. Attempting to switch..." >&2
    if ! kubectl config use-context docker-desktop; then
        echo "Error: Could not switch kubectl context to 'docker-desktop'. Please ensure Kubernetes is enabled in Docker Desktop and the context exists." >&2
        exit 1
    fi
    echo "Successfully switched kubectl context to 'docker-desktop'."
fi

# Check Kubernetes node status (basic check)
if ! kubectl get nodes > /dev/null 2>&1; then
    echo "Error: Cannot connect to Kubernetes cluster via kubectl. Ensure Kubernetes is enabled and running in Docker Desktop." >&2
    exit 1
fi

echo "Prerequisites met."

# --- Secret Handling ---

if [ ! -f "$SECRET_FILE" ]; then
    echo "Secret file ($SECRET_FILE) not found."
    if [ -f "$SECRET_EXAMPLE_FILE" ]; then
        echo "Please copy '$SECRET_EXAMPLE_FILE' to '$SECRET_FILE' and replace '<base64-encoded-dev-token>' with your actual BASE64 ENCODED Telegram Bot token."
        echo "You can encode your token using: echo -n 'YOUR_ACTUAL_TOKEN' | base64"
    else
        echo "Example secret file ($SECRET_EXAMPLE_FILE) also not found. Cannot proceed without secrets."
    fi
    exit 1
fi

# Basic check if placeholder is still present
if grep -q "<base64-encoded-dev-token>" "$SECRET_FILE"; then
    echo "Error: Placeholder '<base64-encoded-dev-token>' found in $SECRET_FILE. Please replace it with your actual Base64 encoded token." >&2
    exit 1
fi

# --- Build Stage ---

echo "Building Docker image: $IMAGE_NAME from context: $DOCKER_CONTEXT ..."
# Use -f to specify Dockerfile location relative to context if it's not at the root
# Assuming Dockerfile is at PROJECT_ROOT/Dockerfile
docker build -t "$IMAGE_NAME" "$DOCKER_CONTEXT"
# If Dockerfile is elsewhere, e.g., PROJECT_ROOT/build/Dockerfile:
# docker build -f "$PROJECT_ROOT/build/Dockerfile" -t "$IMAGE_NAME" "$DOCKER_CONTEXT"
echo "Docker image built successfully."

# --- Deploy Stage ---

echo "Applying Kubernetes secret ($SECRET_FILE)..."
kubectl apply -f "$SECRET_FILE"

echo "Applying Kubernetes deployment ($DEPLOYMENT_FILE)..."
kubectl apply -f "$DEPLOYMENT_FILE"

# --- Rollout (Optional but recommended for updates) ---

# Check if the deployment already exists before attempting a rollout restart
if kubectl get deployment "$DEPLOYMENT_NAME" > /dev/null 2>&1; then
    echo "Triggering deployment rollout restart to ensure the latest image is used..."
    kubectl rollout restart deployment "$DEPLOYMENT_NAME"
else
    echo "Deployment is new, rollout restart not needed yet."
fi

# --- Post-Deployment Info ---

echo "Deployment process initiated."
echo "You can check the status with:"
echo "  kubectl get pods -l app=boom-bot"
echo "Once a pod is 'Running', check logs with:"
echo "  kubectl logs <pod-name>"

