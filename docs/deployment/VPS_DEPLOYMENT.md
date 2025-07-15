# VPS Deployment Configuration

This document explains how to configure VPS deployment for the LeadFactory application.

## Current Status

The VPS deployment step is currently **optional** and will be skipped if the required secrets are not configured. This prevents CI/CD pipeline failures when deployment infrastructure is not set up.

## Required GitHub Secrets

To enable VPS deployment, configure the following secrets in your GitHub repository:

1. **VPS_HOST**: The hostname or IP address of your VPS server
2. **VPS_USERNAME**: The SSH username for connecting to the VPS
3. **VPS_SSH_KEY**: The private SSH key for authentication (ensure proper formatting with newlines)

### Setting up GitHub Secrets

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each required secret with the appropriate value

## VPS Prerequisites

Before enabling deployment, ensure your VPS has:

1. Docker and Docker Compose installed
2. A directory at `/opt/leadfactory` with appropriate permissions
3. A `docker-compose.yml` file in `/opt/leadfactory` for production deployment
4. The SSH user has permissions to run Docker commands

## Deployment Process

When properly configured, the deployment will:

1. SSH into the VPS using the provided credentials
2. Navigate to `/opt/leadfactory`
3. Pull the latest Docker images
4. Deploy services using `docker-compose up -d`
5. Verify services are running
6. Clean up old Docker images

## Troubleshooting

If deployment fails after configuring secrets:

1. Verify SSH connection: `ssh -i <key_file> <username>@<host>`
2. Check Docker installation: `docker --version`
3. Verify docker-compose.yml exists: `ls -la /opt/leadfactory/`
4. Check user permissions: `docker ps` should work without sudo

## Disabling Deployment

The deployment step is already optional and won't block CI if it fails. To completely disable it:

1. Remove the `deploy` job from `.github/workflows/main.yml`
2. Or keep secrets empty (deployment will be skipped automatically)