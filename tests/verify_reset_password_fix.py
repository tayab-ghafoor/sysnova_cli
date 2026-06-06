#!/usr/bin/env python3
"""Verify the reset_password method signatures are correct."""

import inspect
from src.system_manager_cli.app import SystemManagerApp
from src.system_manager_cli.core.backend_client import BackendClient
from src.system_manager_cli.core.Auth_manager import AuthManager

print("[VERIFICATION] Reset Password Method Signatures")
print("=" * 70)

# Check BackendClient.reset_password
bc_method = BackendClient.reset_password
bc_sig = inspect.signature(bc_method)
print("\nBackendClient.reset_password")
print(f"  Signature: {bc_sig}")
bc_params = list(bc_sig.parameters.keys())[1:]  # Skip 'self'
print(f"  Parameters: {bc_params}")

# Check AuthManager.reset_password
am_method = AuthManager.reset_password
am_sig = inspect.signature(am_method)
print("\nAuthManager.reset_password")
print(f"  Signature: {am_sig}")
am_params = list(am_sig.parameters.keys())[1:]  # Skip 'self'
print(f"  Parameters: {am_params}")

# Check SystemManagerApp.execute_reset_password
app_method = SystemManagerApp.execute_reset_password
app_sig = inspect.signature(app_method)
print("\nSystemManagerApp.execute_reset_password")
print(f"  Signature: {app_sig}")
app_params = list(app_sig.parameters.keys())[1:]  # Skip 'self'
print(f"  Parameters: {app_params}")

print("\n" + "=" * 70)
print("[CALL FLOW ANALYSIS]")
print("=" * 70)

expected_calls = [
    ("main.py → app.execute_reset_password()", ['email', 'code', 'new_password', 'confirm']),
    ("app.py → backend.reset_password()", ['email', 'code', 'new_password']),
    ("app.py → auth_manager.reset_password()", ['email', 'code', 'new_password', 'confirm']),
]

print("\n✓ Expected Call Flow:")
for call, params in expected_calls:
    print(f"  {call}")
    print(f"    Parameters: {params}")

print("\n✓ Actual Signatures:")
print(f"  BackendClient.reset_password: {bc_params}")
print(f"  AuthManager.reset_password: {am_params}")

# Verify
print("\n" + "=" * 70)
print("[VERIFICATION RESULTS]")
print("=" * 70)

checks = [
    ("BackendClient takes 3 params", len(bc_params) == 3 and bc_params == ['email', 'code', 'new_password']),
    ("AuthManager takes 4 params", len(am_params) == 4 and am_params == ['email', 'code', 'new_password', 'confirm']),
    ("execute_reset_password takes 4 params", len(app_params) == 4 and app_params == ['email', 'code', 'new_password', 'confirm']),
]

all_pass = True
for check, result in checks:
    status = "✓" if result else "✗"
    print(f"{status} {check}")
    if not result:
        all_pass = False

print("\n" + "=" * 70)
if all_pass:
    print("[OK] All signatures correct! Fix is applied properly.")
    exit(0)
else:
    print("[ERROR] Signature mismatch detected!")
    exit(1)
