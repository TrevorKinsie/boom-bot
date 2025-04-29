# PowerShell script to build and deploy the boom-bot to local Kubernetes (Docker Desktop)
# Assumes this script is located in a 'deploy-scripts' subdirectory of the project root.

# --- Configuration ---
$ErrorActionPreference = 'Stop' # Exit script on any error

# Determine project root directory based on script location
$scriptDir = $PSScriptRoot
$projectRoot = (Get-Item $scriptDir).Parent.FullName
Write-Host "Project Root detected as: $projectRoot"

$imageName = "local-test/boom-bot:latest"
$deploymentName = "boom-bot-deployment"
# Use paths relative to the project root
$secretFile = Join-Path -Path $projectRoot -ChildPath "secrets\secret.yaml"
$secretExampleFile = Join-Path -Path $projectRoot -ChildPath "secrets\secret.ex.yaml"
$deploymentFile = Join-Path -Path $projectRoot -ChildPath "deployment.yaml"

# --- Prerequisites Check ---

Write-Host "Checking prerequisites..."

# Check if Docker is running (using docker info)
try {
    docker info | Out-Null
    Write-Host "Docker is running."
} catch {
    Write-Error "Error: Docker does not seem to be running. Please start Docker Desktop."
    exit 1
}

# Check if kubectl is installed
$kubectlPath = Get-Command kubectl -ErrorAction SilentlyContinue
if (-not $kubectlPath) {
    Write-Error "Error: kubectl command could not be found. Please install kubectl and ensure it's in your PATH."
    exit 1
} else {
     Write-Host "kubectl found at: $($kubectlPath.Source)"
}

# Check kubectl context
try {
    $currentContext = kubectl config current-context
    if ($currentContext -ne "docker-desktop") {
        Write-Warning "kubectl context is not set to 'docker-desktop'. Attempting to switch..."
        kubectl config use-context docker-desktop
        $currentContext = kubectl config current-context
        if ($currentContext -ne "docker-desktop") {
             Write-Error "Error: Could not switch kubectl context to 'docker-desktop'. Please ensure Kubernetes is enabled in Docker Desktop and the context exists."
             exit 1
        }
        Write-Host "Successfully switched kubectl context to 'docker-desktop'."
    } else {
        Write-Host "kubectl context is correctly set to 'docker-desktop'."
    }
} catch {
    Write-Error "Error checking or setting kubectl context: $($_.Exception.Message)"
    exit 1
}

# Check Kubernetes node status (basic check)
try {
    kubectl get nodes | Out-Null
    Write-Host "Kubernetes cluster is reachable."
} catch {
    Write-Error "Error: Cannot connect to Kubernetes cluster via kubectl. Ensure Kubernetes is enabled and running in Docker Desktop."
    exit 1
}

Write-Host "Prerequisites met."

# --- Secret Handling ---

if (-not (Test-Path $secretFile)) {
    Write-Host "Secret file ($secretFile) not found."
    if (Test-Path $secretExampleFile) {
        Write-Host "Please copy '$secretExampleFile' to '$secretFile' and replace '<base64-encoded-dev-token>' with your actual BASE64 ENCODED Telegram Bot token."
        Write-Host "You can encode your token in PowerShell using: [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes('YOUR_ACTUAL_TOKEN'))"
    } else {
        Write-Error "Example secret file ($secretExampleFile) also not found. Cannot proceed without secrets."
    }
    exit 1
}

# Basic check if placeholder is still present
$secretContent = Get-Content $secretFile -Raw
if ($secretContent -match "<base64-encoded-dev-token>") {
    Write-Error "Error: Placeholder '<base64-encoded-dev-token>' found in $secretFile. Please replace it with your actual Base64 encoded token."
    exit 1
}

# --- Build Stage ---

Write-Host "Building Docker image: $imageName from context: $projectRoot ..."
try {
    # Use the determined project root as the build context
    docker build -t $imageName $projectRoot
    Write-Host "Docker image built successfully."
} catch {
    Write-Error "Error building Docker image: $($_.Exception.Message)"
    exit 1
}


# --- Deploy Stage ---

Write-Host "Applying Kubernetes secret ($secretFile)..."
try {
    # Use the full path to the secret file
    kubectl apply -f $secretFile
} catch {
    Write-Error "Error applying secret: $($_.Exception.Message)"
    # Consider if you want to exit here or try applying deployment anyway
    exit 1
}

Write-Host "Applying Kubernetes deployment ($deploymentFile)..."
try {
    # Use the full path to the deployment file
    kubectl apply -f $deploymentFile
} catch {
    Write-Error "Error applying deployment: $($_.Exception.Message)"
    exit 1
}

# --- Rollout ---

Write-Host "Checking if deployment exists before rollout..."
$deploymentExists = $false
try {
    kubectl get deployment $deploymentName -o name | Out-Null
    $deploymentExists = $true
} catch {
    # Deployment likely doesn't exist, which is fine for the first run
    Write-Host "Deployment '$deploymentName' not found, likely first run."
}

if ($deploymentExists) {
    Write-Host "Triggering deployment rollout restart to ensure the latest image is used..."
    try {
        kubectl rollout restart deployment $deploymentName
    } catch {
        Write-Error "Error restarting deployment: $($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Host "Deployment is new, rollout restart not needed yet."
}

# --- Post-Deployment Info ---

Write-Host "`nDeployment process initiated." -ForegroundColor Green
Write-Host "You can check the status with:"
Write-Host "  kubectl get pods -l app=boom-bot"
Write-Host "Once a pod is 'Running', check logs with:"
Write-Host "  kubectl logs <pod-name>"
