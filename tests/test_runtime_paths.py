import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from system_manager_cli.config.config import Config
from system_manager_cli.core import config_manager
from system_manager_cli.core.rclone_runtime import find_rclone
from system_manager_cli.models.config_model import BackupConfig


class RuntimePathTests(unittest.TestCase):
    def test_backup_config_is_saved_under_writable_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            package_dir = Path(temp_dir) / "package"
            package_dir.mkdir()

            with (
                patch.object(Config, "DATA_DIR", data_dir),
                patch.object(Config, "LOGS_DIR", Path(temp_dir) / "logs"),
                patch.object(Config, "REPORTS_DIR", Path(temp_dir) / "reports"),
                patch.object(Config, "BACKUPS_DIR", Path(temp_dir) / "backups"),
                patch.object(Config, "UPDATER_DIR", Path(temp_dir) / "updater"),
                patch.object(Config, "PACKAGE_DIR", package_dir),
            ):
                cfg = BackupConfig(last_destination_path=str(data_dir / "backup-target"))
                self.assertTrue(config_manager.save_config(cfg))

                saved_path = data_dir / "backup_config.json"
                self.assertTrue(saved_path.exists())
                self.assertFalse((package_dir / "config" / "backup_config.json").exists())
                self.assertEqual(
                    str(data_dir / "backup-target"),
                    config_manager.load_config().last_destination_path,
                )

    def test_find_rclone_honors_explicit_binary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            binary = Path(temp_dir) / ("rclone.exe" if os.name == "nt" else "rclone")
            binary.write_text("", encoding="utf-8")
            with patch.dict(os.environ, {"RCLONE_BINARY": str(binary)}):
                self.assertEqual(str(binary), find_rclone())


if __name__ == "__main__":
    unittest.main()
