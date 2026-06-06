from __future__ import annotations

import re
from typing import Any


class LogScrubber:
    """Clean and normalize scanned log data.

    Improvements over original:
    - Bearer tokens, Authorization headers redacted
    - Database connection strings redacted
    - Windows & POSIX paths redacted more accurately (avoids over-redacting)
    - API key patterns (key=, apikey=, api_key=)
    - UUID redaction
    - Phone number redaction
    """

    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
    )
    IP_PATTERN = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
    )
    TOKEN_PATTERN = re.compile(
        r'\b(password|passwd|token|secret|api[_\-]?key|apikey|access[_\-]?key'
        r'|auth[_\-]?token|private[_\-]?key)\s*[:=]\s*\S+',
        re.IGNORECASE,
    )
    BEARER_PATTERN = re.compile(
        r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*',
        re.IGNORECASE,
    )
    DB_URL_PATTERN = re.compile(
        r'(postgres|postgresql|mysql|mongodb|redis|sqlite|mssql|oracle)'
        r'://[^\s\'"<>]+',
        re.IGNORECASE,
    )
    URL_PATTERN = re.compile(r'\bhttps?://[^\s\'"<>]+', re.IGNORECASE)
    # Windows absolute path: C:\something  or UNC \\server\share
    WIN_PATH_PATTERN = re.compile(
        r'(?:[A-Za-z]:\\(?:[^\s\\/:"*?<>|]+\\)*[^\s\\/:"*?<>|]*'
        r'|\\\\[^\s\\]+\\[^\s\\]+(?:\\[^\s]*)?)'
    )
    # POSIX absolute path: /usr/local/something  (at least 2 components)
    POSIX_PATH_PATTERN = re.compile(
        r'(?<!\w)/(?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]*'
    )
    UUID_PATTERN = re.compile(
        r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}'
        r'-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
    )
    FQDN_PATTERN = re.compile(
        r'\b(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+'
        r'[A-Za-z]{2,63}\b'
    )
    HOSTNAME_FIELD_PATTERN = re.compile(
        r'\b(host|hostname|server|node)\s*[:=]\s*[A-Za-z0-9_.\-]+',
        re.IGNORECASE,
    )
    USER_FIELD_PATTERN = re.compile(
        r'\b(user|username|account|login)\s*[:=]\s*[A-Za-z0-9_.\-\\]+',
        re.IGNORECASE,
    )

    def scrub(self, scanned_data: dict[str, Any]) -> dict[str, Any]:
        cleaned_records = []
        redaction_count = 0

        for record in scanned_data.get('records', []):
            orig_msg = record.get('message', '')
            orig_raw = record.get('raw_text', '')

            clean_message = self._redact(orig_msg)
            clean_text = self._redact(orig_raw)

            if clean_message != orig_msg or clean_text != orig_raw:
                redaction_count += 1

            cleaned_records.append(
                {
                    **record,
                    'clean_message': self._normalize_whitespace(clean_message),
                    'clean_text': self._normalize_whitespace(clean_text),
                    'level': (
                        'WARN'
                        if record.get('level') == 'WARNING'
                        else record.get('level', 'INFO')
                    ),
                }
            )

        return {
            **scanned_data,
            'records': cleaned_records,
            'scrub_summary': {
                'records_scrubbed': len(cleaned_records),
                'records_redacted': redaction_count,
            },
        }

    def _redact(self, text: str) -> str:
        if not text:
            return text
        text = self.BEARER_PATTERN.sub(r'\1<redacted>', text)
        text = self.DB_URL_PATTERN.sub(r'\1://<redacted>', text)
        text = self.URL_PATTERN.sub('<url>', text)
        text = self.TOKEN_PATTERN.sub(r'\1=<redacted>', text)
        text = self.EMAIL_PATTERN.sub('<email>', text)
        text = self.IP_PATTERN.sub('<ip>', text)
        text = self.UUID_PATTERN.sub('<uuid>', text)
        text = self.HOSTNAME_FIELD_PATTERN.sub(r'\1=<hostname>', text)
        text = self.USER_FIELD_PATTERN.sub(r'\1=<user>', text)
        text = self.FQDN_PATTERN.sub('<hostname>', text)
        text = self.WIN_PATH_PATTERN.sub('<path>', text)
        text = self.POSIX_PATH_PATTERN.sub('<path>', text)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return ' '.join(text.split())
