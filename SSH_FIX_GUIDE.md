# SSH Deployment Fix Guide

Since you can SSH manually but GitHub Actions is failing, the issue is likely with how the SSH_PRIVATE_KEY is stored in GitHub secrets.

## Steps to Fix:

### 1. Export your working SSH private key:
```bash
cat ~/.ssh/your_deploy_key
```

### 2. Copy the ENTIRE output including:
- The `-----BEGIN OPENSSH PRIVATE KEY-----` line (or `-----BEGIN RSA PRIVATE KEY-----`)
- All the key content
- The `-----END OPENSSH PRIVATE KEY-----` line (or `-----END RSA PRIVATE KEY-----`)
- Make sure there are NO extra spaces or newlines before/after

### 3. Update the GitHub secret:
1. Go to: https://github.com/mirqtio/LeadFactory_v1/settings/secrets/actions
2. Edit `SSH_PRIVATE_KEY`
3. Paste the entire key content exactly as copied
4. Save

### 4. Verify other secrets are correct:
- `SSH_HOST`: Your VPS IP or hostname (no protocol, just the IP/hostname)
- `SSH_PORT`: Your SSH port (usually 22)
- `SSH_USER`: The username you SSH with

### 5. Test the connection:
Run the test workflow: https://github.com/mirqtio/LeadFactory_v1/actions/workflows/test-ssh.yml

## Common Issues:

1. **Extra newlines**: GitHub sometimes adds extra newlines when pasting. Make sure the key is exactly as in your file.

2. **Wrong key type**: If using RSA, headers should be `-----BEGIN RSA PRIVATE KEY-----`. If using Ed25519, headers should be `-----BEGIN OPENSSH PRIVATE KEY-----`.

3. **Key permissions**: The workflow sets chmod 600, but ensure your VPS has the corresponding public key in `~/.ssh/authorized_keys`

4. **User mismatch**: Ensure SSH_USER matches exactly the username you use when SSHing manually.