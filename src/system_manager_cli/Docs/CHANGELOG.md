# Changelog

All notable changes to this project should be documented here.

## 0.1.0 - Unreleased

### Added

- SQLite-backed authentication and session storage.
- Package entry point for `system-manager`.
- Production guide, privacy draft, refund draft, security policy, and release checklist.
- `.env.example` for safe configuration.
- CI workflow for compile, unit tests, linting, and package build checks.

### Changed

- Normalized imports to `system_manager_cli`.
- Verification code disclosure is development-only.
- Scheduled privileged tasks require real session authentication.

### Removed

- Hardcoded scheduled-task auth bypass token.
