#!/bin/bash
# Kubernetes Installation Script for Kamatera server (Debian-specific)
# This script handles both new installations and existing clusters

set -e

# Create installation log
LOGFILE="/var/log/k8s-install.log"
exec > >(tee -a ${LOGFILE}) 2>&1

echo "Starting Kubernetes installation check at $(date)"

# Check if kubeconfig exists and if cluster is accessible
if [ -f "/etc/kubernetes/admin.conf" ] && KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes &> /dev/null; then
  echo "Kubernetes cluster is already configured and accessible."
  echo "Cluster status:"
  KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes
  KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A
  
  # Ensure kubectl is properly configured for root
  echo "Ensuring kubectl is configured for root user..."
  mkdir -p /root/.kube
  cp /etc/kubernetes/admin.conf /root/.kube/config
  chmod 600 /root/.kube/config
  
  # For non-root user if specified
  DEFAULT_USER=$(logname 2>/dev/null || echo "${SUDO_USER:-${USER}}")
  if [ -n "$DEFAULT_USER" ] && [ "$DEFAULT_USER" != "root" ]; then
    USER_HOME=$(eval echo ~$DEFAULT_USER)
    echo "Configuring kubectl for user $DEFAULT_USER..."
    mkdir -p $USER_HOME/.kube
    cp /etc/kubernetes/admin.conf $USER_HOME/.kube/config
    chown -R $DEFAULT_USER:$(id -gn $DEFAULT_USER) $USER_HOME/.kube
  fi
  
  # Check for flannel networking
  if ! KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A | grep -q flannel; then
    echo "Flannel network not detected. Installing..."
    KUBECONFIG=/etc/kubernetes/admin.conf kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
  fi
  
  # Allow scheduling on control-plane if needed
  if KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe node $(hostname) | grep -q "NoSchedule"; then
    echo "Removing NoSchedule taint from control-plane node..."
    KUBECONFIG=/etc/kubernetes/admin.conf kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
    KUBECONFIG=/etc/kubernetes/admin.conf kubectl taint nodes --all node-role.kubernetes.io/master- || true
  fi
  
  echo "Kubernetes cluster is ready to use."
  exit 0
fi

# If we get here, either the cluster doesn't exist or can't be accessed
echo "No working Kubernetes cluster found. Checking for components..."

# Check for Docker
if command -v docker &> /dev/null && systemctl is-active --quiet docker; then
  echo "Docker is already installed and running."
  docker --version
  DOCKER_INSTALLED=true
else
  echo "Docker is not installed or not running. Will install."
  DOCKER_INSTALLED=false
fi

# Check for containerd
if command -v containerd &> /dev/null && systemctl is-active --quiet containerd; then
  echo "containerd is already installed and running."
  containerd --version
  CONTAINERD_INSTALLED=true
else
  echo "containerd is not installed or not running. Will install."
  CONTAINERD_INSTALLED=false
fi

# Fix hostname resolution if needed
echo "Ensuring hostname is in /etc/hosts..."
if ! grep -q "$(hostname)" /etc/hosts; then
  echo "127.0.0.1 $(hostname)" | tee -a /etc/hosts
fi

# Create a marker file to track installation status
MARKER_FILE="/etc/kubernetes/.installation-complete"
K8S_VERSION="1.29"  # Specify the Kubernetes version

# Update and upgrade non-interactively only if we need to install components
if [ "$DOCKER_INSTALLED" = "false" ] || [ "$CONTAINERD_INSTALLED" = "false" ]; then
  echo "Updating system packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get upgrade -y

  # Install dependencies
  echo "Installing dependencies..."
  apt-get install -y apt-transport-https ca-certificates curl software-properties-common gnupg2
fi

# Install Docker CE for Debian if not already installed
if [ "$DOCKER_INSTALLED" = "false" ]; then
  echo "Installing Docker..."
  
  # Detect Debian version
  OS_VERSION_CODENAME=$(grep -oP '(?<=^VERSION_CODENAME=).+' /etc/os-release | tr -d '"')
  echo "Detected Debian version: $OS_VERSION_CODENAME"

  # Create directory for Docker GPG key
  mkdir -p /etc/apt/keyrings

  # Download and save Docker's GPG key
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  # Add Docker repository
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $OS_VERSION_CODENAME stable" | tee /etc/apt/sources.list.d/docker.list

  # Update and install Docker
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable docker
  systemctl start docker
