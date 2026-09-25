"""EmailSender interface — swap SMTP/Resend không sửa service."""
from abc import ABC, abstractmethod

from app.config import get_settings


class EmailSender(ABC):
    @abstractmethod
    async def send(self, to_email: str, subject: str, body_text: str) -> None:
        """Raise Exception khi gửi fail (service lo retry + log)."""


def make_email_sender() -> EmailSender:
    backend = get_settings().email_backend
    if backend == "smtp":
        from app.adapters.email.smtp import SmtpSender
        return SmtpSender()
    if backend == "resend":
        from app.adapters.email.resend import ResendSender
        return ResendSender()
    raise ValueError(f"EMAIL_BACKEND không hợp lệ: {backend}")
