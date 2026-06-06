from __future__ import annotations

import logging
from typing import Optional


class CliException(Exception):
    """Base exception for application-facing errors."""


class ConfigurationError(CliException):
    """Raised when application configuration is invalid."""


class PathError(CliException):
    """Raised when a file system path is invalid or inaccessible."""


class PermissionError(CliException):
    """Raised when the application lacks required permissions."""


class BackupError(CliException):
    """Raised when a backup operation fails."""


class FileOrganizationError(CliException):
    """Raised when file organization fails."""


class DiskSpaceError(CliException):
    """Raised when insufficient free space is available."""


class LogAnalysisError(CliException):
    """Raised when log analysis cannot be completed."""


class HealthMonitorError(CliException):
    """Raised when system health checks fail."""


class AuthenticationError(CliException):
    """Raised when authentication fails."""



def handle_error(error: Exception, operation_name: str, context: Optional[str] = None) -> None:
    """Compatibility helper for logging uncaught errors in older modules."""
    logger = logging.getLogger(__name__)
    if context:
        logger.error('%s failed (%s): %s', operation_name, context, error, exc_info=True)
    else:
        logger.error('%s failed: %s', operation_name, error, exc_info=True)
