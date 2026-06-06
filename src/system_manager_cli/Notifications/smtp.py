"""
Notifications/smtp.py — SMTP Transport Layer

Single responsibility: connect to SMTP server and send one email.
Nothing here knows about templates, subjects, or business logic.

For production on Railway: all credentials come from environment variables.
No .env file loading needed.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config.config import Config
from ..ulits.logger import get_logger

logger = get_logger(__name__, "email_notifier.log")

_PLACEHOLDERS = {
    "your_email@gmail.com", "your_app_password",
    "recipient@gmail.com",  "example@gmail.com", "",
}


def _norm(val: str | None) -> str:
    """Strip quotes and spaces from a credential string."""
    return (val or "").strip().strip('"').strip("'").replace(" ", "")


def send_email(recipient: str, subject: str, plain: str, html: str) -> bool:
    """
    Send a single email via SMTP.

    Args:
        recipient : Destination address.
        subject   : Email subject line.
        plain     : Plain-text fallback body.
        html      : Rich HTML body.

    Returns:
        True on success, False on any failure (never raises).
    
    Configuration: All SMTP settings come from environment variables (Railway).
    """
    sender   = _norm(os.getenv("EMAIL_SENDER",    Config.EMAIL_SENDER    or ""))
    password = _norm(os.getenv("EMAIL_PASSWORD",   Config.EMAIL_PASSWORD  or ""))
    fallback = _norm(os.getenv("EMAIL_RECIPIENT",  Config.EMAIL_RECIPIENT or ""))

    smtp_host    = os.getenv("SMTP_HOST",    Config.SMTP_HOST    or "smtp.gmail.com").strip()
    smtp_port    = int(os.getenv("SMTP_PORT", str(Config.SMTP_PORT or 465)))
    smtp_use_ssl = os.getenv("SMTP_USE_SSL", str(Config.SMTP_USE_SSL).lower()).lower() == "true"
    smtp_use_tls = os.getenv("SMTP_USE_TLS", str(Config.SMTP_USE_TLS).lower()).lower() == "true"

    if not sender or not password:
        logger.error("Email not sent: EMAIL_SENDER / EMAIL_PASSWORD missing in .env")
        return False

    if sender.lower() in _PLACEHOLDERS or password.lower() in _PLACEHOLDERS:
        logger.error("Email not sent: credentials are still placeholder values")
        return False

    to = (recipient or fallback).strip()
    if not to:
        logger.error("Email not sent: no recipient provided and EMAIL_RECIPIENT not set")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as srv:
                srv.ehlo()
                srv.login(sender, password)
                srv.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as srv:
                srv.ehlo()
                if smtp_use_tls:
                    srv.starttls()
                    srv.ehlo()
                srv.login(sender, password)
                srv.send_message(msg)

        logger.info("Email sent ✓  to=%s  subject=%s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP auth failed for %s: %s", sender, exc)
        return False
    except Exception as exc:
        logger.error("Email send failed to %s: %s", to, exc)
        return False
