import os
import unittest
from unittest.mock import MagicMock, patch

from system_manager_cli.Notifications.smtp import send_email


class EmailNotifierTests(unittest.TestCase):
    @patch("system_manager_cli.Notifications.smtp.smtplib.SMTP_SSL")
    def test_send_email_uses_ssl(self, smtp_ssl_mock):
        mock_server = MagicMock()
        smtp_ssl_mock.return_value.__enter__.return_value = mock_server

        env = {
            "EMAIL_SENDER": "sender@example.com",
            "EMAIL_PASSWORD": "password",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "465",
            "SMTP_USE_SSL": "True",
            "SMTP_USE_TLS": "False",
        }
        with patch.dict(os.environ, env, clear=False):
            result = send_email(
                "recipient@example.com",
                "Test Subject",
                "Test body",
                "<p>Test body</p>",
            )

        self.assertTrue(result)
        smtp_ssl_mock.assert_called_once_with("smtp.example.com", 465, timeout=30)
        mock_server.ehlo.assert_called_once()
        mock_server.login.assert_called_once_with("sender@example.com", "password")
        mock_server.send_message.assert_called_once()

    @patch("system_manager_cli.Notifications.smtp.smtplib.SMTP")
    def test_send_email_uses_tls(self, smtp_mock):
        mock_server = MagicMock()
        smtp_mock.return_value.__enter__.return_value = mock_server

        env = {
            "EMAIL_SENDER": "sender@example.com",
            "EMAIL_PASSWORD": "password",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USE_SSL": "False",
            "SMTP_USE_TLS": "True",
        }
        with patch.dict(os.environ, env, clear=False):
            result = send_email(
                "recipient@example.com",
                "TLS Subject",
                "TLS body",
                "<p>TLS body</p>",
            )

        self.assertTrue(result)
        smtp_mock.assert_called_once_with("smtp.example.com", 587, timeout=30)
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@example.com", "password")
        mock_server.send_message.assert_called_once()

    def test_send_email_fails_without_credentials(self):
        env = {
            "EMAIL_SENDER": "",
            "EMAIL_PASSWORD": "",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USE_SSL": "False",
            "SMTP_USE_TLS": "False",
        }
        with patch.dict(os.environ, env, clear=False):
            result = send_email(
                "recipient@example.com",
                "Missing Credentials",
                "Body",
                "<p>Body</p>",
            )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
