#!/usr/bin/env python3
"""Simple test runner for OpenCV modules (no pytest required)."""
import sys
import traceback

# Add backend to path
sys.path.insert(0, '/app')

from tests.test_opencv_modules import TestBokehBlur, TestVintageFilm


def run_tests():
    """Run all tests and report results."""
    test_classes = [TestBokehBlur, TestVintageFilm]
    total = 0
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in methods:
            total += 1
            method = getattr(instance, method_name)
            
            try:
                method()
                print(f"✅ {method_name}")
                passed += 1
            except AssertionError as e:
                print(f"❌ {method_name}: {e}")
                failed += 1
            except Exception as e:
                print(f"💥 {method_name}: {type(e).__name__}: {e}")
                traceback.print_exc()
                failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    print('='*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_tests())
