variable "server_ip" {
  description = "IP address of the existing Kamatera server"
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

# PostgreSQL configuration variables
variable "postgres_password" {
  description = "Password for PostgreSQL admin user"
  type        = string
  default     = "postgres"  # You should override this with a secure password
  sensitive   = true
}

variable "postgres_user" {
  description = "Username for PostgreSQL admin user"
  type        = string
  default     = "postgres"
}

variable "postgres_database" {
  description = "Name of the default PostgreSQL database"
  type        = string
  default     = "postgres"
}


# Bot configuration variables
variable "bot_image" {
  description = "The Docker image for the bot (e.g., ghcr.io/owner/repo)."
  type        = string
}
variable "bot_image_tag" {
  description = "The specific tag for the bot image (e.g., the Git SHA)."
  type        = string
  default     = "latest" # Default, but should be overridden by the action
}

# GitHub Container Registry authentication
variable "github_username" {
  description = "GitHub username for Container Registry authentication"
  type        = string
}

variable "github_token" {
  description = "GitHub Personal Access Token with read:packages scope"
  type        = string
  sensitive   = true
}