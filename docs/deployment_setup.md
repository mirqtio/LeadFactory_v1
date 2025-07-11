# Deployment Setup Guide

## GitHub Secrets Required

To enable automated deployment to VPS, configure the following secrets in your GitHub repository:

### 1. SSH_HOST
- **Description**: The IP address or hostname of your VPS
- **Example**: `123.45.67.89` or `vps.example.com`

### 2. SSH_USER
- **Description**: The SSH username for VPS access
- **Example**: `ubuntu` or `deploy`
- **Note**: This user must have Docker permissions and sudo access

### 3. SSH_PORT
- **Description**: SSH port for VPS access
- **Example**: `22` (default) or custom port like `2222`

### 4. SSH_PRIVATE_KEY
- **Description**: Private SSH key for authentication
- **How to generate**:
  ```bash
  # On your local machine
  ssh-keygen -t ed25519 -C "github-deploy" -f deploy_key
  
  # Copy the public key to VPS
  ssh-copy-id -i deploy_key.pub -p PORT user@vps-host
  
  # Add the private key content to GitHub secrets
  cat deploy_key
  ```
- **Important**: The VPS must have GitHub SSH key configured for repository access

## VPS Prerequisites

Before running the deployment, ensure your VPS has:

1. **Docker and Docker Compose installed**:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   ```

2. **GitHub SSH access configured**:
   ```bash
   # Generate SSH key on VPS (if not already done)
   ssh-keygen -t ed25519 -C "vps-deploy"
   
   # Add the public key to your GitHub repository deploy keys
   cat ~/.ssh/id_ed25519.pub
   # Go to GitHub repo Settings > Deploy keys > Add deploy key
   ```

3. **Required directories**:
   ```bash
   # The deployment script will create /srv/leadfactory automatically
   # Ensure your user has sudo access
   ```

4. **Production configuration**:
   ```bash
   # Create docker-compose.prod.yml in your repository with:
   # - Service definitions
   # - Environment variables
   # - Volume mounts
   # - Network configuration
   ```

5. **Nginx (optional but recommended)**:
   ```bash
   sudo apt install nginx
   sudo nano /etc/nginx/sites-available/leadfactory
   ```
   
   Example Nginx config:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
       
       location /health {
           proxy_pass http://localhost:8000/health;
           access_log off;
       }
   }
   ```

## Deployment Process

1. **Update repository URL**:
   ```bash
   # Edit .github/workflows/deploy.yml
   # Replace YOURORG/LEADFACTORY with your actual GitHub repository
   git clone --depth=1 git@github.com:YOURORG/LEADFACTORY.git .
   ```

2. **Automatic deployment**: 
   - Triggered on every push to `main` branch
   - Uses SSH to connect to VPS
   - Pulls latest code and runs docker-compose

3. **Manual deployment**:
   ```bash
   # Push to main branch
   git push origin main
   
   # Or manually trigger workflow
   gh workflow run deploy.yml
   ```

4. **Monitoring deployment**:
   ```bash
   # View workflow runs
   gh run list --workflow=deploy.yml
   
   # Watch specific run
   gh run watch
   
   # Check deployment on VPS
   ssh user@vps "cd /srv/leadfactory && docker compose ps"
   ```

## Rollback Strategy

If deployment fails:

1. **Quick rollback** (on VPS):
   ```bash
   # List available images
   docker images | grep leadfactory
   
   # Rollback to previous image
   docker stop leadfactory
   docker rm leadfactory
   docker run -d \
     --name leadfactory \
     --restart always \
     -p 8000:8000 \
     --env-file /opt/leadfactory/.env.production \
     -v /opt/leadfactory/logs:/app/logs \
     ghcr.io/your-org/leadfactory:previous-tag
   ```

2. **Via GitHub**:
   - Revert the problematic commit
   - Push to main (triggers new deployment)

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs leadfactory

# Check environment
docker exec leadfactory env | grep -E "DATABASE_URL|REDIS_URL"
```

### Health check fails
```bash
# Test locally
curl http://localhost:8000/health

# Check container network
docker exec leadfactory curl http://localhost:8000/health
```

### Permission issues
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix directory permissions
sudo chown -R $(id -u):$(id -g) /opt/leadfactory
```