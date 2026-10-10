"""Template parser for meeting minutes and bulk task creation."""

import csv
import io
import re
from datetime import UTC, datetime
from typing import Any

from app.services.validator import try_parse_date_simple


class TemplateParseError(Exception):
    def __init__(self, message: str, line_num: int | None = None):
        super().__init__(message)
        self.message = message
        self.line_num = line_num


def parse_meeting_minutes(text: str) -> list[dict[str, Any]]:
    """Parse Action Items Tracker from meeting minutes format.

    Expected format:
    Action Items Tracker:
    - Task: [task name] | Assignee: [name(s)] | Deadline: [date] | Priority: [High/Medium/Low] | Status: [status]
    - Task: ...

    Or table format:
    | Task | Assignee | Deadline | Priority | Status |
    |---|---|---|---|---|
    | Task name | Minh, Cường | 30/09/2026 | High | Not started |
    """
    tasks = []

    # Find Action Items section
    lines = text.split("\n")
    in_action_items = False

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Detect start of action items
        if re.search(r"action items?\s*tracker", line_stripped, re.IGNORECASE):
            in_action_items = True
            continue

        if not in_action_items:
            continue

        # Stop at next major section
        if re.search(
            r"^(?:next steps?|meeting overview|key discussions?|interview|weekly)",
            line_stripped,
            re.IGNORECASE,
        ):
            break

        # Parse bullet format: - Task: X | Assignee: Y | Deadline: Z | Priority: P | Status: S
        bullet_match = re.match(r"^[-*]\s*(.+)$", line_stripped)
        if bullet_match:
            content = bullet_match.group(1)
            task = parse_bullet_task(content, i + 1)
            if task:
                tasks.append(task)
            continue

        # Parse table format
        if "|" in line_stripped and not line_stripped.startswith("|---"):
            task = parse_table_row(line_stripped, i + 1)
            if task:
                tasks.append(task)

    return tasks


def parse_bullet_task(content: str, line_num: int) -> dict[str, Any] | None:
    """Parse a single bullet task line."""
    # Expected: Task: [name] | Assignee: [names] | Deadline: [date] | Priority: [p] | Status: [s]
    fields = {}
    parts = content.split("|")

    for part in parts:
        part = part.strip()
        if ":" in part:
            key, value = part.split(":", 1)
            fields[key.strip().lower()] = value.strip()

    if not fields.get("task"):
        return None

    return build_task_dict(fields, line_num)


def parse_table_row(line: str, line_num: int) -> dict[str, Any] | None:
    """Parse a table row."""
    # Split by | and clean
    cells = [c.strip() for c in line.split("|")]
    cells = [c for c in cells if c]  # Remove empty

    if len(cells) < 2:
        return None

    # Assume header order: Task | Assignee | Deadline | Priority | Status
    # Or detect from header row
    fields = {
        "task": cells[0] if len(cells) > 0 else "",
        "assignee": cells[1] if len(cells) > 1 else "",
        "deadline": cells[2] if len(cells) > 2 else "",
        "priority": cells[3] if len(cells) > 3 else "Medium",
        "status": cells[4] if len(cells) > 4 else "Not started",
    }

    if not fields["task"] or fields["task"].lower() == "task":
        return None  # Skip header row

    return build_task_dict(fields, line_num)


def build_task_dict(fields: dict[str, str], line_num: int) -> dict[str, Any]:
    """Build standardized task dict from parsed fields."""

    today = datetime.now(UTC).date()

    # Parse deadline
    deadline = None
    if fields.get("deadline"):
        deadline = try_parse_date_simple(fields["deadline"], today)
        if not deadline:
            raise TemplateParseError(
                f"Không nhận diện được deadline: {fields['deadline']}", line_num
            )

    # Parse assignees (comma or "và" separated)
    assignees = []
    if fields.get("assignee"):
        assignee_str = fields["assignee"]
        assignees = [a.strip() for a in assignee_str.replace(" và ", ",").split(",") if a.strip()]

    # Validate priority
    priority = fields.get("priority", "Medium")
    if priority not in ("High", "Medium", "Low"):
        priority = "Medium"

    return {
        "title": fields["task"],
        "assignee_names_raw": assignees,
        "deadline": deadline,
        "priority": priority,
        "status": fields.get("status", "Not started"),
        "description": fields.get("description", ""),
        "task_type": fields.get("type", ""),
        "effort": fields.get("effort", ""),
        "start_date": fields.get("start_date", ""),
        "line_num": line_num,
    }


def parse_csv(text: str) -> list[dict[str, Any]]:
    """Parse CSV format task list.

    Expected columns: Task, Assignee, Deadline, Priority, Status, Description, Type, Effort, Start Date
    """
    tasks = []
    reader = csv.DictReader(io.StringIO(text))

    for i, row in enumerate(reader, start=1):
        # Normalize keys
        row = {k.strip().lower(): v.strip() for k, v in row.items() if v}

        if not row.get("task"):
            continue

        try:
            task = build_task_dict(row, i)
            tasks.append(task)
        except TemplateParseError:
            raise
        except ValueError as e:
            raise TemplateParseError(f"Lỗi dòng {i}: {e}", i)

    return tasks


def parse_template_input(text: str, format_hint: str | None = None) -> list[dict[str, Any]]:
    """Auto-detect format and parse.

    Args:
        text: Input text
        format_hint: 'meeting', 'csv', or None for auto-detect
    """
    if format_hint == "csv" or (
        format_hint is None and text.strip().startswith("Task,") or "Assignee," in text
    ):
        return parse_csv(text)
    return parse_meeting_minutes(text)
