"""
src/mcp/servers/email_server.py — Gmail IMAP/SMTP tools
"""

import imaplib
import smtplib
import email
from email.message import EmailMessage
from typing import Optional

from src.config.settings import EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, SMTP_SERVER, SMTP_PORT
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _get_imap() -> Optional[imaplib.IMAP4_SSL]:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        return mail
    except Exception as exc:
        logger.error("IMAP login failed: %s", exc)
        return None


async def read_emails(folder: str = "INBOX", count: int = 5) -> dict:
    """Read recent emails from a specific folder."""
    mail = _get_imap()
    if not mail:
        return {"error": "Email credentials not configured."}

    try:
        mail.select(folder)
        _, messages = mail.search(None, "ALL")
        if not messages[0]:
            return {"emails": []}

        msg_ids = messages[0].split()
        recent_ids = msg_ids[-count:]
        
        results = []
        for msg_id in reversed(recent_ids):
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract plain text body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body += payload.decode(errors="ignore")
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode(errors="ignore")

                    results.append({
                        "id": msg_id.decode(),
                        "subject": msg.get("Subject", "No Subject"),
                        "from": msg.get("From", "Unknown"),
                        "date": msg.get("Date", "Unknown"),
                        "body_preview": body[:500] + ("..." if len(body) > 500 else "")
                    })
        mail.logout()
        return {"emails": results}
    except Exception as exc:
        return {"error": f"Failed to read emails: {str(exc)}"}


async def send_email(to_address: str, subject: str, body: str) -> dict:
    """Send an email via SMTP. (Requires Approval via Phase 5 gateway)"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return {"error": "Email credentials not configured."}

    logger.info("Sending email to %s: %s", to_address, subject)
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_address

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        return {"status": "success", "message": f"Email sent to {to_address}"}
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        return {"error": f"Failed to send email: {str(exc)}"}


def register_email_tools() -> None:
    client = get_mcp_client()
    
    client.register_tool(
        name="read_emails",
        func=read_emails,
        description="Read recent emails from the user's inbox.",
        parameters={
            "type": "object",
            "properties": {
                "folder": {"type": "string", "default": "INBOX"},
                "count": {"type": "integer", "default": 5}
            }
        }
    )
    
    client.register_tool(
        name="send_email",
        func=send_email,
        description="Send an email. Requires explicit user approval.",
        parameters={
            "type": "object",
            "properties": {
                "to_address": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to_address", "subject", "body"]
        }
    )
