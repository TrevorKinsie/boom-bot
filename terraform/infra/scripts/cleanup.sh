#!/bin/bash
# Robust cleanup script to remove any Docker or Kubernetes repositories
# and prepare for a clean installation

# Don't exit on errors since we're fixing errors
set +e

echo "Starting system cleanup at $(date)"

# Check where Docker repositories might be referenced
echo "Checking for Docker repository references..."
grep -r "download.docker.com" /etc/apt/ || echo "No Docker references found in /etc/apt/"

# First, disable the problematic repos to prevent apt-get update errors
echo "Disabling problematic repositories..."
find /etc/apt/sources.list.d/ -name "*.list" -exec sed 's/^deb/#deb/g' {} \;

# Comment out any Docker/Kubernetes references in the main sources.list
if grep -q "docker\|kubernetes" /etc/apt/sources.list; then
  echo "Found Docker/Kubernetes references in main sources.list, commenting out..."
  cp /etc/apt/sources.list /etc/apt/sources.list.bak.$(date +%Y%m%d%H%M%S)
  sed 's/^deb.*docker/#deb docker/g' /etc/apt/sources.list
  sed 's/^deb.*kubernetes/#deb kubernetes/g' /etc/apt/sources.list
fi

# Now remove the repository files completely
echo "Removing Docker and Kubernetes repository files..."
rm -f /etc/apt/sources.list.d/docker*.list
rm -f /etc/apt/sources.list.d/kubernetes*.list

# Remove repository keys
echo "Removing repository keys..."
rm -f /etc/apt/keyrings/docker*.gpg
rm -f /etc/apt/keyrings/kubernetes*.gpg
rm -f /etc/apt/trusted.gpg.d/*docker*.gpg
rm -f /etc/apt/trusted.gpg.d/*kubernetes*.gpg

# Clean the trusted.gpg file if it exists
if [ -f /etc/apt/trusted.gpg ]; then
  echo "Removing Docker and Kubernetes keys from trusted.gpg if they exist..."
  # We can't selectively remove keys from the binary file, so we'll leave it alone
  # But we can create a new trusted.gpg.d directory if it doesn't exist
  mkdir -p /etc/apt/trusted.gpg.d/
fi

# Clean up apt sources cache
echo "Cleaning APT lists cache..."
rm -rf /var/lib/lists/*
apt-get clean

# Try to update package lists, ignoring errors
echo "Updating package lists (ignoring errors)..."
apt-get update -o Acquire::AllowInsecureRepositories=true -o Acquire::AllowDowngradeToInsecureRepositories=true || true

# Remove Docker packages if they exist, ignoring errors
echo "Removing any existing Docker packages..."
apt-get remove -y docker docker-engine docker.io containerd runc docker-ce docker-ce-cli containerd.io || true
apt-get autoremove -y || true

echo "Creating new clean sources.list.d directory..."
mkdir -p /etc/apt/sources.list.d.clean
mv /etc/apt/sources.list.d /etc/apt/sources.list.d.old || true
mv /etc/apt/sources.list.d.clean /etc/apt/sources.list.d
mkdir -p /etc/apt/keyrings

echo "Setting up clean Debian repositories..."
cat > /etc/apt/sources.list <<EOF
deb http://deb.debian.org/debian bookworm main contrib non-free-firmware
deb http://deb.debian.org/debian-security bookworm-security main contrib non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free-firmware
EOF

# Final update attempt
echo "Final update attempt..."
apt-get update || true

echo "Cleanup completed at $(date)"
echo "The system should now be ready for a clean Docker and Kubernetes installation."
exit 0