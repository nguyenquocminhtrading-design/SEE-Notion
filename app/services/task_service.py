"""TaskService: ĐIỂM DUY NHẤT thay đổi task trong Notion. Mọi mutation có audit."""

import json
import logging

from sqlalchemy.orm import Session

from app.adapters.notion_gateway import NotionGateway
from app.db.models import AuditLog, Counter
from app.models.task import (
    validate_transition,
)

log = logging.getLogger(__name__)

# Mapping field nội bộ -> Notion properties (kế hoạch §7.5)


def build_properties(
    *,
    title: str,
    status: str | None = None,
    task_id: str | None = None,
    assignee_notion_ids: list[str] | None = None,
    creator_notion_id: str | None = None,
    deadline: str | None = None,
    priority: str | None = None,
    description: str | None = None,
    task_type: str | None = None,
    effort: str | None = None,
    start_date: str | None = None,
) -> dict:
    """Schema khớp database thật của user: Task name / Due date / Task type (multi_select) /
    Effort level. Property hệ thống (Task ID (system), Creator, Start Date…) được thêm qua API.

    assignee_notion_ids: List of Notion user IDs for multiple assignees"""
    props: dict = {"Task name": {"title": [{"text": {"content": title}}]}}
    if status:
        props["Status"] = {"status": {"name": status}}
    if task_id:
        props["Task ID (system)"] = {"rich_text": [{"text": {"content": task_id}}]}
    if assignee_notion_ids:
        props["Assignee"] = {"people": [{"id": uid} for uid in assignee_notion_ids if uid]}
    if creator_notion_id:
        props["Creator"] = {"people": [{"id": creator_notion_id}]}
    if deadline:
        props["Due date"] = {"date": {"start": deadline}}
    if start_date:
        props["Start Date"] = {"date": {"start": start_date}}
    if priority:
        props["Priority"] = {"select": {"name": priority}}
    if task_type:
        # multi_select — nhiều loại phân tách bằng dấu phẩy
        types = [t.strip() for t in task_type.split(",") if t.strip()]
        props["Task type"] = {"multi_select": [{"name": t} for t in types]}
    if effort:
        props["Effort level"] = {"select": {"name": effort}}
    if description:
        props["Description"] = {"rich_text": [{"text": {"content": description}}]}
    return props


class TaskService:
    def __init__(self, gateway: NotionGateway, session: Session):
        self.gateway = gateway
        self.session = session

    def _audit(
        self,
        actor: str,
        action: str,
        task_ref: str = "",
        diff: dict | None = None,
        result: str = "ok",
    ) -> None:
        self.session.add(
            AuditLog(
                actor=actor,
                action=action,
                task_ref=task_ref,
                diff_json=json.dumps(diff or {}, ensure_ascii=False),
                result=result,
            )
        )
        self.session.commit()

    def next_task_id(self) -> str:
        counter = self.session.get(Counter, "task")
        if counter is None:
            counter = Counter(name="task", value=0)
            self.session.add(counter)
        counter.value += 1
        self.session.commit()
        return f"TSK-{counter.value:04d}"

    # ---------- Tạo ----------

    async def create_task(
        self,
        *,
        actor_name: str,
        title: str,
        assignee_users: list | None = None,
        creator_notion_id: str | None = None,
        deadline: str | None = None,
        priority: str = "Medium",
        description: str | None = None,
        start_date: str | None = None,
        task_type: str | None = None,
        effort: str | None = None,
    ) -> dict:
        """assignee_users: list of app.db.models.User hoặc None. Idempotent theo Task ID (§7.6)."""
        task_id = self.next_task_id()
        assignee_notion_ids = []
        assignee_names = []
        if assignee_users:
            for u in assignee_users:
                if u.notion_user_id:
                    assignee_notion_ids.append(u.notion_user_id)
                assignee_names.append(u.display_name)

        props = build_properties(
            title=title,
            status="Not started",
            task_id=task_id,
            assignee_notion_ids=assignee_notion_ids,
            creator_notion_id=creator_notion_id,
            deadline=deadline,
            priority=priority,
            description=description,
            start_date=start_date,
            task_type=task_type,
            effort=effort,
        )
        page = await self.gateway.create_task_page(props)
        task = self.gateway.parse_task(page)
        self._audit(
            actor_name,
            "create",
            task_id,
            {
                "title": title,
                "deadline": deadline,
                "assignees": assignee_names,
                "priority": priority,
            },
        )
        return task

    # ---------- Tra cứu ----------

    async def find_task(self, *, task_id: str | None = None, title_hint: str | None = None) -> dict:
        if task_id:
            page = await self.gateway.query_by_task_id(task_id)
            if page is None:
                raise LookupError(f"Không tìm thấy task {task_id}.")
            return self.gateway.parse_task(page)
        if title_hint:
            pages = await self.gateway.query_by_title(title_hint)
            if not pages:
                raise LookupError(f"Không tìm thấy task nào khớp '{title_hint}'.")
            if len(pages) > 1:
                tasks = [self.gateway.parse_task(p) for p in pages[:5]]
                raise AmbiguousTask(tasks)
            return self.gateway.parse_task(pages[0])
        raise ValueError("Cần task_id hoặc title_hint.")

    # ---------- Sửa ----------

    async def change_status(self, *, actor_name: str, task: dict, target: str) -> dict:
        current = task.get("status") or "Not started"
        if current != target:
            validate_transition(current, target)
        page = await self.gateway.update_task_page(
            task["page_id"], {"Status": {"status": {"name": target}}}
        )
        self._audit(
            actor_name,
            "update_status",
            task.get("task_id", ""),
            {"status": {"old": current, "new": target}},
        )
        return self.gateway.parse_task(page)

    async def change_deadline(self, *, actor_name: str, task: dict, new_deadline: str) -> dict:
        page = await self.gateway.update_task_page(
            task["page_id"], {"Due date": {"date": {"start": new_deadline}}}
        )
        self._audit(
            actor_name,
            "change_deadline",
            task.get("task_id", ""),
            {"deadline": {"old": task.get("deadline"), "new": new_deadline}},
        )
        return self.gateway.parse_task(page)

    async def reassign(self, *, actor_name: str, task: dict, new_assignees: list) -> dict:
        assignee_notion_ids = []
        assignee_names = []
        for u in new_assignees:
            if u.notion_user_id:
                assignee_notion_ids.append(u.notion_user_id)
            assignee_names.append(u.display_name)

        props = build_properties(title=task["title"], assignee_notion_ids=assignee_notion_ids)
        page = await self.gateway.update_task_page(task["page_id"], props)
        self._audit(
            actor_name,
            "reassign",
            task.get("task_id", ""),
            {"assignee": {"new": assignee_names}},
        )
        return self.gateway.parse_task(page)

    async def archive(self, *, actor_name: str, task: dict) -> dict:
        page = await self.gateway.update_task_page(task["page_id"], {}, archived=True)
        self._audit(actor_name, "archive", task.get("task_id", ""))
        return self.gateway.parse_task(page)


class AmbiguousTask(Exception):
    def __init__(self, tasks: list[dict]):
        self.tasks = tasks
        super().__init__("Nhiều task khớp — cần làm rõ.")
