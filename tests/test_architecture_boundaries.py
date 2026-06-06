import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if not SRC_DIR.exists():
    SRC_DIR = PROJECT_ROOT  # Fallback for packaged environment
CLI_FILE = SRC_DIR / 'system_manager_cli' / 'CLI' / 'CLI.py'
APP_FILE = SRC_DIR / 'system_manager_cli' / 'app.py'


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_cli_does_not_import_domain_layers_directly(self) -> None:
        source = CLI_FILE.read_text(encoding='utf-8')

        self.assertNotIn('system_manager_cli.core.', source)
        self.assertNotIn('system_manager_cli.logs_analysis.Analysis.', source)
        self.assertNotIn('system_manager_cli.Reporting.', source)
        self.assertNotIn('system_manager_cli.Notifications.', source)

    def test_app_does_not_import_cli(self) -> None:
        source = APP_FILE.read_text(encoding='utf-8')

        self.assertNotIn('system_manager_cli.CLI', source)


if __name__ == '__main__':
    unittest.main()
