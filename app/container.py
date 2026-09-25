"""Container: dựng toàn bộ dependency 1 lần, chia sẻ cho bot/API/scheduler."""
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select

from app.adapters.email.base import EmailSender, make_email_sender
from app.adapters.llm.base import LLMClient
from app.adapters.llm.factory import make_llm_client
from app.adapters.notion_gateway import NotionGateway
from app.config import load_team
from app.db.models import User
from app.db.session import get_session, init_db
from app.services.authz import seed_users_from_yaml
from app.services.command_flow import CommandFlow
from app.services.confirmation import ConfirmationService
from app.services.parser import ParserService
from app.services.reminder_engine import ReminderEngine
from app.services.task_service import TaskService

log = logging.getLogger(__name__)


@dataclass
class Container:
    gateway: NotionGateway
    parser: ParserService
    tasks: TaskService
    flow: CommandFlow
    confirmations: ConfirmationService
    reminder: ReminderEngine
    llm: LLMClient
    email: EmailSender
    _discord_send: Optional[object] = field(default=None, repr=False)

    def users_provider(self):
        session = get_session()
        try:
            return list(session.scalars(select(User).where(User.active == True)))  # noqa: E712
        finally:
            session.close()

    def set_discord_sender(self, sender) -> None:
        self._discord_send = sender
        self.reminder.discord_send = sender

    async def send_discord_dm(self, discord_id: str, text: str) -> None:
        if self._discord_send is None:
            raise RuntimeError("Discord bot chưa sẵn sàng")
        await self._discord_send(discord_id, text)

    async def sync_notion_users(self) -> int:
        """Tự map notion_user_id cho user chưa có: khớp email (nếu integration có
        quyền đọc email), fallback khớp tên không dấu. Best-effort khi khởi động."""
        import unicodedata

        def norm(s: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                           if unicodedata.category(c) != "Mn")

        try:
            notion_users = await self.gateway.list_users()
        except Exception as e:
            log.warning("Không lấy được Notion users — bỏ qua sync user ID: %s", e)
            return 0
        matched = 0
        session = get_session()
        try:
            for u in session.scalars(select(User).where(User.active == True)):  # noqa: E712
                if u.notion_user_id:
                    continue
                for nu in notion_users:
                    if nu.get("type") != "person":
                        continue  # bỏ qua bot
                    person = nu.get("person") or {}
                    email = (person.get("email") or "").strip().lower()
                    name = nu.get("name") or ""
                    if (email and email == u.email.lower()) or (name and norm(name) == norm(u.display_name)):
                        u.notion_user_id = nu["id"]
                        matched += 1
                        break
            session.commit()
        finally:
            session.close()
        if matched:
            log.info("Đã tự map %d Notion user ID", matched)
        return matched


def build_container() -> Container:
    init_db()
    session = get_session()
    try:
        seed_users_from_yaml(session)
    finally:
        session.close()

    llm = make_llm_client()
    parser = ParserService(llm, team_names=[u["display_name"] for u in load_team()])
    gateway = NotionGateway()
    tasks = TaskService(gateway, get_session())
    confirmations = ConfirmationService()
    email = make_email_sender()
    reminder = ReminderEngine(gateway, email)
    flow = CommandFlow(parser, tasks, users_provider=None, email=email)
    c = Container(gateway=gateway, parser=parser, tasks=tasks, flow=flow,
                  confirmations=confirmations, reminder=reminder, llm=llm, email=email)
    c.flow.users_provider = c.users_provider  # type: ignore[method-assign]
    c.reminder.users_provider = c.users_provider  # type: ignore[method-assign]
    return c
