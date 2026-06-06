import uuid
from system_manager_cli.app import SystemManagerApp
from system_manager_cli.core.backend_client import _clear_token, _load_token
app = SystemManagerApp()
app._backend_online = False
email = f'test-{uuid.uuid4().hex[:8]}@example.com'
password = 'TestPass123!'
try:
    app.auth_manager.register_user(email, password, full_name='Test User')
except Exception:
    pass
_clear_token()
result = app.execute_login_user(email, password)
print('login_status=', result.get('status'))
print('token_present=', bool(result.get('data', {}).get('token')))
print('loaded_token=', _load_token())
logout_result = app.execute_logout_user(email)
print('logout_status=', logout_result.get('status'))
print('token_after_logout=', _load_token())
