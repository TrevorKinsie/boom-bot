# Kubernetes with PostgreSQL on Kamatera Server

This repository contains Terraform configurations and GitHub Actions workflows to automatically deploy and maintain a Kubernetes cluster with PostgreSQL on an existing Kamatera server.

## Features

- **Automated Deployment**: Deploy Kubernetes and PostgreSQL with a simple git push
- **Idempotent Installation**: Scripts check if components are already installed and update them if needed
- **GitHub Actions Integration**: CI/CD pipeline for infrastructure deployment
- **Server-Side State Management**: Terraform state stored on the same server for simplicity
- **PostgreSQL Database**: Fully configured PostgreSQL database running in Kubernetes

## Prerequisites

1. An existing Kamatera server with SSH access
2. GitHub repository to host this code
3. GitHub repository secrets for server credentials

## Repository Structure

```
kubernetes-kamatera-terraform/
├── .github/
│   └── workflows/
│       └── deploy.yml              # GitHub Actions workflow
├── terraform/
│   ├── main.tf                     # Main Terraform configuration
│   ├── variables.tf                # Variable definitions
│   ├── outputs.tf                  # Output definitions
│   └── scripts/
│       ├── install-k8s.sh          # Kubernetes installation script
│       ├── install-postgres.sh     # PostgreSQL installation script
│       └── postgres-values.yaml    # PostgreSQL Helm values
└── README.md                       # This documentation
```

## Setup Instructions

### 1. Fork/Clone this Repository

```bash
git clone https://github.com/yourusername/kubernetes-kamatera-terraform.git
cd kubernetes-kamatera-terraform
```

### 2. Configure GitHub Repository Secrets

Add the following secrets to your GitHub repository:

- `SERVER_IP`: Your Kamatera server IP address
- `SSH_USERNAME`: SSH username for your server
- `SSH_PASSWORD`: SSH password (if using password authentication)
- `SSH_PRIVATE_KEY`: Your private SSH key (if using key-based authentication)
- `POSTGRES_PASSWORD`: Password for PostgreSQL admin user
- `POSTGRES_USER`: Username for PostgreSQL (optional, defaults to 'postgres')
- `POSTGRES_DATABASE`: Default database name (optional, defaults to 'postgres')

### 3. Prepare Your Server for State Storage

SSH into your server and create a directory for storing Terraform state:

```bash
ssh your-username@your-server-ip
sudo mkdir -p /opt/terraform/state
sudo chown your-username /opt/terraform/state
sudo chmod 700 /opt/terraform/state
```

### 4. Deploy using GitHub Actions

Simply push to the main branch to trigger deployment:

```bash
git add .
git commit -m "Initial deployment"
git push
```

The GitHub Actions workflow will:
1. Set up Terraform
2. Download any existing state from your server
3. Deploy Kubernetes and PostgreSQL
4. Upload the updated state back to your server

## PostgreSQL Configuration

The PostgreSQL installation:

- Runs in its own `postgres` namespace
- Uses Bitnami's PostgreSQL Helm chart
- Has persistent storage (8GB by default)
- Creates a default database with the specified credentials

### Accessing PostgreSQL

#### From inside the Kubernetes cluster

Applications running in the cluster can connect to PostgreSQL using:

```
Host: postgresql.postgres.svc.cluster.local
Port: 5432
Username: [value of POSTGRES_USER]
Password: [value of POSTGRES_PASSWORD]
Database: [value of POSTGRES_DATABASE]
```

#### From outside the cluster

To access PostgreSQL from your local machine:

```bash
# Port-forward the PostgreSQL service
kubectl port-forward --namespace postgres svc/postgresql 5432:5432

# Then connect using:
# Host: localhost
# Port: 5432
# Username: [value of POSTGRES_USER]  
# Password: [value of POSTGRES_PASSWORD]
# Database: [value of POSTGRES_DATABASE]
```

#### Getting the PostgreSQL password

If you need to retrieve the PostgreSQL password:

```bash
kubectl get secret --namespace postgres postgres-secrets -o jsonpath="{.data.postgres-password}" | base64 --decode
```

## Customizing PostgreSQL

To customize the PostgreSQL configuration:

1. Edit `terraform/scripts/postgres-values.yaml`
2. Commit and push your changes
3. The GitHub Actions workflow will detect the changes and update the deployment

## Troubleshooting

### Common Issues

1. **SSH Connection Errors**:
   - Verify the SERVER_IP, SSH_USERNAME, and SSH_PASSWORD/SSH_PRIVATE_KEY secrets
   - Check if your server has proper firewall rules to allow SSH

2. **Kubernetes Installation Failures**:
   - Check the Kubernetes installation logs on the server: `/var/log/k8s-install.log`
   - Ensure your server meets the minimum requirements (2 CPU, 2GB RAM)

3. **PostgreSQL Installation Issues**:
   - Check PostgreSQL installation logs: `/var/log/postgres-install.log`
   - Verify Kubernetes is running properly: `kubectl get nodes`
   - Check Persistent Volume provisioning: `kubectl get pv,pvc -n postgres`

### Debugging Commands

```bash
# Check Kubernetes status
kubectl get nodes
kubectl get pods -A

# Check PostgreSQL status
kubectl get pods -n postgres
kubectl get svc -n postgres
kubectl logs -n postgres -l app.kubernetes.io/name=postgresql

# Check storage
kubectl get pv,pvc -n postgres
```

## Maintenance

### Updating Kubernetes

Edit the `terraform/scripts/install-k8s.sh` file to update Kubernetes version or configuration:

```bash
# Change this line in install-k8s.sh
K8S_VERSION="1.29"  # Change to desired version
```

### Updating PostgreSQL

Edit the `terraform/scripts/postgres-values.yaml` file to update PostgreSQL configuration, then push your changes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.