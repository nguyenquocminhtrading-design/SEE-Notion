"""Reminder Engine — scan-based, dedupe bằng UNIQUE constraint (kế hoạch §10).

Mô hình: cron tick mỗi 5' -> query task mở -> với mỗi task × rule, nếu rule đến hạn
hôm nay thì INSERT notification_log (UNIQUE task_id+rule_key+due_date+channel).
Insert thành công = "chưa gửi lần nào" -> gửi. Trùng = constraint chặn -> skip.
"""
import asyncio
import json
import logging
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.email.base import EmailSender
from app.adapters.notion_gateway import NotionGateway
from app.config import load_yaml_config
from app.db.models import NotificationLog
from app.models.task import CLOSED_STATUSES

log = logging.getLogger(__name__)

# Thuần logic — unit test không cần I/O
def compute_due_rules(deadline: str, today: str, rule_offsets: dict[str, int]) -> list[str]:
    """deadline/today: YYYY-MM-DD. rule_offsets: {rule_key: offset_days}.
    Rule đến hạn khi deadline + offset == today, hoặc quá hạn và offset lớn hơn gap
    gần nhất (lặp overN: quá hạn N ngày -> rule có offset <= N gần nhất đã phát)."""
    d = date.fromisoformat(deadline)
    t = date.fromisoformat(today)
    gap_days = (t - d).days  # âm = chưa đến hạn
    due: list[str] = []
    for rule, offset in rule_offsets.items():
        if gap_days == offset:
            due.append(rule)
    # Overdue lặp: quá hạn nhiều hơn rule lớn nhất -> phát rule có offset lớn nhất
    overdue_offsets = sorted(o for o in rule_offsets.values() if o > 0)
    if overdue_offsets and gap_days > overdue_offsets[-1]:
        due.append([k for k, v in rule_offsets.items() if v == overdue_offsets[-1]][0])
    return due


def compute_reminder_window(cfg: dict, today: date) -> tuple[str, str]:
    past = today - timedelta(days=cfg.get("scan_window_past_days", 30))
    future = today + timedelta(days=cfg.get("scan_window_future_days", 4))
    return past.isoformat(), future.isoformat()