fi

# Configure containerd if Docker is installed but containerd needs configuration
if [ "$DOCKER_INSTALLED" = "true" ] && [ "$CONTAINERD_INSTALLED" = "false" ]; then
  echo "Configuring containerd..."
  mkdir -p /etc/containerd
  containerd config default | tee /etc/containerd/config.toml
  sed 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
  systemctl restart containerd
fi

# Disable swap
echo "Disabling swap..."
swapoff -a
sed '/swap/s/^/#/' /etc/fstab

# Load kernel modules
echo "Loading kernel modules..."
cat > /etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

# Setup required sysctl params
echo "Setting up sysctl parameters..."
cat > /etc/sysctl.d/k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sysctl --system

# Check if Kubernetes components are already installed
if command -v kubectl &> /dev/null && command -v kubelet &> /dev/null && command -v kubeadm &> /dev/null; then
  echo "Kubernetes components are already installed."
  kubectl version --client -o yaml 2>/dev/null || kubectl version --client
  K8S_COMPONENTS_INSTALLED=true
  exit 0
else
  echo "Installing Kubernetes components..."
  mkdir -p /etc/apt/keyrings

  # Download and save Kubernetes GPG key
  curl -fsSL https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
  chmod a+r /etc/apt/keyrings/kubernetes-apt-keyring.gpg

  # Add Kubernetes repository
  echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/ /" | tee /etc/apt/sources.list.d/kubernetes.list

  # Update and install Kubernetes
  apt-get update
  apt-get install -y kubelet kubeadm kubectl
  apt-mark hold kubelet kubeadm kubectl
  
  K8S_COMPONENTS_INSTALLED=true
fi

# Create kubeadm configuration
echo "Creating kubeadm configuration..."
cat > /tmp/kubeadm-config.yaml <<EOF
apiVersion: kubeadm.k8s.io/v1beta3
kind: InitConfiguration
nodeRegistration:
  criSocket: "unix:///var/run/containerd/containerd.sock"
---
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
networking:
  podSubnet: "10.244.0.0/16"
EOF

# Initialize Kubernetes
echo "Initializing Kubernetes cluster..."
kubeadm init --config=/tmp/kubeadm-config.yaml --ignore-preflight-errors=all

# Save join command for worker nodes
JOIN_COMMAND=$(kubeadm token create --print-join-command)
echo "Worker node join command:"
echo "$JOIN_COMMAND"
echo "$JOIN_COMMAND" > /etc/kubernetes/join-command.txt

# Setup kubectl for root
mkdir -p /root/.kube
cp /etc/kubernetes/admin.conf /root/.kube/config
chmod 600 /root/.kube/config

# For non-root user if specified
DEFAULT_USER=$(logname 2>/dev/null || echo "${SUDO_USER:-${USER}}")
if [ -n "$DEFAULT_USER" ] && [ "$DEFAULT_USER" != "root" ]; then
  USER_HOME=$(eval echo ~$DEFAULT_USER)
  mkdir -p $USER_HOME/.kube
  cp /etc/kubernetes/admin.conf $USER_HOME/.kube/config
  chown -R $DEFAULT_USER:$(id -gn $DEFAULT_USER) $USER_HOME/.kube
  echo "Configured kubectl for user $DEFAULT_USER"
fi

# Install CNI (Flannel)
echo "Installing Flannel network..."
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# Wait for network to be ready
echo "Waiting for network pods to be ready..."
sleep 30

# Allow scheduling on the control-plane node
echo "Allowing workloads on the control-plane node..."
kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
kubectl taint nodes --all node-role.kubernetes.io/master- || true  # For older K8s versions

# Create the marker file
touch $MARKER_FILE
echo "$(date)" > $MARKER_FILE

echo "Kubernetes installation completed at $(date)!"
kubectl get nodes