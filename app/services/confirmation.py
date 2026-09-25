"""Pending actions: preview chờ xác nhận. Nonce 1-lần, TTL, chỉ chủ nonce redeem được."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_yaml_config
from app.db.models import PendingAction


class NonceError(Exception):
    pass


class ConfirmationService:
    def __init__(self):
        self._ttl_minutes = load_yaml_config().get("pending_action_ttl_minutes", 10)

    def create(self, session: Session, *, discord_user: str, channel_id: str,
               payload: dict, summary_lines: list[str], warnings: list[str]) -> str:
        nonce = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        summary = "\n".join(summary_lines)
        if warnings:
            summary += "\n⚠️ " + "\n⚠️ ".join(warnings)
        session.add(PendingAction(
            nonce=nonce,
            discord_user=discord_user,
            channel_id=channel_id,
            payload_json=json.dumps(payload, ensure_ascii=False),
            summary=summary,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=self._ttl_minutes)).isoformat(),
        ))
        session.commit()
        return nonce

    def redeem(self, session: Session, nonce: str, discord_user: str) -> dict:
        """Trả payload nếu hợp lệ; consume. Bất thường -> NonceError."""
        pa = session.get(PendingAction, nonce)
        if pa is None:
            raise NonceError("Không tìm thấy hành động chờ xác nhận này.")
        if pa.consumed_at is not None:
            raise NonceError("Hành động này đã được xác nhận rồi.")
        if pa.discord_user != str(discord_user):
            raise NonceError("Chỉ người tạo lệnh mới được xác nhận.")
        if datetime.now(timezone.utc).isoformat() > pa.expires_at:
            raise NonceError("Đã hết hạn (10 phút). Gửi lại lệnh nhé.")
        pa.consumed_at = datetime.now(timezone.utc).isoformat()
        session.commit()
        return json.loads(pa.payload_json)
