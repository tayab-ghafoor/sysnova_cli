"""Session validation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def check_authentication(session_id: str | None, auth_manager: Any) -> bool:
    """Return True only when *session_id* is a real, unexpired auth token."""
    if not session_id:
        return False

    try:
        verify_token = getattr(auth_manager, "verify_token", None)
        if callable(verify_token):
            return bool(verify_token(session_id))

        sessions: dict[str, Any] = auth_manager.sessions
        for _user_key, session_data in sessions.items():
            if session_data.get("token") != session_id:
                continue

            expires_at = session_data.get("expires_at", "")
            if not expires_at:
                return False

            expiry = datetime.fromisoformat(expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            return expiry > datetime.now(timezone.utc)
    except Exception:
        return False

    return False
