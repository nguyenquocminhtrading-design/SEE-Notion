"""AuthZ: map Discord ID -> user nội bộ, RBAC. Danh bạ seed từ team.yaml."""
import json
import logging
import re
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
        discord_id = str(entry.get("discord_id", "")).strip() or None
        if not discord_id:
            log.warning("User %s (%s) KHÔNG CÓ discord_id trong team.yaml — chỉ dùng email/Notion, ko nhận DM Discord",
                        display_name, email)
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
    users_with_discord = sum(1 for e in load_team() if str(e.get("discord_id", "")).strip())
    users_without = count - users_with_discord
    log.info("Seed summary: %d user có discord_id, %d user chỉ email/Notion (không nhận DM Discord)", users_with_discord, users_without)
    return count


def get_actor_by_discord_id(session: Session, discord_id: str) -> Actor:
    user = session.scalar(select(User).where(User.discord_id == str(discord_id), User.active == True))
    if user is None:
        raise NotAuthorized(
            "Bạn chưa có trong danh bạ team. Liên hệ admin (xem team.yaml) để được thêm."
        )
    return Actor(user)


def require_role(actor: Actor, *roles: str) -> None:
    if actor.role not in roles:
        raise NotAuthorized(f"Hành động này cần vai trò {' hoặc '.join(roles)}, bạn đang là {actor.role}.")


def can_edit_task(actor: Actor, task: dict, users_by_notion_id: dict[str, User] | None = None) -> bool:
    """Admin sửa mọi task; member chỉ sửa task mình tạo hoặc được assign."""
    if actor.is_admin:
        return True
    assignee_ids = task.get("assignee_ids") or []
    if actor.user.notion_user_id and actor.user.notion_user_id in assignee_ids:
        return True
    # creator_id lưu notion id người tạo
    creator_id = task.get("creator_id")
    if creator_id and actor.user.notion_user_id and actor.user.notion_user_id == creator_id:
        return True
    return False


def link_discord_account(session: Session, email: str, discord_id: str) -> User:
    """Link discord_id với User qua email. Cập nhật cả DB và file team.yaml."""
    from pathlib import Path
    import yaml
    from app.config import BASE_DIR

    email_clean = email.strip().lower()
    discord_id_clean = str(discord_id).strip()

    # 1. Tìm user trong DB theo email
    user = session.scalar(select(User).where(User.email.ilike(email_clean)))
    if not user:
        raise ValueError(f"Không tìm thấy người dùng với email: {email}")

    # 2. Kiểm tra xem discord_id này đã được tài khoản khác dùng chưa
    existing_discord = session.scalar(
        select(User).where(User.discord_id == discord_id_clean, User.id != user.id)
    )
    if existing_discord:
        raise ValueError(
            f"Discord ID {discord_id_clean} đã được liên kết với tài khoản: {existing_discord.email} ({existing_discord.display_name})"
        )

    user.discord_id = discord_id_clean
    session.commit()

    # 3. Cập nhật trực tiếp vào team.yaml (giữ nguyên comment và định dạng)
    team_yaml_path = BASE_DIR / "team.yaml"
    if team_yaml_path.exists():
        try:
            content = team_yaml_path.read_text(encoding="utf-8")
            # Tìm block của email này và cập nhật discord_id
            pattern = rf'(email:\s*["\']?{re.escape(email_clean)}["\']?\s*\n\s*discord_id:\s*)["\']?[^"\']*["\']?'
            if re.search(pattern, content, flags=re.IGNORECASE):
                new_content = re.sub(
                    pattern,
                    rf'\g<1>"{discord_id_clean}"',
                    content,
                    flags=re.IGNORECASE,
                )
                team_yaml_path.write_text(new_content, encoding="utf-8")
            else:
                # Fallback dùng safe_load nếu regex không match
                data = yaml.safe_load(content) or {}
                for u in data.get("users", []):
                    if str(u.get("email", "")).strip().lower() == email_clean:
                        u["discord_id"] = discord_id_clean
                        break
                team_yaml_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            log.info("Đã cập nhật discord_id=%s cho email=%s vào team.yaml", discord_id_clean, email_clean)
        except Exception as e:
            log.error("Không thể ghi cập nhật discord_id vào team.yaml: %s", e)

    return user
