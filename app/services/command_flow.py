"""Orchestrator luồng lệnh NL: parse -> validate -> preview -> [xác nhận] -> execute.

Discord bot và REST API đều gọi lớp này — không chứa logic Discord.
"""
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.models.preview import ActionError, ClarifyError
from app.models.parsed_command import ParsedCommand
from app.models.task import CLOSED_STATUSES, validate_transition
from app.services import validator as vld
from app.services.parser import ParseError, ParserService
from app.services.task_service import AmbiguousTask, TaskService

log = logging.getLogger(__name__)

MUTATING_INTENTS = {"create_task", "update_task", "assign_task", "change_deadline",
                    "complete_task", "archive_task"}
DESTRUCTIVE_INTENTS = {"archive_task"}


class CommandFlow:
    def __init__(self, parser: ParserService, task_service: TaskService, users_provider, email=None):
        self.parser = parser
        self.tasks = task_service
        self.users_provider = users_provider
        self.email = email

    # ---------- Giai đoạn 1: chuẩn bị preview ----------

    async def prepare(self, *, actor, text: str, today: date, session: Session) -> dict:
        """Trả về {'summary_lines', 'warnings', 'payload', 'intent', 'expires_in_seconds'}.
        Raise ParseError / ClarifyError / ActionError."""
        parsed = await self.parser.parse(text, today.isoformat())

        if parsed.intent == "unknown" or parsed.confidence < 0.5:
            raise ParseError(
                "Mình không hiểu lệnh này là hành động gì. "
                "Thử mẫu: 'Assign <người> làm <việc> trước ngày <dd/mm/yyyy>'."
            )

        if parsed.intent in MUTATING_INTENTS:
            return await self._prepare_mutation(parsed, actor=actor, today=today, session=session)
        return await self.handle_query(parsed, actor=actor, session=session)

    async def prepare_create(self, *, actor, fields: dict, today: date, session: Session) -> dict:
        warnings: list[str] = []
        
        # Parse start_date
        if fields.get("start_date"):
            start_str = fields["start_date"]
            parsed_start = vld.try_parse_date_simple(start_str, today)
            if not parsed_start:
                parsed_start = await self.parser.parse_date(start_str, today.isoformat())
            fields["start_date"] = parsed_start
            if not parsed_start:
                warnings.append(f"Không thể nhận diện ngày bắt đầu: {start_str}")
        else:
            fields["start_date"] = None

        # Parse deadline
        due_str = fields["deadline"]
        parsed_due = vld.try_parse_date_simple(due_str, today)
        if not parsed_due:
            parsed_due = await self.parser.parse_date(due_str, today.isoformat())
        fields["deadline"] = parsed_due

        if not parsed_due:
            raise ActionError("VALIDATION_FAILED", f"Không thể nhận diện hạn chót: {due_str}. Hãy nhập ngày rõ ràng (VD: 30/09/2026).")
        
        if parsed_due < today.isoformat():
            warnings.append(f"Deadline {parsed_due} là ngày trong quá khứ so với hôm nay {today.isoformat()} — bạn chắc chứ?")

        # Assignee
        assignee = vld.resolve_assignee(fields["assignee_name_raw"], self.users_provider())
        
        payload = {
            "intent": "create_task",
            "actor": actor.display_name,
            "title": fields["title"],
            "deadline": fields["deadline"],
            "priority": fields["priority"],
            "task_type": fields["task_type"],
            "effort": fields["effort"],
            "description": fields.get("description"),
            "assignee_email": assignee.email,
            "assignee_notion_id": assignee.notion_user_id or "",
        }

        # Build summary
        lines = [f"Tạo task: {fields['title']}"]
        lines.append(f"Assignee: {assignee.display_name}")
        lines.append(f"Deadline: {fields['deadline']} (23:59 ICT)")
        lines.append(f"Priority: {fields['priority']} | Effort: {fields['effort']} | Type: {fields['task_type']}")
        if fields.get("start_date"):
            lines.append(f"Start date: {fields['start_date']}")
        if fields.get("description"):
            lines.append(f"Mô tả: {fields['description']}")

        payload["summary_lines"] = lines

        return {"summary_lines": lines, "warnings": warnings, "payload": payload, "intent": "create_task", "expires_in_seconds": 600}

    async def prepare_update(self, *, actor, text: str, today: date, session: Session) -> dict:
        parsed = await self.parser.parse_update(text, today.isoformat())
        return await self._prepare_mutation(parsed, actor=actor, today=today, session=session)

    async def prepare_complete(self, *, actor, text: str, today: date, session: Session) -> dict:
        parsed = await self.parser.parse_complete(text)
        return await self._prepare_mutation(parsed, actor=actor, today=today, session=session)

    async def _prepare_mutation(self, parsed: ParsedCommand, *, actor, today: date,
                                session: Session) -> dict:
        fields, warnings = vld.build_preview_fields(parsed, today)
        payload: dict = {"intent": parsed.intent, "fields": fields, "actor": actor.display_name}

        if parsed.intent == "create_task":
            if not fields["title"]:
                raise ActionError("VALIDATION_FAILED", "Thiếu tên task. Task tên gì?")
            if not fields["deadline"]:
                raise ActionError("VALIDATION_FAILED", "Thiếu deadline. Hạn khi nào?")
            assignee = None
            if fields["assignee_name_raw"]:
                assignee = vld.resolve_assignee(
                    fields["assignee_name_raw"], self.users_provider())
                payload["assignee_email"] = assignee.email
                payload["assignee_notion_id"] = assignee.notion_user_id or ""
            payload["title"] = fields["title"]
            payload["deadline"] = fields["deadline"]
            payload["priority"] = fields["priority"]
            payload["description"] = fields["description"]
            payload["task_type"] = fields.get("task_type")
            payload["effort"] = fields.get("effort")
            summary = self._create_summary(fields, assignee)
            payload["summary_lines"] = summary

        elif parsed.intent in {"complete_task", "archive_task", "update_task",
                               "assign_task", "change_deadline"}:
            task = await self._find_task(fields["task_ref"])
            payload["task_ref_page_id"] = task["page_id"]
            payload["task_ref_title"] = task["title"]
            payload["task_ref_task_id"] = task.get("task_id")
            payload["task_status"] = task.get("status")
            payload["task_deadline"] = task.get("deadline")

            if parsed.intent == "complete_task":
                payload["new_status"] = "Done"
                self._check_transition(task, "Done")
                summary = [f"Hoàn thành task: {task['title']} ({task.get('task_id')})"]
            elif parsed.intent == "archive_task":
                summary = [f"⚠️ LƯU TRỮ (archive) task: {task['title']} ({task.get('task_id')})",
                           "Task sẽ bị ẩn khỏi Notion database."]
            elif parsed.intent == "change_deadline":
                if not fields["deadline"]:
                    raise ActionError("VALIDATION_FAILED", "Chưa nói deadline mới là ngày nào.")
                payload["new_deadline"] = fields["deadline"]
                old = task.get("deadline") or "(chưa có)"
                summary = [f"Đổi deadline task '{task['title']}' ({task.get('task_id')})",
                           f"  {old} → {fields['deadline']}"]
                if fields["deadline"] != old and task.get("status") not in CLOSED_STATUSES:
                    pass  # reminder engine tự tính lại theo deadline mới
            else:  # update_task / assign_task
                summary, changes = await self._prepare_update(task, parsed, fields)
                payload["changes"] = changes
                if not changes:
                    raise ActionError("VALIDATION_FAILED",
                                      "Mình chưa hiểu bạn muốn sửa gì (status? deadline? assignee?).")
        else:
            raise ActionError("UNSUPPORTED", f"Intent {parsed.intent} chưa hỗ trợ.")

        return {"summary_lines": summary, "warnings": warnings, "payload": payload,
                "intent": parsed.intent, "expires_in_seconds": 600}

    def _create_summary(self, fields: dict, assignee) -> list[str]:
        lines = [f"Tạo task: {fields['title']}"]
        lines.append(f"Assignee: {assignee.display_name}" if assignee else "Assignee: (chưa gán)")
        lines.append(f"Deadline: {fields['deadline']} (23:59 ICT)")
        lines.append(f"Priority: {fields['priority']}")
        if fields.get("task_type"):
            lines.append(f"Task type: {fields['task_type']}")
        if fields.get("effort"):
            lines.append(f"Effort: {fields['effort']}")
        if fields["description"]:
            lines.append(f"Mô tả: {fields['description']}")
        return lines

    async def _prepare_update(self, task: dict, parsed: ParsedCommand, fields: dict):
        changes: dict = {}
        if parsed.status:
            validate_transition(task.get("status") or "Not started", parsed.status)
            changes["status"] = parsed.status
        if fields["deadline"]:
            changes["deadline"] = fields["deadline"]
        if fields["assignee_name_raw"]:
            assignee = vld.resolve_assignee(fields["assignee_name_raw"], self.users_provider())
            changes["assignee_email"] = assignee.email
            changes["assignee_notion_id"] = assignee.notion_user_id or ""
        lines = [f"Cập nhật task: {task['title']} ({task.get('task_id')})"]
        if "status" in changes:
            lines.append(f"  Status: {task.get('status')} → {changes['status']}")
        if "deadline" in changes:
            lines.append(f"  Deadline: {task.get('deadline')} → {changes['deadline']}")
        if "assignee_email" in changes:
            lines.append(f"  Assignee → {fields['assignee_name_raw']}")
        return lines, changes

    async def _find_task(self, task_ref: dict) -> dict:
        if not task_ref.get("task_id") and not task_ref.get("title_hint"):
            raise ActionError(
                "TASK_NOT_SPECIFIED",
                "Không rõ task nào. Nói kèm tên task hoặc mã TSK-xxxx "
                "(vd: 'task viết tài liệu xong rồi' hoặc 'hoàn thành TSK-0003').")
        try:
            return await self.tasks.find_task(
                task_id=task_ref.get("task_id"), title_hint=task_ref.get("title_hint"))
        except AmbiguousTask as e:
            raise ClarifyError(
                "AMBIGUOUS_TASK",
                "Nhiều task khớp — nói rõ hơn hoặc dùng mã TSK-xxxx:\n" +
                "\n".join(f"• {t.get('task_id')}: {t['title']}" for t in e.tasks),
            ) from e
        except LookupError as e:
            raise ActionError("TASK_NOT_FOUND", str(e)) from e

    @staticmethod
    def _check_transition(task: dict, target: str) -> None:
        validate_transition(task.get("status") or "Not started", target)

    # ---------- Giai đoạn 2: thực thi sau khi ✅ ----------

    async def execute(self, *, actor, payload: dict, session: Session) -> str:
        intent = payload["intent"]
        if intent == "create_task":
            assignee = self._user_by_email(session, payload.get("assignee_email"))
            task = await self.tasks.create_task(
                actor_name=actor.display_name,
                title=payload["title"],
                assignee_user=assignee,
                creator_notion_id=actor.user.notion_user_id or None,
                deadline=payload["deadline"],
                priority=payload["priority"],
                description=payload["description"],
            )
            
            if self.email and assignee and assignee.email:
                subject = f"[Task Mới] Bạn có công việc mới: {task['title']}"
                body = (
                    f"Chào {assignee.display_name},\n\n"
                    f"Bạn vừa được giao một task mới từ hệ thống:\n"
                    f"- Tên công việc: {task['title']}\n"
                    f"- Deadline: {payload['deadline']}\n\n"
                    f"Xem chi tiết tại Notion: {task['url']}\n\n"
                    f"*Lưu ý: Task này sẽ tự động xuất hiện trên Notion Calendar của bạn.*\n"
                )
                try:
                    await self.email.send(assignee.email, subject, body)
                except Exception as e:
                    log.error(f"Lỗi khi gửi email cho {assignee.email}: {e}")

            return f"✅ Đã tạo **{task['task_id']}**: {task['title']}\n{task['url']}\n" \
                   f"Assignee: {assignee.display_name if assignee else '(chưa gán)'} · " \
                   f"Deadline: {payload['deadline']}"

        page_id = payload["task_ref_page_id"]
        task = {"page_id": page_id, "title": payload["task_ref_title"],
                "task_id": payload.get("task_ref_task_id"),
                "status": payload.get("task_status"), "deadline": payload.get("task_deadline")}

        if intent == "complete_task":
            await self.tasks.change_status(actor_name=actor.display_name, task=task, target="Done")
            return f"✅ Đã hoàn thành: {task['title']} ({task.get('task_id')})"
        if intent == "archive_task":
            await self.tasks.archive(actor_name=actor.display_name, task=task)
            return f"📦 Đã archive: {task['title']} ({task.get('task_id')})"
        if intent == "change_deadline":
            await self.tasks.change_deadline(actor_name=actor.display_name, task=task,
                                             new_deadline=payload["new_deadline"])
            return f"✅ Deadline mới của {task['title']}: {payload['new_deadline']}"

        if intent in {"update_task", "assign_task"}:
            changes = payload.get("changes", {})
            if "status" in changes:
                await self.tasks.change_status(actor_name=actor.display_name, task=task,
                                               target=changes["status"])
            if "deadline" in changes and intent != "assign_task":
                await self.tasks.change_deadline(actor_name=actor.display_name, task=task,
                                                 new_deadline=changes["deadline"])
            if "assignee_email" in changes:
                assignee = self._user_by_email(session, changes["assignee_email"])
                await self.tasks.reassign(actor_name=actor.display_name, task=task,
                                          new_assignee=assignee)
            return f"✅ Đã cập nhật: {task['title']} ({task.get('task_id')})"

        raise ActionError("UNSUPPORTED", f"Không thực thi được intent {intent}.")

    # ---------- Query (không cần xác nhận) ----------

    async def handle_query(self, parsed: ParsedCommand, *, actor, session: Session) -> dict:
        if parsed.intent == "list_my_tasks":
            if not actor.user.notion_user_id:
                raise ActionError("CONFIG_MISSING",
                                  "Tài khoản của bạn chưa link Notion user ID. Nhờ admin cập nhật team.yaml.")
            pages = await self.tasks.gateway.query_open_tasks()
            mine = [self.tasks.gateway.parse_task(p) for p in pages
                    if actor.user.notion_user_id in (self.tasks.gateway.parse_task(p).get("assignee_ids") or [])]
            if not mine:
                return {"query_result": "Bạn không có task nào đang mở 🎉", "intent": "list_my_tasks",
                        "summary_lines": [], "warnings": [], "payload": {"intent": "noop"}}
            lines = [f"• {t.get('task_id') or '?'}: {t['title']} — {t.get('status')}, "
                     f"deadline {t.get('deadline')}" for t in mine[:15]]
            return {"query_result": f"Task đang mở của bạn ({len(mine)}):\n" + "\n".join(lines),
                    "intent": "list_my_tasks", "summary_lines": [], "warnings": [],
                    "payload": {"intent": "noop"}}

        raise ParseError("Mình mới hỗ trợ query dạng 'việc của mình có gì' — lệnh khác đang hoàn thiện.")

    @staticmethod
    def _user_by_email(session: Session, email: str | None):
        if not email:
            return None
        from sqlalchemy import select
        return session.scalar(select(User).where(User.email == email))
