#!/usr/bin/env python3
"""
Minimal test to verify basic LeadFactory functionality
"""
import sys
import time
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all core modules can be imported"""
    print("Testing module imports...")
    
    modules = [
        ("Core Config", "core.config"),
        ("Core Logging", "core.logging"),
        ("Gateway Factory", "d0_gateway.factory"),
        ("Gateway Facade", "d0_gateway.facade"),
        ("Database Models", "database.models"),
        ("Database Session", "database.session"),
    ]
    
    passed = 0
    failed = 0
    
    for name, module_path in modules:
        try:
            __import__(module_path)
            print(f"✅ {name}: OK")
            passed += 1
        except Exception as e:
            print(f"❌ {name}: FAILED - {str(e)}")
            failed += 1
    
    print(f"\nImport tests: {passed} passed, {failed} failed")
    return failed == 0


def test_config():
    """Test configuration loading"""
    print("\nTesting configuration...")
    
    try:
        from core.config import settings
        
        # Check essential settings
        checks = [
            ("App Name", settings.app_name == "LeadFactory"),
            ("Environment", settings.environment in ["development", "test"]),
            ("Database URL", bool(settings.database_url)),
            ("Use Stubs", isinstance(settings.use_stubs, bool)),
            ("Cost Budget", settings.cost_budget_usd > 0),
        ]
        
        passed = 0
        for check_name, result in checks:
            if result:
                print(f"✅ {check_name}: OK")
                passed += 1
            else:
                print(f"❌ {check_name}: FAILED")
        
        print(f"\nConfig tests: {passed}/{len(checks)} passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Config loading failed: {str(e)}")
        return False


def test_database():
    """Test database connection"""
    print("\nTesting database connection...")
    
    try:
        from database.session import engine
        from sqlalchemy import text
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            value = result.scalar()
            
        if value == 1:
            print("✅ Database connection: OK")
            return True
        else:
            print("❌ Database connection: FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False


def test_gateway():
    """Test gateway facade initialization"""
    print("\nTesting gateway initialization...")
    
    try:
        from d0_gateway.facade import get_gateway_facade
        
        facade = get_gateway_facade()
        
        # Check facade has required attributes
        checks = [
            ("Factory", hasattr(facade, 'factory')),
            ("Logger", hasattr(facade, 'logger')),
            ("Metrics", hasattr(facade, 'metrics')),
            ("Search method", hasattr(facade, 'search_businesses')),
        ]
        
        passed = 0
        for check_name, result in checks:
            if result:
                print(f"✅ {check_name}: OK")
                passed += 1
            else:
                print(f"❌ {check_name}: FAILED")
        
        print(f"\nGateway tests: {passed}/{len(checks)} passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Gateway initialization failed: {str(e)}")
        return False


def main():
    """Run all minimal tests"""
    print("="*60)
    print("LEADFACTORY MINIMAL TEST SUITE")
    print("="*60)
    
    start_time = time.time()
    
    # Run tests
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Gateway", test_gateway),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Running: {test_name}")
        print('='*40)
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    duration = time.time() - start_time
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed in {duration:.2f}s")
    
    if passed == total:
        print("\n🎉 All minimal tests PASSED!")
        print("Core functionality is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} tests FAILED.")
        print("Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())