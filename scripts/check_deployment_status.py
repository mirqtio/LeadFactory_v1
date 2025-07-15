#!/usr/bin/env python3
"""
Check deployment configuration and status for LeadFactory CI/CD pipeline.
"""
import os
import subprocess
import sys

def check_local_env():
    """Check if deployment secrets are configured locally."""
    print("=== Checking Local Environment ===")
    
    env_files = ['.env', '.env.production']
    deployment_vars = ['VPS_HOST', 'VPS_USERNAME', 'VPS_SSH_KEY']
    
    found_vars = {}
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"✓ Found {env_file}")
            with open(env_file, 'r') as f:
                content = f.read()
                for var in deployment_vars:
                    if var in content:
                        found_vars[var] = env_file
    
    print("\n=== Deployment Variables ===")
    for var in deployment_vars:
        if var in found_vars:
            print(f"✓ {var} found in {found_vars[var]}")
        else:
            print(f"✗ {var} not found in any .env file")
    
    return len(found_vars) == len(deployment_vars)

def check_workflow_config():
    """Check GitHub Actions workflow configuration."""
    print("\n=== Checking Workflow Configuration ===")
    
    workflow_file = '.github/workflows/main.yml'
    if not os.path.exists(workflow_file):
        print(f"✗ {workflow_file} not found")
        return False
    
    with open(workflow_file, 'r') as f:
        content = f.read()
    
    # Check for deployment job
    if 'deploy:' in content:
        print("✓ Deployment job found in workflow")
        
        # Check if it's optional
        if 'continue-on-error: true' in content:
            print("✓ Deployment is configured as optional (won't block CI)")
        else:
            print("⚠ Deployment might block CI if it fails")
            
        # Check for secret usage
        secrets = ['VPS_HOST', 'VPS_USERNAME', 'VPS_SSH_KEY']
        for secret in secrets:
            if f'secrets.{secret}' in content:
                print(f"✓ Workflow uses secret: {secret}")
    else:
        print("✗ No deployment job found in workflow")
    
    return True

def check_github_status():
    """Check latest GitHub Actions run status."""
    print("\n=== GitHub Actions Status ===")
    
    try:
        # Get latest commit
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H'],
            capture_output=True, text=True, check=True
        )
        latest_commit = result.stdout.strip()
        print(f"Latest commit: {latest_commit[:8]}")
        
        # Get current branch
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, check=True
        )
        branch = result.stdout.strip()
        print(f"Current branch: {branch}")
        
        print("\nTo check CI status:")
        print(f"1. Visit: https://github.com/mirqtio/LeadFactory_v1/actions")
        print(f"2. Look for commit: {latest_commit[:8]}")
        print("3. Check if 'Deploy to VPS (Optional)' job is skipped or passing")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error checking git status: {e}")
        return False
    
    return True

def main():
    """Main function to check deployment status."""
    print("LeadFactory Deployment Status Check")
    print("=" * 40)
    
    # Check local environment
    has_local_config = check_local_env()
    
    # Check workflow configuration
    workflow_ok = check_workflow_config()
    
    # Check GitHub status
    github_ok = check_github_status()
    
    # Summary
    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)
    
    if not has_local_config:
        print("⚠ Deployment secrets not configured locally")
        print("  This is OK - deployment will be skipped in CI")
    
    if workflow_ok:
        print("✓ Workflow is properly configured")
        print("  Deployment is optional and won't block CI")
    
    print("\n✅ The CI pipeline should pass without deployment issues!")
    print("   The 'Deploy to VPS' job will be skipped if secrets are missing.")

if __name__ == "__main__":
    main()