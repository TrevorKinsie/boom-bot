terraform {
  required_providers {
    null = {
      source = "hashicorp/null"
      version = "~> 3.2.0"
    }
  }
}

# Load variable definitions from the secrets directory
variable "server_ip" {
  description = "IP address of the existing server"
  type        = string
}

variable "ssh_username" {
  description = "SSH username for the existing server"
  type        = string
}

variable "ssh_password" {
  description = "SSH password for the existing server"
  type        = string
  default     = ""
  sensitive   = true
}

variable "postgres_password" {
  description = "Password for PostgreSQL admin user"
  type        = string
  sensitive   = true
}

variable "postgres_user" {
  description = "Username for PostgreSQL admin user"
  type        = string
}

variable "postgres_database" {
  description = "Name of the default PostgreSQL database"
  type        = string
}

# Handle existing or new Kubernetes cluster
resource "null_resource" "k8s_management" {
  # Use a checksum of the installation script to trigger updates when the script changes
  triggers = {
    installation_script_hash = md5(file("${path.module}/scripts/install-k8s.sh"))
  }

  # Copy the installation script to the remote server
  provisioner "file" {
    source      = "${path.module}/scripts/install-k8s.sh"
    destination = "/tmp/install-k8s.sh"
    
    connection {
      type        = "ssh"
      user        = var.ssh_username
      password    = var.ssh_password != "" ? var.ssh_password : null
      host        = var.server_ip
    }
  }

  # Execute the installation script
  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_username
      password    = var.ssh_password != "" ? var.ssh_password : null
      host        = var.server_ip
    }
    
    inline = [
      "chmod +x /tmp/install-k8s.sh",
      "sudo bash /tmp/install-k8s.sh || (echo 'Kubernetes management failed' && exit 1)"
    ]
  }
}

# Add PostgreSQL installation
resource "null_resource" "postgres_installation" {
  depends_on = [null_resource.k8s_management]
  
  # Use a checksum of the PostgreSQL installation script to trigger updates
  triggers = {
    postgres_script_hash = md5(file("${path.module}/scripts/install-postgres.sh"))
    postgres_values_hash = md5(file("${path.module}/scripts/postgres-values.yaml"))
  }
  
  # Copy the PostgreSQL installation script to the remote server
  provisioner "file" {
    source      = "${path.module}/scripts/install-postgres.sh"
    destination = "/tmp/install-postgres.sh"
    
    connection {
      type        = "ssh"
      user        = var.ssh_username
      password    = var.ssh_password != "" ? var.ssh_password : null
      host        = var.server_ip
    }
  }

  # Copy PostgreSQL values file to the remote server
  provisioner "file" {
    source      = "${path.module}/scripts/postgres-values.yaml"
    destination = "/tmp/postgres-values.yaml"
    
    connection {
      type        = "ssh"
      user        = var.ssh_username
      password    = var.ssh_password != "" ? var.ssh_password : null
      host        = var.server_ip
    }
  }
  
  # Execute the PostgreSQL installation script
  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_username
      password    = var.ssh_password != "" ? var.ssh_password : null
      host        = var.server_ip
    }
    
    inline = [
      "chmod +x /tmp/install-postgres.sh",
      "sudo bash /tmp/install-postgres.sh ${var.postgres_password} ${var.postgres_database} ${var.postgres_user} || (echo 'PostgreSQL installation failed' && exit 1)"
    ]
  }
}