class ReminderEngine:
    def __init__(self, gateway: NotionGateway, email: EmailSender,
                 discord_send=None, users_provider=None):
        """discord_send: async fn(discord_id, text) | None.
        users_provider: fn() -> list[User] (để biết assignee là ai)."""
        self.gateway = gateway
        self.email = email
        self.discord_send = discord_send
        self.users_provider = users_provider
        self._cfg = load_yaml_config()
        self._rules = self._cfg["reminder_rules"]
        self._offsets = {k: int(v["offset_days"]) for k, v in self._rules.items()}
        self._channels = {k: list(v["channels"]) for k, v in self._rules.items()}

    # ---------- Ghi log + dedupe ----------

    def _claim(self, session: Session, *, task_id: str, rule_key: str, due_date: str,
               recipient: str, channel: str) -> NotificationLog | None:
        """INSERT với UNIQUE — thành công = quyền gửi (claim). Trùng -> None."""
        entry = NotificationLog(task_id=task_id, rule_key=rule_key, due_date=due_date,
                                recipient=recipient, channel=channel)
        session.add(entry)
        try:
            session.commit()
            return entry
        except IntegrityError:
            session.rollback()
            return None

    # ---------- Tick chính ----------

    async def scan_and_dispatch(self, session: Session, now: date) -> int:
        past, future = compute_reminder_window(self._cfg, now)
        pages = await self.gateway.query_open_tasks(deadline_on_or_before=future)
        sent = 0
        for page in pages:
            task = self.gateway.parse_task(page)
            deadline = task.get("deadline")
            if not deadline or deadline > future:
                continue
            if task.get("status") in CLOSED_STATUSES:
                continue
            if deadline < past:  # quá cũ — bỏ để đỡ spam task quên đóng
                continue
            for rule in compute_due_rules(deadline, now.isoformat(), self._offsets):
                if await self._dispatch_rule(session, task, rule, deadline):
                    sent += 1
        if sent:
            log.info("Reminder tick: gửi %d thông báo", sent)
        return sent

    async def _dispatch_rule(self, session: Session, task: dict, rule: str, deadline: str) -> bool:
        assignee_user = self._find_assignee_user(task)
        title = task.get("title", "(không tên)")
        task_ref = task.get("task_id") or task.get("page_id", "?")
        sent_any = False

        if "email" in self._channels.get(rule, []) and assignee_user:
            entry = self._claim(session, task_id=task_ref, rule_key=rule, due_date=deadline,
                                recipient=assignee_user.email, channel="email")
            if entry:
                await self._send_with_log(session, entry, lambda: self.email.send(
                    assignee_user.email,
                    f"[SEE Notion] {rule_label(rule, deadline)}: {title}",
                    _email_body(task, rule, deadline, assignee_user.display_name),
                ))
                sent_any = True

        if "discord_dm" in self._channels.get(rule, []) and assignee_user and self.discord_send \
                and assignee_user.discord_id:
            entry = self._claim(session, task_id=task_ref, rule_key=rule, due_date=deadline,
                                recipient=assignee_user.discord_id, channel="discord_dm")
            if entry:
                try:
                    await self.discord_send(assignee_user.discord_id,
                                            f"⏰ {rule_label(rule, deadline)}: **{title}** "
                                            f"({task_ref}, deadline {deadline})")
                    entry.status, entry.delivered_at = "SENT", entry.created_at
                    session.commit()
                    sent_any = True
                except Exception as e:  # DM best-effort, không block email
                    entry.status, entry.error = "FAILED", str(e)[:300]
                    session.commit()
                    log.warning("Discord DM fail cho %s: %s", assignee_user.display_name, e)
        return sent_any

    def _find_assignee_user(self, task: dict):
        users = self.users_provider() if self.users_provider else []
        assignee_ids = set(task.get("assignee_ids") or [])
        for u in users:
            if u.notion_user_id and u.notion_user_id in assignee_ids:
                return u
        return None

    async def _send_with_log(self, session: Session, entry: NotificationLog, send_fn) -> None:
        entry.attempts += 1
        try:
            await send_fn()
            entry.status, entry.delivered_at = "SENT", entry.created_at
        except Exception as e:
            entry.status, entry.error = "FAILED", str(e)[:300]
            log.error("Gửi email fail (task=%s rule=%s): %s", entry.task_id, entry.rule_key, e)
        finally:
            session.commit()


def rule_label(rule: str, deadline: str) -> str:
    return {
        "pre3": f"Nhắc trước 3 ngày (deadline {deadline})",
        "pre1": f"SẮP ĐẾN HẠN (deadline {deadline})",
        "due": f"ĐẾN HẠN HÔM NAY ({deadline})",
        "over1": f"QUÁ HẠN (deadline {deadline})",
        "over3": "QUÁ HẠN — nhắc lại",
        "over6": "QUÁ HẠN LÂU — nhắc lại",
    }.get(rule, f"Nhắc hạn ({rule})")


def _email_body(task: dict, rule: str, deadline: str, assignee: str) -> str:
    lines = [
        f"Chào {assignee},",
        "",
        f"Task: {task.get('title', '(không tên)')}",
        f"Mã: {task.get('task_id') or task.get('page_id', '?')}",
        f"Deadline: {deadline} (23:59 ICT)",
        f"Trạng thái: {task.get('status', 'Not started')}",
    ]
    if task.get("description"):
        lines += ["", "Mô tả:", task["description"]]
    lines += ["", "Xem chi tiết trong Notion.", "", "— SEE Notion Bot (email tự động)"]
    return "\n".join(lines)
