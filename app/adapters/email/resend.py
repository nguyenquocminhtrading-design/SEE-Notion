"""Resend — nâng cấp deliverability sau MVP (kế hoạch §4.3). Cần RESEND_API_KEY."""
import logging

import httpx

from app.adapters.email.base import EmailSender
from app.config import get_settings

log = logging.getLogger(__name__)


class ResendSender(EmailSender):
    def __init__(self):
        s = get_settings()
        self._client = httpx.AsyncClient(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
            timeout=30.0,
        )

    async def send(self, to_email: str, subject: str, body_text: str) -> None:
        resp = await self._client.post(
            "/emails",
            json={"from": get_settings().email_from, "to": [to_email], "subject": subject, "text": body_text},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Resend {resp.status_code}: {resp.text[:200]}")
        log.info("Email (Resend) đã gửi tới %s", to_email)

    async def close(self) -> None:
        await self._client.aclose()
