"""Gmail SMTP qua App Password. smtplib chạy trong thread (không block event loop)."""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.adapters.email.base import EmailSender
from app.config import get_settings

log = logging.getLogger(__name__)


class SmtpSender(EmailSender):
    def _send_sync(self, to_email: str, subject: str, body_text: str) -> None:
        s = get_settings()
        msg = EmailMessage()
        # EMAIL_FROM dạng "Name <addr>" — tách địa chỉ gửi
        from_addr = s.email_from
        if "<" in from_addr and ">" in from_addr:
            from_addr = from_addr.split("<", 1)[1].rstrip(">")
        msg["From"] = s.email_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body_text)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(s.smtp_user, s.smtp_pass)
            server.send_message(msg)

    async def send(self, to_email: str, subject: str, body_text: str) -> None:
        await asyncio.to_thread(self._send_sync, to_email, subject, body_text)
        log.info("Email đã gửi tới %s (subject=%r)", _mask(to_email), subject)


def _mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"
