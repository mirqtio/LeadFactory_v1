# SSH Deployment Troubleshooting Guide

## Common SSH Issues and Solutions

### 1. Verify GitHub Secrets

Go to your repository settings:
https://github.com/mirqtio/LeadFactory_v1/settings/secrets/actions

Ensure you have these secrets set:
- `SSH_HOST` - Your VPS IP or hostname
- `SSH_PORT` - SSH port (usually 22)
- `SSH_USER` - Username on VPS
- `SSH_PRIVATE_KEY` - Private SSH key content

### 2. SSH Key Format

The SSH_PRIVATE_KEY must include the full key with headers:

```
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
...rest of key...
-----END RSA PRIVATE KEY-----
```

Or for Ed25519:
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
...rest of key...
-----END OPENSSH PRIVATE KEY-----
```

### 3. Test SSH Manually

Run the test workflow:
1. Go to https://github.com/mirqtio/LeadFactory_v1/actions/workflows/test-ssh.yml
2. Click "Run workflow"
3. Check the output for specific error messages

### 4. Common Error Messages and Fixes

**"Permission denied (publickey)"**
- The SSH key is not added to the VPS's authorized_keys
- Fix: Add your public key to `~/.ssh/authorized_keys` on the VPS

**"Connection refused"**
- SSH service not running or wrong port
- Fix: Check SSH is running: `sudo systemctl status ssh`
- Fix: Verify correct port in `/etc/ssh/sshd_config`

**"Host key verification failed"**
- First time connecting to host
- Already fixed with StrictHostKeyChecking=accept-new

**"sudo: no tty present"**
- User needs passwordless sudo
- Fix on VPS: `echo "$SSH_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/$SSH_USER`

### 5. Manual Deployment Test

Test the deployment manually from your local machine:

```bash
# Set environment variables
export SSH_HOST=your-vps-ip
export SSH_PORT=22
export SSH_USER=your-username

# Test connection
ssh -p $SSH_PORT $SSH_USER@$SSH_HOST "echo 'Connection successful'"

# Test sudo access
ssh -p $SSH_PORT $SSH_USER@$SSH_HOST "sudo echo 'Sudo works'"

# Test Docker
ssh -p $SSH_PORT $SSH_USER@$SSH_HOST "docker --version"

# Test Git access
ssh -p $SSH_PORT $SSH_USER@$SSH_HOST "ssh -T git@github.com"
```

### 6. VPS Prerequisites Script

Run this on your VPS to ensure all prerequisites are met:

```bash
#!/bin/bash
# Run as your deployment user

# Install Docker
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    newgrp docker
fi

# Install Docker Compose
if ! docker compose version &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# Setup GitHub SSH access
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -C "vps-deploy" -f ~/.ssh/id_ed25519 -N ""
    echo "Add this key to your GitHub deploy keys:"
    cat ~/.ssh/id_ed25519.pub
fi

# Create deployment directory
sudo mkdir -p /srv/leadfactory
sudo chown $USER:$USER /srv/leadfactory

# Test everything
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"
echo "GitHub SSH test:"
ssh -T git@github.com
```

### 7. Check Latest Deployment Logs

View the verbose logs from the latest deployment:
https://github.com/mirqtio/LeadFactory_v1/actions

The `-v` flag we added will show detailed SSH connection information.