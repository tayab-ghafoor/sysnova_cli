"""Prompt helpers for the CLI layer."""

from __future__ import annotations

import getpass
from typing import Optional


class PromptCollector:
    """Collect user input with format-only validation."""

    @staticmethod
    def get_file_path() -> Optional[str]:
        while True:
            value = input('Enter a log file or directory (blank to cancel): ').strip()
            if not value:
                return None
            if value:
                return value

    @staticmethod
    def get_backup_target() -> Optional[str]:
        while True:
            value = input('Enter a file or directory to back up (blank to cancel): ').strip()
            if not value:
                return None
            if value:
                return value

    @staticmethod
    def get_backup_type() -> str:
        mapping = {'1': 'full', '2': 'incremental', '3': 'differential'}
        while True:
            print('1. Full')
            print('2. Incremental')
            print('3. Differential')
            choice = input('Select backup type: ').strip()
            if choice in mapping:
                return mapping[choice]
            print('Please enter 1, 2, or 3.')

    @staticmethod
    def get_username() -> Optional[str]:
        value = input('Username or email (blank to cancel): ').strip()
        return value or None

    @staticmethod
    def get_email() -> Optional[str]:
        while True:
            value = input('Email address (blank to cancel): ').strip()
            if not value:
                return None
            if '@' in value and '.' in value:
                return value
            print('Please enter a valid email address.')

    @staticmethod
    def get_password() -> Optional[str]:
        while True:
            show = input('Show password while typing? (y/n, blank to cancel): ').strip().lower()
            if not show:
                return None
            if show in ('y', 'yes'):
                value = input('Password (blank to cancel): ').strip()
                return value or None
            if show in ('n', 'no'):
                value = getpass.getpass('Password (blank to cancel): ')
                return value or None
            print('Please enter y or n.')

    @staticmethod
    def get_full_name() -> Optional[str]:
        value = input('Full name (blank to cancel): ').strip()
        return value or None

    @staticmethod
    def get_confirm_password() -> Optional[str]:
        value = getpass.getpass('Confirm password (blank to cancel): ')
        return value or None

    @staticmethod
    def get_verification_code() -> Optional[str]:
        value = input('Verification code (blank to cancel): ').strip()
        return value or None

    @staticmethod
    def get_source_directory() -> Optional[str]:
        value = input('Source directory path (blank to cancel): ').strip()
        return value or None

    @staticmethod
    def get_target_directory() -> Optional[str]:
        value = input('Target directory path (blank to cancel): ').strip()
        return value or None
