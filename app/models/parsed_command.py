"""JSON schema đầu ra của LLM (kế hoạch §9.1) — Pydantic ép chặt."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Intent = Literal[
    "create_task", "update_task", "assign_task", "change_deadline",
    "complete_task", "archive_task", "query_tasks", "list_my_tasks",
    "get_task_status", "unknown",
]

Status = Literal["Not started", "In progress", "In review", "Done", "Blocked", "Cancelled"]
Effort = Literal["High", "Medium", "Low"]

JSON_SCHEMA_HINT = """{
  "intent": "create_task|update_task|assign_task|change_deadline|complete_task|archive_task|query_tasks|list_my_tasks|get_task_status|unknown",
  "confidence": 0.0,
  "task_ref": {"task_id": "TSK-0001 | null", "title_hint": "string | null"},
  "title": "string | null",
  "description": "string | null",
  "assignee_names_raw": ["tên người 1", "tên người 2"],
  "start_date": "YYYY-MM-DD | null",
  "deadline": "YYYY-MM-DD | null",
  "deadline_time": "HH:MM | null",
  "priority": "High|Medium|Low|null",
  "task_type": "Feature request|Polish|Bug|Documentation|Meeting|Other|null",
  "effort": "High|Medium|Low|null",
  "status": "Not started|In progress|In review|Done|Blocked|Cancelled|null",
  "missing_fields": ["..."],
  "ambiguous_fields": [],
  "user_language": "vi|en"
}"""


class TaskRef(BaseModel):
    task_id: Optional[str] = None
    title_hint: Optional[str] = None


class ParsedCommand(BaseModel):
    intent: Intent = "unknown"
    confidence: float = 0.0
    task_ref: TaskRef = Field(default_factory=TaskRef)
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_name_raw: Optional[str] = None          # tương thích đơn giản
    assignee_names_raw: list[str] = Field(default_factory=list)  # nhiều người
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    deadline_time: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    effort: Optional[str] = None
    status: Optional[Status] = None
    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    user_language: str = "vi"

    model_config = {"extra": "ignore"}  # field lạ từ LLM -> loại bỏ
