# Reference the variables from the secrets directory
# This file ensures Terraform loads variable values from the secrets directory

# Set the path to locate the terraform.tfvars file in the secrets directory
terraform {
  # The variables are loaded from the -var-file parameter during terraform apply
  # Usage: terraform apply -var-file=../secrets/terraform.tfvars
}

# Load common provider configurations
provider "null" {
  # No specific configuration needed for null provider
}