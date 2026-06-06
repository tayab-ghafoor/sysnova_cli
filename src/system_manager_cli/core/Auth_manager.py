"""Core authentication service backed by SQLite."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..Notifications.Emailer import EmailNotifier
from ..config.config import Config
from ..ulits.logger import get_logger
from .Exception import AuthenticationError
import time
logger = get_logger(__name__)


class AuthManager:
    """Local authentication with SQLite persistence.

    The public API intentionally mirrors the older JSON-backed manager so the
    application and tests can move to SQLite without a broad rewrite.
    """

    PASSWORD_HASH_ITERATIONS = 200_000
    SESSION_DURATION_HOURS = 8
    VERIFICATION_CODE_TTL_HOURS = 24

    def __init__(self, db_path: str | Path | None = None):
        Config.ensure_directories()
        self.db_path = Path(db_path) if db_path else Config.DATA_DIR / "system_manager.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_legacy_json()
        self._refresh_cache()
    # Inside AuthManager class



    def _get_resets_file(self) -> Path:
        return Config.DATA_DIR / "auth_resets.json"

    def _load_resets(self) -> dict:
        f = self._get_resets_file()
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return {}

    def _save_resets(self, data: dict) -> None:
        self._get_resets_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
        
    def forgot_password(self, email: str) -> dict:
        email = email.strip().lower()
        if not self._get_user(email):
            return {"success": False, "error": "Email not found. Please register first."}
        # Generate a 6-digit code, valid for 15 minutes.
        code = f"{secrets.randbelow(1000000):06d}"
        expires = time.time() + 15 * 60
        resets = self._load_resets()
        resets[email] = {"code": code, "expires": expires}
        self._save_resets(resets)

        # In a real system you would send the email. Here we print it for development.
        print(f"\n  [DEV] Password reset code for {email}: {code}")
        return {"success": True, "message": "Reset code sent (check console for development)."}

    def reset_password(self, email: str, code: str, new_password: str, confirm: str) -> dict:
        email = email.strip().lower()
        if new_password != confirm:
            return {"success": False, "error": "Passwords do not match."}
        resets = self._load_resets()
        record = resets.get(email)
        if not record or record["code"] != code or time.time() > record["expires"]:
            return {"success": False, "error": "Invalid or expired reset code."}
        update_result = self.update_password(email, new_password)
        if not update_result.get("success"):
            return update_result
        del resets[email]
        self._save_resets(resets)
        return {"success": True, "message": "Password reset successful."}

    def update_password(self, email: str, new_password: str) -> dict[str, Any]:
        """Update an existing local user's password hash in SQLite."""
        email = email.strip().lower()
        if len(new_password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters long."}
        user = self._get_user(email)
        if not user:
            return {"success": False, "error": "Email not found in local database."}

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE email = ?
                """,
                (self.hash_password(new_password), email),
            )
            conn.execute("DELETE FROM sessions WHERE user_email = ?", (email,))
        self._refresh_cache()
        return {"success": True, "message": "Local password updated."}

    def resend_verification_code(self, email: str) -> dict[str, Any]:
        """Resend verification code to a user's email address.
        
        Used when a user needs a new verification code during registration
        or hasn't verified their email yet.
        """
        email = email.strip().lower()
        user = self._get_user(email)
        
        if not user:
            return {"success": False, "error": "Email not found in local database."}
        
        if user.get("verified"):
            return {"success": False, "error": "This email is already verified."}
        
        # Generate new verification code
        verification_code = secrets.token_hex(3).upper()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.VERIFICATION_CODE_TTL_HOURS)
        
        # Update database with new code
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users 
                SET verification_code = ?, verification_expires_at = ?
                WHERE email = ?
                """,
                (verification_code, expires_at.isoformat(), email),
            )
        self._refresh_cache()
        
        # Send verification email
        full_name = user.get("full_name", "")
        email_sent = self._send_verification_email(email, verification_code, full_name)
        
        response: dict[str, Any] = {
            "success": True,
            "email_sent": email_sent,
            "message": "Verification code resent."
        }
        
        if not email_sent:
            response["message"] += " (check console for development mode)"
            print(f"\n  [DEV] Verification code for {email}: {verification_code}")
        
        return response
    # Database

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=2.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 2000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verification_code TEXT,
                    verification_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    verified_at TEXT,
                    last_login TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_users_username
                    ON users(username);

                CREATE TABLE IF NOT EXISTS sessions (
                    user_email TEXT PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_email) REFERENCES users(email)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS auth_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            self._ensure_sessions_schema(conn)

    def _ensure_sessions_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure legacy auth DBs have the required sessions token schema."""
        columns = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "token_hash" in columns:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions_new (
                    user_email TEXT PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_email) REFERENCES users(email)
                        ON DELETE CASCADE
                );

                INSERT INTO sessions_new (user_email, token, expires_at, created_at)
                SELECT
                    user_email,
                    CASE
                        WHEN token IS NOT NULL AND token != '' THEN token
                        WHEN token_hash IS NOT NULL AND token_hash != '' THEN token_hash
                        ELSE hex(randomblob(24))
                    END,
                    expires_at,
                    created_at
                FROM sessions;

                DROP TABLE sessions;
                ALTER TABLE sessions_new RENAME TO sessions;
                """
            )
        elif "token" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN token TEXT DEFAULT ''")
            rows = conn.execute("SELECT rowid FROM sessions WHERE token IS NULL OR token = ''").fetchall()
            for (rowid,) in rows:
                token = secrets.token_hex(24)
                conn.execute(
                    "UPDATE sessions SET token = ? WHERE rowid = ?",
                    (token, rowid),
                )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")

    def _migrate_legacy_json(self) -> None:
        with self._connect() as conn:
            done = conn.execute(
                "SELECT 1 FROM auth_migrations WHERE name = ?",
                ("legacy_json_v1",),
            ).fetchone()
        if done:
            return

        users_file = Config.DATA_DIR / "users.json"
        sessions_file = Config.DATA_DIR / "session.json"
        if not users_file.exists() and not sessions_file.exists():
            self._mark_migration_applied("legacy_json_v1")
            return

        try:
            users = json.loads(users_file.read_text(encoding="utf-8")) if users_file.exists() else {}
            sessions = json.loads(sessions_file.read_text(encoding="utf-8")) if sessions_file.exists() else {}
        except json.JSONDecodeError:
            logger.warning("Skipping auth JSON migration because a legacy file is invalid.")
            self._mark_migration_applied("legacy_json_v1")
            return

        inserted_or_updated = 0
        with self._connect() as conn:
            for email, user in (users or {}).items():
                if not isinstance(user, dict):
                    continue
                email = str(user.get("email") or email).strip().lower()
                if not email:
                    continue
                created_at = user.get("created_at") or datetime.now(timezone.utc).isoformat()
                before = conn.total_changes
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (
                        email, username, full_name, password_hash, verified,
                        verification_code, verification_expires_at,
                        created_at, verified_at, last_login
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        email,
                        user.get("username") or email.split("@", 1)[0],
                        user.get("full_name") or "",
                        user.get("password_hash") or "",
                        1 if user.get("verified") else 0,
                        user.get("verification_code"),
                        user.get("verification_expires_at"),
                        created_at,
                        user.get("verified_at"),
                        user.get("last_login"),
                    ),
                )
                inserted_or_updated += conn.total_changes - before

            for email, session in (sessions or {}).items():
                if not isinstance(session, dict):
                    continue
                email = str(email).strip().lower()
                if not conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                    continue
                token = session.get("token")
                expires_at = session.get("expires_at")
                if not token or not expires_at:
                    continue
                before = conn.total_changes
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions
                        (user_email, token, expires_at, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        email,
                        token,
                        expires_at,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                inserted_or_updated += conn.total_changes - before

        if inserted_or_updated:
            logger.info("Migrated legacy auth JSON files into %s", self.db_path)
        self._mark_migration_applied("legacy_json_v1")

    def _mark_migration_applied(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO auth_migrations (name, applied_at)
                VALUES (?, ?)
                """,
                (name, datetime.now(timezone.utc).isoformat()),
            )

    def _refresh_cache(self) -> None:
        """Refresh compatibility snapshots used by older app code/tests."""
        self._delete_expired_sessions()
        with self._connect() as conn:
            users = conn.execute("SELECT * FROM users").fetchall()
            sessions = conn.execute("SELECT * FROM sessions").fetchall()

        self.users = {
            row["email"]: {
                "email": row["email"],
                "username": row["username"],
                "full_name": row["full_name"],
                "password_hash": row["password_hash"],
                "verified": bool(row["verified"]),
                "verification_code": row["verification_code"],
                "verification_expires_at": row["verification_expires_at"],
                "created_at": row["created_at"],
                "verified_at": row["verified_at"],
                "last_login": row["last_login"],
            }
            for row in users
        }
        self.sessions = {
            row["user_email"]: {
                "token": row["token"] if row["token"] else row.get("token_hash", ""),
                "expires_at": row["expires_at"],
            }
            for row in sessions
        }

    def _delete_expired_sessions(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )

    # Password hashing

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.PASSWORD_HASH_ITERATIONS,
        )
        return f"pbkdf2_sha256${cls.PASSWORD_HASH_ITERATIONS}${salt}${digest.hex()}"

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        try:
            algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(derived.hex(), digest)

    # Lookups

    @staticmethod
    def _validate_email(email: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))

    def _get_user(self, identifier: str) -> sqlite3.Row | None:
        identifier = identifier.strip().lower()
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT * FROM users
                WHERE lower(email) = ? OR lower(username) = ?
                LIMIT 1
                """,
                (identifier, identifier),
            ).fetchone()

    def _resolve_user_key(self, identifier: str) -> str | None:
        user = self._get_user(identifier)
        return str(user["email"]) if user else None

    def _send_verification_email(
        self, email: str, verification_code: str, full_name: str = ""
    ) -> bool:
        try:
            success = EmailNotifier.send_verification_email(email, verification_code, full_name)
            if success:
                logger.info("Verification email sent to %s", email)
            return success
        except Exception as exc:
            logger.error("Exception while sending verification email to %s: %s", email, exc)
            return False

    # Registration and verification

    def register_user_with_verification(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> dict[str, Any]:
        if not full_name.strip():
            return {"success": False, "message": "Full name is required."}

        email = email.strip().lower()
        if not self._validate_email(email):
            return {"success": False, "message": "Invalid email address format."}
        if len(password) < 8:
            return {"success": False, "message": "Password must be at least 8 characters."}
        if password != confirm_password:
            return {"success": False, "message": "Passwords do not match."}
        if self._get_user(email):
            return {"success": False, "message": "Email is already registered."}

        verification_code = secrets.token_hex(3).upper()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.VERIFICATION_CODE_TTL_HOURS)
        username = email.split("@", 1)[0]

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    email, username, full_name, password_hash, verified,
                    verification_code, verification_expires_at, created_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    email,
                    username,
                    full_name.strip(),
                    self.hash_password(password),
                    verification_code,
                    expires_at.isoformat(),
                    now.isoformat(),
                ),
            )
        self._refresh_cache()

        email_sent = self._send_verification_email(email, verification_code, full_name.strip())
        response: dict[str, Any] = {
            "success": True,
            "email_sent": email_sent,
            "message": (
                f"{full_name} registered successfully! "
                f"A verification email has been sent to {email}."
                if email_sent
                else f"{full_name} registered successfully, but the verification email could not be sent."
            ),
            "user": {"full_name": full_name.strip(), "email": email, "username": username},
        }
        if not email_sent:
            response["message"] += " Check SMTP settings and request a new code."
            if Config.DEVELOPMENT_MODE:
                response["verification_code"] = verification_code
                response["message"] += f" Development verification code: {verification_code}"
        return response

    def verify_email(self, email: str, verification_code: str) -> dict[str, Any]:
        email = email.strip().lower()
        user = self._get_user(email)
        if not user:
            return {"success": False, "message": "Email not found. Please register first."}
        if bool(user["verified"]):
            return {"success": False, "message": "Email is already verified. You can log in."}

        stored_code = user["verification_code"] or ""
        expires_at = user["verification_expires_at"] or ""
        if not stored_code or not expires_at:
            return {"success": False, "message": "No verification code found for this account."}

        try:
            expiry = datetime.fromisoformat(expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError:
            return {"success": False, "message": "Verification code is invalid. Please request a new code."}

        if expiry <= datetime.now(timezone.utc):
            return {"success": False, "message": "Verification code expired. Please request a new code."}
        if stored_code.upper() != verification_code.strip().upper():
            return {"success": False, "message": "Invalid verification code. Please check and try again."}

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET verified = 1,
                    verified_at = ?,
                    verification_code = NULL,
                    verification_expires_at = NULL
                WHERE email = ?
                """,
                (datetime.now(timezone.utc).isoformat(), email),
            )
        self._refresh_cache()
        return {"success": True, "message": "Email verified successfully! You can now log in."}

    # Login/logout

    def authenticate_with_verification(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        user = self._get_user(email)
        if not user:
            return {"success": False, "message": f"{email} is not registered. Please register first."}
        if not bool(user["verified"]):
            return {
                "success": False,
                "message": "Email not verified. Please verify your email before logging in.",
            }
        return self.authenticate(email, password)

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        user = self._get_user(username)
        if not user:
            return {"success": False, "message": "Unknown user."}
        if not self.verify_password(password, user["password_hash"] or ""):
            return {"success": False, "message": "Invalid credentials."}

        token = secrets.token_hex(24)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.SESSION_DURATION_HOURS)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (user_email, token, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_email) DO UPDATE SET
                    token = excluded.token,
                    expires_at = excluded.expires_at,
                    created_at = excluded.created_at
                """,
                (user["email"], token, expires_at.isoformat(), now.isoformat()),
            )
            conn.execute(
                "UPDATE users SET last_login = ? WHERE email = ?",
                (now.isoformat(), user["email"]),
            )
        self._refresh_cache()

        return {
            "success": True,
            "token": token,
            "message": "Login successful.",
            "user": {
                "email": user["email"],
                "username": user["username"],
                "full_name": user["full_name"] or user["email"],
            },
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self.authenticate(username, password)

    def logout(self, username: str) -> dict[str, Any]:
        user = self._get_user(username)
        if user:
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE user_email = ?", (user["email"],))
            self._refresh_cache()
        return {"success": True, "message": "Logged out successfully."}

    def verify_session(self, username: str, token: str) -> bool:
        user = self._get_user(username)
        if not user:
            return False
        with self._connect() as conn:
            session = conn.execute(
                "SELECT token, expires_at FROM sessions WHERE user_email = ?",
                (user["email"],),
            ).fetchone()
        if not session or not hmac.compare_digest(session["token"], token):
            return False
        try:
            expiry = datetime.fromisoformat(session["expires_at"])
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return expiry > datetime.now(timezone.utc)

    def verify_token(self, token: str) -> bool:
        self._refresh_cache()
        for email, session in self.sessions.items():
            if self.verify_session(email, token):
                return True
        return False

    # Legacy API

    def register_user(self, email: str, password: str, full_name: str = "") -> dict[str, Any]:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise AuthenticationError("A valid email address is required.")
        if len(password) < 8:
            raise AuthenticationError("Password must be at least 8 characters.")
        if self._get_user(email):
            raise AuthenticationError("User already exists.")

        username = email.split("@", 1)[0]
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    email, username, full_name, password_hash,
                    verified, created_at, verified_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (email, username, full_name.strip(), self.hash_password(password), now, now),
            )
        self._refresh_cache()
        return {
            "success": True,
            "email": email,
            "username": username,
            "message": "User registered successfully.",
        }

    def list_users(self) -> list[dict[str, Any]]:
        self._refresh_cache()
        return [
            {
                "email": user.get("email"),
                "username": user.get("username"),
                "full_name": user.get("full_name"),
            }
            for user in self.users.values()
        ]


auth_manager: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    """Return a lazily-created module-level auth manager for legacy callers."""
    global auth_manager
    if auth_manager is None:
        auth_manager = AuthManager()
    return auth_manager
