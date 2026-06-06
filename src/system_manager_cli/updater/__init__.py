"""
Updater Package

Provides automatic update functionality for SysNova.
"""

from .auto_updater import AutoUpdater
from .version_manager import VersionManager

__version__ = "1.0.0"
__all__ = ['AutoUpdater', 'VersionManager']
