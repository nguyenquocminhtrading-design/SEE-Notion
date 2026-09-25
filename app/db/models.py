"""Models SQLite — trạng thái vận hành của hệ thống (Notion = nguồn sự thật nghiệp vụ)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    discord_id: Mapped[str] = mapped_column(Text, default="", unique=True)
    notion_user_id: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(Text, default="member")  # admin|member|viewer
    prefs_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PendingAction(Base):
    __tablename__ = "pending_actions"
    nonce: Mapped[str] = mapped_column(Text, primary_key=True)
    discord_user: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, default=utcnow_iso)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    consumed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationLog(Base):
    """TRÁI TIM chống gửi trùng: UNIQUE(task_id, rule_key, due_date, channel)."""
    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("task_id", "rule_key", "due_date", "channel", name="uq_dedupe"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_key: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)   # email | discord_dm
    status: Mapped[str] = mapped_column(Text, default="QUEUED")  # QUEUED|SENT|FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, default=utcnow_iso)
    delivered_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    """Append-only. Không sửa, không xóa."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(Text, default=utcnow_iso)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    task_ref: Mapped[str] = mapped_column(Text, default="")
    diff_json: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="ok")


class Counter(Base):
    """Sinh TSK-#### tuần tự."""
    __tablename__ = "counters"
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
