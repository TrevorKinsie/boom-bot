#!/bin/bash
# Script to check for existing Docker and Kubernetes installations

set +e  # Don't exit on error

echo "Checking for existing installations at $(date)"
LOGFILE="/var/log/k8s-check.log"
exec > >(tee -a ${LOGFILE}) 2>&1

# Check Docker
echo "Checking for Docker..."
if command -v docker &> /dev/null && systemctl is-active --quiet docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    echo "Docker is installed and running. Version: $DOCKER_VERSION"
    DOCKER_INSTALLED=true
else
    echo "Docker is not installed or not running."
    DOCKER_INSTALLED=false
fi

# Check containerd
echo "Checking for containerd..."
if command -v containerd &> /dev/null && systemctl is-active --quiet containerd; then
    CONTAINERD_VERSION=$(containerd --version | awk '{print $3}')
    echo "containerd is installed and running. Version: $CONTAINERD_VERSION"
    CONTAINERD_INSTALLED=true
else
    echo "containerd is not installed or not running."
    CONTAINERD_INSTALLED=false
fi

# Check Kubernetes components
echo "Checking for Kubernetes components..."
if command -v kubectl &> /dev/null && command -v kubelet &> /dev/null && command -v kubeadm &> /dev/null; then
    KUBECTL_VERSION=$(kubectl version --client -o yaml 2>/dev/null | grep gitVersion | head -1 | awk '{print $2}')
    echo "Kubernetes components are installed. kubectl version: $KUBECTL_VERSION"
    K8S_COMPONENTS_INSTALLED=true
else
    echo "Kubernetes components are not installed."
    K8S_COMPONENTS_INSTALLED=false
fi

# Check if Kubernetes cluster is running
echo "Checking if Kubernetes cluster is running..."
if kubectl get nodes &> /dev/null; then
    echo "Kubernetes cluster is running."
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    echo "Number of nodes: $NODE_COUNT"
    POD_COUNT=$(kubectl get pods --all-namespaces --no-headers | wc -l)
    echo "Number of pods: $POD_COUNT"
    CLUSTER_RUNNING=true
else
    echo "Kubernetes cluster is not running or kubectl is not configured."
    CLUSTER_RUNNING=false
fi

# Check if PostgreSQL is running in the cluster
echo "Checking for PostgreSQL in the cluster..."
if kubectl get namespace postgres &> /dev/null && kubectl get pods -n postgres &> /dev/null; then
    echo "PostgreSQL namespace and pods exist."
    PG_PODS=$(kubectl get pods -n postgres --no-headers | wc -l)
    echo "Number of PostgreSQL pods: $PG_PODS"
    POSTGRES_INSTALLED=true
else
    echo "PostgreSQL is not installed in the cluster."
    POSTGRES_INSTALLED=false
fi

# Create a summary file with the results
cat > /tmp/installation-status.txt << EOF
DOCKER_INSTALLED=$DOCKER_INSTALLED
CONTAINERD_INSTALLED=$CONTAINERD_INSTALLED
K8S_COMPONENTS_INSTALLED=$K8S_COMPONENTS_INSTALLED
CLUSTER_RUNNING=$CLUSTER_RUNNING
POSTGRES_INSTALLED=$POSTGRES_INSTALLED
EOF

echo "Installation check completed at $(date)"
echo "Check /tmp/installation-status.txt for a summary of the results."

# Return success
exit 0