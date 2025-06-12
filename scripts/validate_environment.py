#!/usr/bin/env python3
"""
Validate LeadFactory Environment Configuration
Ensures all required environment variables are set
"""
import os
import sys
import re
from typing import Dict, List, Tuple

# Required environment variables by category
REQUIRED_VARS = {
    "Database": [
        ("DATABASE_URL", r"postgresql://.*", "PostgreSQL connection string"),
        ("POSTGRES_PASSWORD", r".{8,}", "PostgreSQL password (min 8 chars)"),
        ("REDIS_URL", r"redis://.*", "Redis connection string"),
    ],
    "External APIs": [
        ("YELP_API_KEY", r"[A-Za-z0-9_-]{20,}", "Yelp API key"),
        ("GOOGLE_PAGESPEED_API_KEY", r"[A-Za-z0-9_-]{20,}", "Google PageSpeed API key"),
        ("OPENAI_API_KEY", r"sk-[A-Za-z0-9]{40,}", "OpenAI API key"),
        ("SENDGRID_API_KEY", r"SG\.[A-Za-z0-9_-]{20,}", "SendGrid API key"),
        ("STRIPE_SECRET_KEY", r"(sk_test_|sk_live_)[A-Za-z0-9]{20,}", "Stripe secret key"),
    ],
    "Monitoring": [
        ("DATADOG_API_KEY", r"[a-f0-9]{32}", "Datadog API key"),
        ("DATADOG_APP_KEY", r"[a-f0-9]{40}", "Datadog application key"),
        ("SENTRY_DSN", r"https://[a-f0-9]+@.*sentry\.io/[0-9]+", "Sentry DSN"),
    ],
    "Application": [
        ("SECRET_KEY", r".{32,}", "Application secret key (min 32 chars)"),
        ("ENVIRONMENT", r"(development|staging|production)", "Environment name"),
    ]
}

# Optional but recommended
OPTIONAL_VARS = {
    "Features": [
        ("ENABLE_WEBHOOKS", r"(true|false|True|False)", "Enable webhook processing"),
        ("ENABLE_ANALYTICS", r"(true|false|True|False)", "Enable analytics"),
    ],
    "Limits": [
        ("RATE_LIMIT_PER_MINUTE", r"[0-9]+", "API rate limit per minute"),
        ("MAX_WORKERS", r"[0-9]+", "Maximum worker processes"),
    ]
}


def validate_env_var(name: str, pattern: str, value: str) -> Tuple[bool, str]:
    """Validate an environment variable against a pattern"""
    if not value:
        return False, "Not set"
    
    if pattern and not re.match(pattern, value):
        # Mask sensitive values in error messages
        if any(keyword in name for keyword in ["KEY", "SECRET", "PASSWORD", "DSN"]):
            masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            return False, f"Invalid format (got: {masked_value})"
        else:
            return False, f"Invalid format (got: {value})"
    
    return True, "Valid"


def check_env_vars(vars_dict: Dict[str, List[Tuple[str, str, str]]], required: bool = True) -> Dict[str, Dict[str, Tuple[bool, str]]]:
    """Check environment variables and return results"""
    results = {}
    
    for category, vars_list in vars_dict.items():
        results[category] = {}
        for var_name, pattern, description in vars_list:
            value = os.getenv(var_name, "")
            is_valid, message = validate_env_var(var_name, pattern, value)
            results[category][var_name] = (is_valid, message)
    
    return results


def print_results(results: Dict[str, Dict[str, Tuple[bool, str]]], required: bool = True):
    """Print validation results"""
    all_valid = True
    
    for category, vars_results in results.items():
        print(f"\n{category}:")
        print("-" * 50)
        
        for var_name, (is_valid, message) in vars_results.items():
            status = "✅" if is_valid else ("❌" if required else "⚠️")
            print(f"  {status} {var_name}: {message}")
            
            if not is_valid and required:
                all_valid = False
    
    return all_valid


def check_file_exists(filename: str) -> bool:
    """Check if a configuration file exists"""
    return os.path.isfile(filename)


def main():
    """Main validation function"""
    print("🔍 LeadFactory Environment Validation")
    print("=" * 60)
    
    # Check for .env file
    env_files = [".env", ".env.production"]
    env_file_found = False
    
    print("\nConfiguration Files:")
    print("-" * 50)
    for env_file in env_files:
        exists = check_file_exists(env_file)
        status = "✅" if exists else "❌"
        print(f"  {status} {env_file}")
        if exists:
            env_file_found = True
    
    if not env_file_found:
        print("\n❌ No .env file found! Create one from .env.example")
        sys.exit(1)
    
    # Load .env file
    if check_file_exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()
    
    # Check required variables
    print("\n🔒 Required Variables:")
    required_results = check_env_vars(REQUIRED_VARS, required=True)
    all_required_valid = print_results(required_results, required=True)
    
    # Check optional variables
    print("\n📋 Optional Variables:")
    optional_results = check_env_vars(OPTIONAL_VARS, required=False)
    print_results(optional_results, required=False)
    
    # Check for common issues
    print("\n🔧 Common Issues Check:")
    print("-" * 50)
    
    # Check DATABASE_URL format
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        if "@db:" in db_url or "@postgres:" in db_url:
            print("  ⚠️  DATABASE_URL uses container name - OK for Docker")
        elif "@localhost:" in db_url:
            print("  ⚠️  DATABASE_URL uses localhost - OK for local dev")
        elif "@leadfactory-postgres:" in db_url:
            print("  ✅ DATABASE_URL uses correct production container name")
    
    # Check API key types
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if stripe_key.startswith("sk_test_"):
        print("  ⚠️  STRIPE_SECRET_KEY is in test mode")
    elif stripe_key.startswith("sk_live_"):
        print("  ✅ STRIPE_SECRET_KEY is in live mode")
    
    # Summary
    print("\n" + "=" * 60)
    if all_required_valid:
        print("✅ All required environment variables are properly configured!")
        print("\nYou can now run:")
        print("  docker compose -f docker-compose.production.yml up -d")
        return 0
    else:
        print("❌ Some required environment variables are missing or invalid!")
        print("\nPlease fix the issues above and run this script again.")
        print("\nTip: Copy .env.example to .env and fill in the values")
        return 1


if __name__ == "__main__":
    sys.exit(main())