"""
skills/email_skill.py — Email Sending Skill

Sends emails through Gmail SMTP (port 465, SSL) using credentials
stored in ``.env``.  Parses natural-language voice commands to extract
the recipient address, subject line, and message body.

Environment Variables (in .env):
    GMAIL_ADDRESS=your_email@gmail.com
    GMAIL_APP_PASSWORD=your_app_password_here

Commands:
    "send email to john@gmail.com saying hello how are you"
    "email to alice@example.com subject meeting body see you at 3"
    "mail to bob@gmail.com hello from Jarvis"
"""

import os
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from skills.base_skill import BaseSkill


# ──────────────────────────────────────────────
#  SMTP Configuration
# ──────────────────────────────────────────────

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


# ──────────────────────────────────────────────
#  EmailSkill
# ──────────────────────────────────────────────

class EmailSkill(BaseSkill):
    """Sends emails via Gmail SMTP from voice commands."""

    @property
    def name(self) -> str:
        return "Email"

    @property
    def keywords(self) -> list[str]:
        return ["send email", "email to", "mail to", "send a mail", "send an email"]

    # ── Execution ─────────────────────────────

    def execute(self, query: str) -> str:
        """
        Parse the email query, validate credentials, and send.

        Returns a voice-friendly confirmation or error message.
        """
        # Load credentials from environment
        sender_email = os.getenv("GMAIL_ADDRESS", "").strip()
        app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()

        if not sender_email or not app_password:
            return (
                "Email is not configured. Please set GMAIL_ADDRESS and "
                "GMAIL_APP_PASSWORD in your .env file."
            )

        # Parse the query
        parsed = self._parse_email_query(query)
        if parsed is None:
            return (
                "I couldn't understand the email request. "
                "Try saying: send email to someone@gmail.com saying your message here."
            )

        to_address, subject, body = parsed

        # Validate the email address format
        if not self._is_valid_email(to_address):
            return f"The email address '{to_address}' doesn't look valid. Please try again."

        # Send the email
        success, error = self._send_email(
            sender=sender_email,
            password=app_password,
            to=to_address,
            subject=subject,
            body=body,
        )

        if success:
            return f"Email sent to {to_address} successfully."
        else:
            return f"Sorry, I couldn't send the email. Error: {error}"

    # ── SMTP Sending ──────────────────────────

    @staticmethod
    def _send_email(
        sender: str,
        password: str,
        to: str,
        subject: str,
        body: str,
    ) -> tuple[bool, str]:
        """
        Send an email via Gmail SMTP with SSL.

        Returns:
            (True, "") on success, (False, error_message) on failure.
        """
        try:
            # Build the MIME message
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Connect with SSL and send
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                server.login(sender, password)
                server.send_message(msg)

            print(f"   [✉] Email sent to {to} — subject: {subject}")
            return True, ""

        except smtplib.SMTPAuthenticationError:
            return False, (
                "Gmail authentication failed. Check your GMAIL_APP_PASSWORD "
                "in .env. You need a Google App Password, not your regular password."
            )
        except smtplib.SMTPRecipientsRefused:
            return False, f"The recipient address '{to}' was rejected by Gmail."
        except Exception as e:
            return False, str(e)

    # ── Query Parsing ─────────────────────────

    @staticmethod
    def _parse_email_query(query: str) -> tuple[str, str, str] | None:
        """
        Extract (to_address, subject, body) from a natural-language query.

        Supported patterns:
            "send email to X saying Y"
            "send email to X subject S body B"
            "email to X message Y"
            "mail to X Y"

        Returns:
            (to, subject, body) or None if parsing fails.
        """
        q = query.strip()

        # ── Pattern 1: explicit subject + body ──
        # "send email to X subject S body B"
        match = re.search(
            r"(?:send\s+(?:an?\s+)?)?(?:email|mail)\s+to\s+"
            r"(\S+@\S+)\s+"
            r"subject\s+(.+?)\s+body\s+(.+)",
            q,
            re.IGNORECASE,
        )
        if match:
            return (
                match.group(1).strip().rstrip("."),
                match.group(2).strip(),
                match.group(3).strip(),
            )

        # ── Pattern 2: "saying / message / with message" ──
        # "send email to X saying Y"
        match = re.search(
            r"(?:send\s+(?:an?\s+)?)?(?:email|mail)\s+to\s+"
            r"(\S+@\S+)\s+"
            r"(?:saying|message|with\s+message|body|that\s+says?)\s+"
            r"(.+)",
            q,
            re.IGNORECASE,
        )
        if match:
            return (
                match.group(1).strip().rstrip("."),
                "Message from Jarvis",
                match.group(2).strip(),
            )

        # ── Pattern 3: bare "email to X <rest>" ──
        # "mail to john@gmail.com hello from Jarvis"
        match = re.search(
            r"(?:send\s+(?:an?\s+)?)?(?:email|mail)\s+to\s+"
            r"(\S+@\S+)\s*(.+)?",
            q,
            re.IGNORECASE,
        )
        if match:
            to = match.group(1).strip().rstrip(".")
            body = (match.group(2) or "").strip()
            if not body:
                return None  # no body — can't send an empty email
            return to, "Message from Jarvis", body

        return None

    # ── Validation ────────────────────────────

    @staticmethod
    def _is_valid_email(address: str) -> bool:
        """Basic RFC-style email validation."""
        return bool(re.match(
            r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
            address,
        ))
