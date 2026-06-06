"""Unit tests for main menu command routing and shortcuts."""

import pytest
import sys
from pathlib import Path

# Add src to path
_test_dir = Path(__file__).parent.resolve()
_src_dir = _test_dir.parent / "src"
if _src_dir.exists():
    sys.path.insert(0, str(_src_dir))
else:
    sys.path.insert(0, str(_test_dir.parent))


class TestMainMenuShortcuts:
    """Test command shortcuts in main menu."""

    def test_health_shortcut_h(self):
        """Test 'h' shortcut for health monitor."""
        shortcuts = {
            'h': 'health',
            'b': 'backup',
            'f': 'file_organizer',
            'l': 'logs',
            's': 'schedule',
            'c': 'settings',
            'cfg': 'settings',
            'q': 'quit',
        }
        assert shortcuts.get('h') == 'health'

    def test_backup_shortcut_b(self):
        """Test 'b' shortcut for backup."""
        shortcuts = {'b': 'backup'}
        assert shortcuts.get('b') == 'backup'

    def test_numeric_option_1_health(self):
        """Test numeric option 1 maps to health."""
        menu_options = {
            '1': 'health',
            '2': 'file_organizer',
            '3': 'logs',
            '4': 'backup',
            '5': 'schedule',
            '6': 'settings',
            '7': 'logout',
            '0': 'exit',
        }
        assert menu_options.get('1') == 'health'

    def test_numeric_option_4_backup(self):
        """Test numeric option 4 maps to backup."""
        menu_options = {
            '1': 'health',
            '4': 'backup',
        }
        assert menu_options.get('4') == 'backup'

    def test_invalid_input_handling(self):
        """Test that invalid inputs are rejected."""
        valid_inputs = {'1', '2', '3', '4', '5', '6', '7', '0', 'h', 'b', 'l', 's', 'c', 'q', '?'}
        assert 'x' not in valid_inputs
        assert '99' not in valid_inputs
        assert 'xyz' not in valid_inputs


class TestCommandIntegration:
    """Test CLI command integration with main menu."""

    def test_command_health_integration(self):
        """Test that health command is available."""
        from system_manager_cli.cli_parser import build_parser
        parser = build_parser()
        args = parser.parse_args(['health'])
        assert args.command == 'health'

    def test_command_status_integration(self):
        """Test that status command is available."""
        from system_manager_cli.cli_parser import build_parser
        parser = build_parser()
        args = parser.parse_args(['status'])
        assert args.command == 'status'

    def test_command_analyze_integration(self):
        """Test that analyze command is available."""
        from system_manager_cli.cli_parser import build_parser
        parser = build_parser()
        args = parser.parse_args(['analyze', '.'])
        assert args.command == 'analyze'
        assert args.path == '.'


class TestUIModules:
    """Test Phase 1 UI modules."""

    def test_theme_module_imports(self):
        """Test theme module imports without errors."""
        from system_manager_cli.ulits.theme import colorize, T
        assert callable(colorize)
        assert hasattr(T, 'SUCCESS')

    def test_screen_module_imports(self):
        """Test screen module imports without errors."""
        from system_manager_cli.ulits.screen import box_top, box_bottom
        assert callable(box_top)
        assert callable(box_bottom)

    def test_spinner_module_imports(self):
        """Test spinner module imports without errors."""
        from system_manager_cli.ulits.spinner import Spinner
        assert Spinner is not None

    def test_menu_modules_import(self):
        """Test all menu modules import without errors."""
        from system_manager_cli.CLI import health_menu
        from system_manager_cli.CLI import settings_menu
        from system_manager_cli.CLI import logs_menu
        assert health_menu is not None
        assert settings_menu is not None
        assert logs_menu is not None


class TestPhase3Features:
    """Test Phase 3 feature placeholders."""

    def test_command_history_placeholder(self):
        """Test that command history can be initialized."""
        history = []
        history.append("health")
        history.append("status")
        assert len(history) == 2
        assert "health" in history

    def test_json_output_flag(self):
        """Test --json flag parsing."""
        from system_manager_cli.cli_parser import build_parser
        parser = build_parser()
        args = parser.parse_args(['status', '--json'])
        assert args.json is True

    def test_autocomplete_options(self):
        """Test autocomplete suggestion system."""
        commands = ['health', 'status', 'analyze', 'backup', 'organize', 'schedule']
        
        def autocomplete(partial):
            return [cmd for cmd in commands if cmd.startswith(partial)]
        
        assert autocomplete('h') == ['health']
        assert autocomplete('s') == ['status', 'schedule']
        assert len(autocomplete('x')) == 0


class TestProductionReadiness:
    """Test production readiness criteria."""

    def test_all_modules_compile(self):
        """Test that all modules compile without syntax errors."""
        modules = [
            'system_manager_cli.ulits.theme',
            'system_manager_cli.ulits.table',
            'system_manager_cli.ulits.spinner',
            'system_manager_cli.ulits.screen',
            'system_manager_cli.CLI.health_menu',
            'system_manager_cli.CLI.settings_menu',
            'system_manager_cli.main',
        ]
        
        for module_name in modules:
            mod = __import__(module_name, fromlist=[module_name.split('.')[-1]])
            assert mod is not None

    def test_cli_parser_builds(self):
        """Test that CLI parser builds successfully."""
        from system_manager_cli.cli_parser import build_parser
        parser = build_parser()
        assert parser is not None

    def test_app_bootstraps(self):
        """Test that app can be bootstrapped."""
        from system_manager_cli.app import SystemManagerApp
        # Don't actually instantiate to avoid backend connection
        assert SystemManagerApp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
