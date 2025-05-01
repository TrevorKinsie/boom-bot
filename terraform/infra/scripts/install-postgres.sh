#!/bin/bash
# PostgreSQL installation script for Kubernetes
# This script installs PostgreSQL on a Kubernetes cluster using Helm

set -e

# Check if arguments are provided
POSTGRES_PASSWORD=${1:-postgres}
POSTGRES_DATABASE=${2:-postgres}
POSTGRES_USER=${3:-postgres}

# Create installation log
LOGFILE="/var/log/postgres-install.log"
exec > >(tee -a ${LOGFILE}) 2>&1

echo "Starting PostgreSQL installation at $(date)"

# Create a marker file to track installation status
MARKER_FILE="/etc/kubernetes/.postgres-installation-complete"

# Ensure KUBECONFIG is set if not already set
if [ -z "$KUBECONFIG" ] && [ -f "/etc/kubernetes/admin.conf" ]; then
  export KUBECONFIG=/etc/kubernetes/admin.conf
  echo "KUBECONFIG set to /etc/kubernetes/admin.conf"
fi

# Check if Kubernetes is accessible
if ! kubectl get nodes &> /dev/null; then
  echo "Error: Cannot access Kubernetes cluster. Ensure the cluster is running and configured."
  echo "Try running: export KUBECONFIG=/etc/kubernetes/admin.conf"
  exit 1
fi

echo "Kubernetes cluster is accessible."
kubectl get nodes

# Check if PostgreSQL is already installed in the cluster
if kubectl get namespace postgres &> /dev/null; then
  echo "PostgreSQL namespace already exists. Checking for running pods..."
  
  if kubectl get pods -n postgres -l app.kubernetes.io/name=postgresql &> /dev/null; then
    RUNNING_PODS=$(kubectl get pods -n postgres -l app.kubernetes.io/name=postgresql --field-selector=status.phase=Running --no-headers | wc -l)
    
    if [ "$RUNNING_PODS" -gt 0 ]; then
      echo "PostgreSQL is already installed and running in the cluster."
      echo "PostgreSQL service details:"
      kubectl get svc -n postgres
      
      # Check if values file has changed
      if [ -f "$MARKER_FILE" ]; then
        OLD_CHECKSUM=$(cat "$MARKER_FILE")
        NEW_CHECKSUM=$(md5sum /tmp/postgres-values.yaml | awk '{print $1}')
        
        if [ "$OLD_CHECKSUM" = "$NEW_CHECKSUM" ]; then
          echo "No changes detected in PostgreSQL configuration. Skipping update."
          exit 0
        else
          echo "Changes detected in PostgreSQL configuration. Will update the deployment."
        fi
      else
        echo "Marker file not found, but PostgreSQL is running. Will update with current values."
      fi
    else
      echo "PostgreSQL namespace exists but no running pods found. Will reinstall."
    fi
  else
    echo "PostgreSQL namespace exists but no PostgreSQL pods found. Will install PostgreSQL."
  fi
else
  echo "PostgreSQL namespace does not exist. Will install PostgreSQL."
fi

# Install Helm if not already installed
if ! command -v helm &> /dev/null; then
  echo "Installing Helm..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Add Bitnami repository if not already added
if ! helm repo list | grep -q "bitnami"; then
  echo "Adding Bitnami Helm repository..."
  helm repo add bitnami https://charts.bitnami.com/bitnami
fi

# Update repositories
echo "Updating Helm repositories..."
helm repo update

# Create a Kubernetes namespace for PostgreSQL if it doesn't exist
if ! kubectl get namespace postgres &> /dev/null; then
  echo "Creating 'postgres' namespace..."
  kubectl create namespace postgres
fi

# Create a secret for PostgreSQL passwords
echo "Creating PostgreSQL secrets..."
kubectl create secret generic postgres-secrets \
  --namespace postgres \
  --from-literal=postgres-password="$POSTGRES_PASSWORD" \
  --from-literal=postgres-user="$POSTGRES_USER" \
  --from-literal=postgres-database="$POSTGRES_DATABASE" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify values file exists
if [ ! -f /tmp/postgres-values.yaml ]; then
  echo "Error: PostgreSQL values file not found at /tmp/postgres-values.yaml"
  exit 1
fi

# Check if PostgreSQL is already installed via Helm
if helm list -n postgres | grep -q "postgresql"; then
  echo "PostgreSQL is already installed via Helm. Upgrading with new configuration..."
  helm upgrade postgresql bitnami/postgresql \
    --namespace postgres \
    --values /tmp/postgres-values.yaml \
    --set auth.username="$POSTGRES_USER" \
    --set auth.password="$POSTGRES_PASSWORD" \
    --set auth.database="$POSTGRES_DATABASE"
else
  echo "Installing PostgreSQL using Helm..."
  helm install postgresql bitnami/postgresql \
    --namespace postgres \
    --values /tmp/postgres-values.yaml \
    --set auth.username="$POSTGRES_USER" \
    --set auth.password="$POSTGRES_PASSWORD" \
    --set auth.database="$POSTGRES_DATABASE"
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql --timeout=300s --namespace postgres || true

# Store checksum of values file in marker file
md5sum /tmp/postgres-values.yaml | awk '{print $1}' > "$MARKER_FILE"

echo "PostgreSQL installation completed at $(date)!"
echo "Database name: $POSTGRES_DATABASE"
echo "Username: $POSTGRES_USER"
echo ""
echo "To connect to PostgreSQL from inside the cluster:"
echo "postgresql.postgres.svc.cluster.local"
echo ""
echo "To get the PostgreSQL password:"
echo "kubectl get secret --namespace postgres postgres-secrets -o jsonpath=\"{.data.postgres-password}\" | base64 --decode"
echo ""
echo "To port-forward PostgreSQL to your local machine (for external access):"
echo "kubectl port-forward --namespace postgres svc/postgresql 5432:5432"
echo "Then connect to: localhost:5432"
echo ""
echo "To get connection details:"
kubectl get svc -n postgres