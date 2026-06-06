import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from system_manager_cli.app import SystemManagerApp
from system_manager_cli.config.config import Config


TEST_TMP_ROOT = Path(__file__).resolve().parent / '_tmp'
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)

APP_LOG = '''
[2026-04-22 10:00:00] INFO Service started
[2026-04-22 10:01:00] WARN Retry scheduled for worker 17 from 192.168.1.10
[2026-04-22 10:02:00] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:03:00] CRITICAL Payment processor unavailable
'''.strip()


class SystemManagerAppRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_TMP_ROOT / f"app_routes_{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self.data_dir = self.temp_dir / 'data'
        self.backup_dir = self.temp_dir / 'backups'
        self.report_dir = self.temp_dir / 'reports'
        self.log_dir = self.temp_dir / 'logs'

        self._patches = [
            patch.object(Config, 'APP_DATA_ROOT', self.temp_dir),
            patch.object(Config, 'DATA_DIR', self.data_dir),
            patch.object(Config, 'BACKUP_DRIVE', self.backup_dir),
            patch.object(Config, 'REPORTS_DIR', self.report_dir),
            patch.object(Config, 'LOGS_DIR', self.log_dir),
        ]
        for item in self._patches:
            item.start()
            self.addCleanup(item.stop)

        Config.ensure_directories()

        self.log_file = self.temp_dir / 'app.log'
        self.log_file.write_text(APP_LOG + '\n', encoding='utf-8')

        self.backup_source = self.temp_dir / 'to_backup.txt'
        self.backup_source.write_text('backup smoke content\n', encoding='utf-8')

        self.app = SystemManagerApp()
        self.app.emailer.send_health_alert = lambda *_args, **_kwargs: False
        self.app.emailer.send_log_analysis = lambda *_args, **_kwargs: False
        self.app.emailer.send_backup_complete = lambda *_args, **_kwargs: False

        self.app.auth_manager.register_user(
            'route-session@example.com',
            'Password1',
            'Route Session',
        )
        auth = self.app.execute_authentication('route-session@example.com', 'Password1')
        self.session_id = auth['data']['token']

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_log_analysis_returns_formatted_success(self) -> None:
        result = self.app.execute_log_analysis(str(self.log_file), self.session_id)

        self.assertEqual('success', result['status'])
        self.assertEqual('Log analysis', result['operation'])
        self.assertIn('Log analysis completed', result['display'])
        self.assertGreaterEqual(result['data']['summary']['records_processed'], 1)

    def test_execute_analysis_alias_matches_log_analysis_route(self) -> None:
        result = self.app.execute_log_analysis(str(self.log_file), self.session_id)

        self.assertEqual('success', result['status'])
        self.assertEqual('Log analysis', result['operation'])

    def test_execute_log_analysis_returns_structured_error_for_missing_path(self) -> None:
        missing_file = self.temp_dir / 'missing.log'
        result = self.app.execute_log_analysis(str(missing_file), self.session_id)

        self.assertEqual('error', result['status'])
        self.assertEqual('Log analysis failed', result['operation'])
        self.assertIn('Path does not exist', result['error'])

    def test_execute_backup_returns_formatted_success(self) -> None:
        result = self.app.execute_backup(str(self.backup_source), 'full', self.session_id)

        self.assertEqual('success', result['status'])
        self.assertEqual('Backup', result['operation'])
        self.assertIn('Backup completed', result['display'])
        self.assertTrue(Path(result['data']['backup_path']).exists())

    def test_execute_health_check_returns_formatted_success(self) -> None:
        result = self.app.execute_health_check()

        self.assertEqual('success', result['status'])
        self.assertEqual('Health check', result['operation'])
        self.assertIn('Health check completed', result['display'])

    def test_execute_authentication_returns_formatted_failure_for_unknown_user(self) -> None:
        result = self.app.execute_authentication('unknown@example.com', 'Password1')

        self.assertEqual('error', result['status'])
        self.assertEqual('Authentication', result['operation'])
        self.assertIn('Authentication failed', result['display'])

    def test_execute_authentication_returns_formatted_success_for_registered_user(self) -> None:
        self.app.auth_manager.register_user('route@example.com', 'Password1', 'Route User')
        result = self.app.execute_authentication('route@example.com', 'Password1')

        self.assertEqual('success', result['status'])
        self.assertEqual('Authentication', result['operation'])
        self.assertIn('Authentication successful', result['display'])
        self.assertEqual('route@example.com', result['data']['user']['email'])

    def test_execute_reset_password_syncs_backend_success_to_sqlite(self) -> None:
        self.app.auth_manager.register_user('reset@example.com', 'OldPass123', 'Reset User')
        self.app._backend_online = True
        self.app.backend.reset_password = MagicMock(
            return_value={'success': True, 'message': 'Password reset successfully.'}
        )

        result = self.app.execute_reset_password(
            'reset@example.com',
            '123456',
            'NewPass123',
            'NewPass123',
        )

        self.assertEqual('success', result['status'])
        self.assertFalse(self.app.auth_manager.authenticate('reset@example.com', 'OldPass123')['success'])
        self.assertTrue(self.app.auth_manager.authenticate('reset@example.com', 'NewPass123')['success'])

    def test_execute_reset_password_does_not_fallback_on_backend_validation_error(self) -> None:
        self.app.auth_manager.register_user('reset-error@example.com', 'OldPass123', 'Reset User')
        local_request = self.app.auth_manager.forgot_password('reset-error@example.com')
        self.assertTrue(local_request['success'])
        local_code = self.app.auth_manager._load_resets()['reset-error@example.com']['code']
        self.app._backend_online = True
        self.app.backend.reset_password = MagicMock(
            return_value={
                'success': False,
                'error': 'Invalid or expired reset code.',
                'status_code': 400,
            }
        )

        result = self.app.execute_reset_password(
            'reset-error@example.com',
            local_code,
            'NewPass123',
            'NewPass123',
        )

        self.assertEqual('error', result['status'])
        self.assertTrue(self.app.auth_manager.authenticate('reset-error@example.com', 'OldPass123')['success'])
        self.assertFalse(self.app.auth_manager.authenticate('reset-error@example.com', 'NewPass123')['success'])

    def test_validate_configuration_returns_true(self) -> None:
        self.assertTrue(self.app.validate_configuration())


if __name__ == '__main__':
    unittest.main()
