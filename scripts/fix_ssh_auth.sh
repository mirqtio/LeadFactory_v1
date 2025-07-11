#!/bin/bash
# Script to extract public key from private key and add to VPS

echo "SSH Key Setup for GitHub Actions Deployment"
echo "=========================================="
echo ""

# Extract public key from your private key
echo "1. First, extract the public key from your private key:"
echo ""
echo "On your local machine, save your SSH_PRIVATE_KEY secret to a file:"
echo "  echo 'YOUR_PRIVATE_KEY_CONTENT' > deploy_key"
echo "  chmod 600 deploy_key"
echo ""
echo "2. Extract the public key:"
echo "  ssh-keygen -y -f deploy_key > deploy_key.pub"
echo ""
echo "3. Copy the public key content:"
echo "  cat deploy_key.pub"
echo ""
echo "4. Add to VPS authorized_keys:"
echo "  ssh -p SSH_PORT USER@VPS_HOST"
echo "  mkdir -p ~/.ssh"
echo "  echo 'PASTE_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
echo "  chmod 600 ~/.ssh/authorized_keys"
echo ""
echo "5. Test the connection:"
echo "  ssh -i deploy_key -p SSH_PORT USER@VPS_HOST 'echo Success!'"
echo ""
echo "6. Clean up local files:"
echo "  rm deploy_key deploy_key.pub"

# Alternative: Generate the public key from the fingerprint we saw
echo ""
echo "Based on the GitHub Actions output, your key fingerprint is:"
echo "SHA256:x+9Qtasan/Tqn5U/dWHnBcMZjsdJkbRAc+qDLn51sxM"
echo ""
echo "The key is an ED25519 key with comment 'leadfactory-ci'"