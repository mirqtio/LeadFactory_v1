#!/usr/bin/env python3
"""Debug environment variables"""
import os
import sys

# Add project root to path
sys.path.insert(0, '/app')

print("=== Environment Variables ===")
for key in sorted(os.environ.keys()):
    if any(x in key.upper() for x in ['API', 'KEY', 'GOOGLE', 'STUB', 'PAGESPEED']):
        value = os.environ[key]
        if 'KEY' in key.upper() and len(value) > 10:
            value = value[:10] + '...'
        print(f"{key}: {value}")

print("\n=== Config Settings ===")
try:
    from core.config import settings
    print(f"use_stubs: {settings.use_stubs}")
    print(f"environment: {settings.environment}")
    print(f"google_api_key exists: {bool(settings.google_api_key)}")
    print(f"google_api_key: {settings.google_api_key[:10] if settings.google_api_key else 'None'}...")
    
    print("\n=== get_api_key test ===")
    try:
        key = settings.get_api_key('pagespeed')
        print(f"pagespeed key: {key[:10] if key else 'None'}...")
    except Exception as e:
        print(f"Error getting pagespeed key: {e}")
        
except Exception as e:
    print(f"Error loading config: {e}")
    import traceback
    traceback.print_exc()