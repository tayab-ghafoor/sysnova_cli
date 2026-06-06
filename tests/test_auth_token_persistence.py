import uuid

from system_manager_cli.app import SystemManagerApp
from system_manager_cli.core.backend_client import _clear_token, _load_token


def test_local_login_persists_token_and_logout_clears_it():
    app = SystemManagerApp()
    app._backend_online = False

    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    # Create a local verified user directly in the local auth store.
    try:
        app.auth_manager.register_user(email, password, full_name="Test User")
    except Exception:
        pass

    _clear_token()

    result = app.execute_login_user(email, password)
    assert result.get("status") == "success"
    token = result.get("data", {}).get("token")
    assert token
    assert _load_token() == token

    logout_result = app.execute_logout_user(email)
    assert logout_result.get("status") == "success"
    assert _load_token() is None
