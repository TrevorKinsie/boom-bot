terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20" # Use an appropriate version
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2.0"
    }
  }
  
  # Add this backend configuration to reference the variables file
  backend "local" {}
}

# Load external variables from shared location
# These are still passed via TF_VAR_ or -var in the GitHub Actions workflow
# Variables are used in different places, so we simply declare them
# matching the names in the referenced file
variable "postgres_user" {
  description = "Username for PostgreSQL admin user"
  type        = string
}

variable "postgres_password" {
  description = "Password for PostgreSQL admin user"
  type        = string
  sensitive   = true
}

variable "postgres_database" {
  description = "Name of the default PostgreSQL database"
  type        = string
}

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

# Additional bot-specific variables
variable "bot_image" {
  description = "The Docker image for the bot (e.g., ghcr.io/owner/repo)."
  type        = string
}

variable "bot_image_tag" {
  description = "The specific tag for the bot image (e.g., the Git SHA)."
  type        = string
  default     = "latest" # Default, but should be overridden by the action
}

variable "bot_replicas" {
  description = "Number of bot instances to run."
  type        = number
  default     = 1
}

variable "bot_container_port" {
  description = "The port the bot container listens on."
  type        = number
  default     = 8080 # Assuming default, adjust if needed
}

variable "db_secret_name" {
  description = "Name of the Kubernetes secret storing DB credentials."
  type        = string
  default     = "postgres-credentials"
}

# Variables sourced from the main variables.tf (or passed via secrets/env vars)
# These are needed to create the K8s secret if it doesn't exist
variable "postgres_host" {
  description = "Hostname or service name for the PostgreSQL database within Kubernetes."
  type        = string
  # Assuming Helm chart installed postgres in default namespace with a standard service name
  # Adjust if your install-postgres.sh creates a different service name/namespace
  default = "postgresql.default.svc.cluster.local"
}

# GitHub Container Registry credentials
variable "github_username" {
  description = "GitHub username for Container Registry authentication"
  type        = string
}

variable "github_token" {
  description = "GitHub Personal Access Token with read:packages scope"
  type        = string
  sensitive   = true
}

# Configure the Kubernetes provider
provider "kubernetes" {
  config_path = "~/.kube/config"
}

# Setup connection to the remote Kubernetes cluster and import existing resources
resource "null_resource" "setup_kube_connection" {
  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ~/.kube
      sshpass -p "${var.ssh_password}" ssh -o StrictHostKeyChecking=no ${var.ssh_username}@${var.server_ip} 'cat /etc/kubernetes/admin.conf' > ~/.kube/config
      chmod 600 ~/.kube/config
      sed -i 's/kubernetes-admin@kubernetes/kubernetes-admin@${var.server_ip}/g' ~/.kube/config
      sed -i 's/kubernetes/kubernetes-${var.server_ip}/g' ~/.kube/config
      sed -i 's/server: https:\/\/[^:]*:/server: https:\/\/${var.server_ip}:/g' ~/.kube/config
      
      # Check if the deployment exists and handle existing resources
      if kubectl get deployment boom-bot-deployment &>/dev/null; then
        echo "Deployment already exists, removing it to allow Terraform to manage it"
        kubectl delete deployment boom-bot-deployment
        # Give Kubernetes a moment to remove the deployment
        sleep 5
      fi
      
      # Check if the service exists and handle it
      if kubectl get service boom-bot-service &>/dev/null; then
        echo "Service already exists, removing it to allow Terraform to manage it"
        kubectl delete service boom-bot-service
        sleep 2
      fi
      
      # Check if the secrets exist and handle them
      if kubectl get secret github-registry-credentials &>/dev/null; then
        echo "GitHub registry credentials secret already exists, removing it"
        kubectl delete secret github-registry-credentials
      fi
      
      if kubectl get secret ${var.db_secret_name} &>/dev/null; then
        echo "Database credentials secret already exists, removing it"
        kubectl delete secret ${var.db_secret_name}
      fi
    EOT
  }
}

# --- Kubernetes Resources ---

# Create a Secret for GitHub Container Registry authentication
resource "kubernetes_secret" "github_registry_credentials" {
  depends_on = [null_resource.setup_kube_connection]
  
  metadata {
    name = "github-registry-credentials"
  }

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        "ghcr.io" = {
          auth = base64encode("${var.github_username}:${var.github_token}")
        }
      }
    })
  }

  type = "kubernetes.io/dockerconfigjson"
}

# 1. Secret for Database Credentials
resource "kubernetes_secret" "db_creds" {
  depends_on = [null_resource.setup_kube_connection]
  
  metadata {
    name = var.db_secret_name
    # Consider adding a namespace if not deploying to 'default'
    # namespace = "your-namespace"
  }

  data = {
    POSTGRES_HOST     = var.postgres_host # Store host in secret too
    POSTGRES_USER     = var.postgres_user
    POSTGRES_PASSWORD = var.postgres_password
    POSTGRES_DB       = var.postgres_database
    # Add other necessary connection details if required by the bot
  }

  type = "Opaque" # Standard secret type
}

# 2. Bot Deployment
resource "kubernetes_deployment" "bot_deployment" {
  metadata {
    name = "boom-bot-deployment"
    labels = {
      app = "boom-bot"
    }
    # Consider adding a namespace if not deploying to 'default'
    # namespace = "your-namespace"
  }

  spec {
    replicas = var.bot_replicas

    selector {
      match_labels = {
        app = "boom-bot"
      }
    }

    template {
      metadata {
        labels = {
          app = "boom-bot"
        }
      }

      spec {
        # Add the image pull secrets reference
        image_pull_secrets {
          name = kubernetes_secret.github_registry_credentials.metadata[0].name
        }
        
        container {
          name  = "boom-bot-container"
          image = "${var.bot_image}:${var.bot_image_tag}"
          
          port {
            container_port = var.bot_container_port
            name = "http"
            protocol = "TCP"
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.db_creds.metadata[0].name
            }
          }
          
          # Set container environment variables
          env {
            name  = "APPLICATION_ENV"
            value = "production"
          }
          
          # Resource limits and requests
          resources {
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
            requests = {
              cpu    = "200m"
              memory = "256Mi"
            }
          }
          
          # Liveness probe to check if the bot is running
          liveness_probe {
            exec {
              command = ["pgrep", "-f", "python"]
            }
            initial_delay_seconds = 30
            period_seconds        = 20
            timeout_seconds       = 5
            failure_threshold     = 3
          }
          
          # Security context for the container
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = false
          }
        }
      }
    }
  }
}

# 3. Service to expose the Bot Deployment (Optional, depending on needs)
# This creates an internal ClusterIP service. Use NodePort or LoadBalancer for external access.
resource "kubernetes_service" "bot_service" {
  metadata {
    name = "boom-bot-service"
    # Consider adding a namespace if not deploying to 'default'
    # namespace = "your-namespace"
  }
  spec {
    selector = {
      app = kubernetes_deployment.bot_deployment.spec[0].template[0].metadata[0].labels.app
    }
    port {
      port        = 80 # Port the service listens on
      target_port = var.bot_container_port # Port on the container
    }

    type = "ClusterIP" # Change to NodePort or LoadBalancer if external access needed
  }
}
