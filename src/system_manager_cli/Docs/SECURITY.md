# Security Policy

## Supported Versions

Security fixes are applied to the latest released version only until a formal support matrix is published.

## Reporting Vulnerabilities

Do not publish security issues publicly before maintainers have reviewed them. Send reports to the project owner or the published support email.

Include:

- A clear description of the issue
- Steps to reproduce
- Impact
- Affected version or commit

## Secret Handling

- Never commit `.env`, credentials, database files, tokens, or generated backups.
- Use `.env.example` as the template for required variables.
- Use app passwords or service credentials for SMTP/cloud providers.
- Keep `SYSTEM_MANAGER_DEV_MODE=false` in production.

## Authentication

User accounts and sessions are stored in local SQLite. Sessions must be real, unexpired tokens. The app does not accept hardcoded bypass tokens.

## Verification Codes

Verification codes are stored with expiry and are not returned to users in production. Development-only code display requires `SYSTEM_MANAGER_DEV_MODE=true` or `APP_ENV=development`.
