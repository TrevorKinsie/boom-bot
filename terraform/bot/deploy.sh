#!/bin/bash

# Terraform deployment script for bot that automatically uses variables from the secrets folder
# This script makes it easy to deploy the bot with secrets properly configured

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
SECRETS_DIR="$SCRIPT_DIR/../secrets"
TFVARS_FILE="$SECRETS_DIR/terraform.tfvars"

# Check if terraform.tfvars exists in secrets directory
if [ ! -f "$TFVARS_FILE" ]; then
  echo "Error: terraform.tfvars not found in $SECRETS_DIR"
  echo "Please create this file based on terraform.ex.tfvars template"
  exit 1
fi

# CD to the directory containing this script
cd "$SCRIPT_DIR"

# Run terraform with the secrets file
echo "Running terraform with variables from $TFVARS_FILE"
terraform "$@" -var-file="$TFVARS_FILE"