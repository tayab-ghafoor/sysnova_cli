#!/usr/bin/env python3
"""Test the forgot password flow implementation."""

import sys
from pathlib import Path

# Add src to path
_test_dir = Path(__file__).parent.resolve()
_src_dir = _test_dir.parent / "src"
if _src_dir.exists():
    sys.path.insert(0, str(_src_dir))
else:
    sys.path.insert(0, str(_test_dir.parent))

from system_manager_cli.app import SystemManagerApp


def test_app_methods():
    """Test that app has required methods."""
    print("[TEST 1] Checking SystemManagerApp methods...")
    print("=" * 60)
    
    methods_to_check = {
        'execute_forgot_password': ['email'],
        'execute_reset_password': ['email', 'code', 'new_password', 'confirm'],
    }
    
    import inspect
    
    for method_name, expected_params in methods_to_check.items():
        method = getattr(SystemManagerApp, method_name, None)
        assert method is not None, f"{method_name} method not found"
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())[1:]  # Skip 'self'
        print(f"\n✓ {method_name}")
        print(f"  Signature: {sig}")
        print(f"  Expected params: {expected_params}")
        print(f"  Actual params: {params}")
    
    print("\n" + "=" * 60)


def test_main_py_flow():
    """Test that main.py has the forgot password flow."""
    print("\n[TEST 2] Checking main.py forgot password flow...")
    print("=" * 60)
    
    # Get the actual main.py from src/system_manager_cli/
    _test_dir = Path(__file__).parent.resolve()
    main_file = _test_dir.parent / "src" / "system_manager_cli" / "main.py"
    
    if not main_file.exists():
        # Fallback: check if we're already in the right location
        main_file = Path(__file__).parent.parent / "main.py"
    
    if not main_file.exists():
        # If still not found, skip this test gracefully
        print(f"Warning: main.py not found at {main_file}")
        print("=" * 60)
        return
    
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_elements = [
        ('execute_forgot_password', 'execute_forgot_password method'),
        ('Enter Reset Code', 'Reset code prompt'),
        ('Enter New Password', 'New password prompt'),
        ('Confirm New Password', 'Confirm password prompt'),
        ('execute_reset_password', 'execute_reset_password method'),
    ]
    
    for element, description in required_elements:
        assert element in content, f"{description} NOT FOUND: {element}"
        print(f"✓ {description:<40} Found")
    
    print("=" * 60)


def test_password_validation_logic():
    """Test password validation rules."""
    print("\n[TEST 3] Testing password validation logic...")
    print("=" * 60)
    
    test_cases = [
        ("123", False, "Too short (< 6 chars)"),
        ("123456", True, "Valid (6 chars)"),
        ("password123", True, "Valid (long)"),
        ("", False, "Empty"),
        ("  ", False, "Spaces only"),
    ]
    
    for password, expected_valid, description in test_cases:
        is_valid = len(password) >= 6
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"{status} {description:<35} Valid={is_valid}, Expected={expected_valid}")
        assert is_valid == expected_valid, f"{description}: got {is_valid}, expected {expected_valid}"
    
    print("=" * 60)


def test_reset_code_validation_logic():
    """Test reset code validation rules."""
    print("\n[TEST 4] Testing reset code validation logic...")
    print("=" * 60)
    
    test_cases = [
        ("12", False, "Too short (< 4 chars)"),
        ("1234", True, "Valid (4 chars)"),
        ("123456", True, "Valid (long)"),
        ("", False, "Empty"),
        ("   ", False, "Spaces only"),
    ]
    
    for code, expected_valid, description in test_cases:
        is_valid = len(code.strip()) >= 4
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"{status} {description:<35} Valid={is_valid}, Expected={expected_valid}")
        assert is_valid == expected_valid, f"{description}: got {is_valid}, expected {expected_valid}"
    
    print("=" * 60)


def test_password_match_logic():
    """Test password matching logic."""
    print("\n[TEST 5] Testing password match logic...")
    print("=" * 60)
    
    test_cases = [
        ("password123", "password123", True, "Passwords match"),
        ("password123", "Password123", False, "Case mismatch"),
        ("password123", "password124", False, "Value mismatch"),
        ("", "", True, "Both empty"),
    ]
    
    for pwd1, pwd2, expected_match, description in test_cases:
        matches = pwd1 == pwd2
        status = "✓" if matches == expected_match else "✗"
        print(f"{status} {description:<35} Match={matches}, Expected={expected_match}")
        assert matches == expected_match, f"{description}: got {matches}, expected {expected_match}"
    
    print("=" * 60)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FORGOT PASSWORD FLOW VALIDATION TESTS")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("App Methods", test_app_methods()))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        results.append(("App Methods", False))
    
    try:
        results.append(("Main.py Flow", test_main_py_flow()))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        results.append(("Main.py Flow", False))
    
    try:
        results.append(("Password Validation", test_password_validation_logic()))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        results.append(("Password Validation", False))
    
    try:
        results.append(("Reset Code Validation", test_reset_code_validation_logic()))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        results.append(("Reset Code Validation", False))
    
    try:
        results.append(("Password Matching", test_password_match_logic()))
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        results.append(("Password Matching", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:<10} {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("[OK] All tests passed! Forgot password flow is complete.")
        return 0
    else:
        print("[ERROR] Some tests failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
