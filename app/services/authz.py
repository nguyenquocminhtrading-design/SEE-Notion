"""AuthZ: map Discord ID -> user nội bộ, RBAC. Danh bạ seed từ team.yaml."""
import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_team
from app.db.models import User

log = logging.getLogger(__name__)


class NotAuthorized(Exception):
    pass


@dataclass
class Actor:
    user: User

    @property
    def display_name(self) -> str:
        return self.user.display_name

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"


def seed_users_from_yaml(session: Session) -> int:
    """Đồng bộ team.yaml -> DB (chạy mỗi lần khởi động).
    Upsert theo Discord ID TRƯỚC (đúng danh tính), rồi theo email — tránh lỗi UNIQUE
    khi user đổi tên/email trong yaml."""
    count = 0
    for entry in load_team():
        display_name = str(entry["display_name"]).strip()
        email = str(entry["email"]).strip()
        discord_id = str(entry.get("discord_id", "")).strip()
        prefs = entry.get("prefs", {})
        existing = None
        if discord_id:
            existing = session.scalar(select(User).where(User.discord_id == discord_id))
        if existing is None:
            existing = session.scalar(select(User).where(User.email == email))
        if existing:
            existing.display_name = display_name
            existing.full_name = entry.get("full_name", "").strip()
            existing.email = email
            existing.discord_id = discord_id
            # CHỈ ghi đè notion_user_id khi yaml có giá trị thật —
            # không xóa mất ID do sync_notion_users tự map ở lần chạy trước
            yaml_notion_id = str(entry.get("notion_user_id", "")).strip()
            if yaml_notion_id:
                existing.notion_user_id = yaml_notion_id
            existing.role = entry.get("role", "member")
            existing.prefs_json = json.dumps(prefs, ensure_ascii=False)
        else:
            session.add(User(
                display_name=display_name,
                full_name=entry.get("full_name", "").strip(),
                email=email,
                discord_id=discord_id,
                notion_user_id=entry.get("notion_user_id", "").strip(),
                role=entry.get("role", "member"),
                prefs_json=json.dumps(prefs, ensure_ascii=False),
            ))
        count += 1
    session.commit()
    log.info("Đã seed %d user từ team.yaml", count)
    return count


def get_actor_by_discord_id(session: Session, discord_id: str) -> Actor:
    user = session.scalar(select(User).where(User.discord_id == str(discord_id), User.active == True))  # noqa: E712
    if user is None:
        raise NotAuthorized(
            "Bạn chưa có trong danh bạ team. Liên hệ admin (xem team.yaml) để được thêm."
        )
    return Actor(user)


def require_role(actor: Actor, *roles: str) -> None:
    if actor.role not in roles:
        raise NotAuthorized(f"Hành động này cần vai trò {' hoặc '.join(roles)}, bạn đang là {actor.role}.")


def can_edit_task(actor: Actor, task: dict, users_by_notion_id: dict[str, User]) -> bool:
    """Admin sửa mọi task; member chỉ sửa task mình tạo hoặc được assign."""
    if actor.is_admin:
        return True
    assignee_ids = task.get("assignee_ids") or []
    if actor.user.notion_user_id and actor.user.notion_user_id in assignee_ids:
        return True
    # creator của task chính là người đã tạo qua hệ thống — ghi trong audit (đơn giản: admin-only check MVP)
    return False
