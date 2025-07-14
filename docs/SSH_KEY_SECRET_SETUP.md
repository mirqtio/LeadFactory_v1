# SSH Key Secret Setup Guide

## Verifying and Fixing the SSH_PRIVATE_KEY Secret

### Step 1: Export Your Working SSH Key

On your local machine where SSH works:

```bash
# Display the private key content
cat ~/.ssh/leadfactory_deploy
```

### Step 2: Copy the ENTIRE Key

Make sure to copy:
- The `-----BEGIN OPENSSH PRIVATE KEY-----` line
- All the key content (multiple lines)
- The `-----END OPENSSH PRIVATE KEY-----` line
- NO extra spaces or blank lines before/after

### Step 3: Update GitHub Secret

1. Go to: https://github.com/mirqtio/LeadFactory_v1/settings/secrets/actions
2. Click on `SSH_PRIVATE_KEY` to edit it (or create if missing)
3. Paste the entire key content EXACTLY as copied
4. Click "Update secret"

### Step 4: Verify Other Secrets

Ensure these are also set correctly:
- `SSH_HOST`: `96.30.197.121` (just the IP, no protocol)
- `SSH_PORT`: `22` (or your custom port)
- `SSH_USER`: `deploy` (or your deployment user)

### Common Issues and Fixes

#### Issue: Extra newlines or spaces
**Symptom**: "Permission denied (publickey,password)"
**Fix**: Re-copy the key without any modifications

#### Issue: Wrong key format
**Symptom**: "invalid format" or "not a valid private key"
**Fix**: Ensure you're copying the private key (not the .pub file)

#### Issue: Windows line endings
**Symptom**: Key appears correct but still fails
**Fix**: Use a text editor that preserves Unix line endings (LF not CRLF)

### Testing the Fix

After updating the secret:
1. Push any small change to main branch
2. Watch the Deploy workflow: https://github.com/mirqtio/LeadFactory_v1/actions
3. The "Set up SSH agent" step should show "Adding private key(s) to agent"
4. The "Remote deploy" step should connect without password prompts

### Alternative: Direct Key Test

If you want to verify the key format locally:

```bash
# Save the key to a temp file
echo "YOUR_KEY_CONTENT_HERE" > /tmp/test_key
chmod 600 /tmp/test_key

# Test it
ssh -i /tmp/test_key -o StrictHostKeyChecking=no deploy@96.30.197.121 "echo 'Success!'"

# Clean up
rm /tmp/test_key
```

### Notes

- The deploy workflow already has the SSH agent setup (webfactory/ssh-agent@v0.8.0)
- The agent automatically loads the key for all SSH commands in the job
- No need to specify `-i` flag when using the agent
- The key is only available during the workflow run (secure)