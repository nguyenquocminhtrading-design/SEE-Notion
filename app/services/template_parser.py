"""Template parser for meeting minutes, TSV action item tables, and bulk task creation."""

import csv
import io
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.validator import try_parse_date_simple
import zipfile
import xml.etree.ElementTree as ET


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from docx, formatting tables as TSV for parser."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx:
            if "word/document.xml" not in docx.namelist():
                return ""
            xml_content = docx.read("word/document.xml")
            
        tree = ET.ElementTree(ET.fromstring(xml_content))
        root = tree.getroot()
        
        # Word XML namespace
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        lines = []
        
        # Iterate over body elements (paragraphs w:p and tables w:tbl)
        body = root.find('w:body', ns)
        if body is None:
            return ""
            
        for elem in body:
            if elem.tag == f"{{{ns['w']}}}p":
                # Paragraph
                texts = elem.findall('.//w:t', ns)
                para_text = "".join(t.text for t in texts if t.text)
                if para_text.strip():
                    lines.append(para_text)
            elif elem.tag == f"{{{ns['w']}}}tbl":
                # Table
                for row in elem.findall('.//w:tr', ns):
                    row_data = []
                    for cell in row.findall('.//w:tc', ns):
                        # Extract all text in cell
                        texts = cell.findall('.//w:t', ns)
                        cell_text = "".join(t.text for t in texts if t.text)
                        # Clean cell text
                        cell_text = cell_text.replace('\n', ' ').replace('\t', ' ').strip()
                        row_data.append(cell_text)
                    if any(row_data):
                        lines.append("\t".join(row_data))
                lines.append("") # Empty line after table
                
        return "\n".join(lines)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Docx parsing error: {e}")
        return ""


class TemplateParseError(Exception):
    def __init__(self, message: str, line_num: int | None = None):
        super().__init__(message)
        self.message = message
        self.line_num = line_num


def parse_pic_names(raw: str) -> list[str]:
    """Parse PIC (Owner) string into clean assignee names list.

    Examples:
    - "Minh / [PIC bổ sung]" -> ["Minh"]
    - "Ánh → Cường" -> ["Ánh", "Cường"]
    - "Hân (Minh)" -> ["Hân", "Minh"]
    - "[PIC]" -> []
    """
    if not raw or not raw.strip():
        return []

    # Remove placeholders like [PIC bổ sung], [PIC], [DD/MM]
    clean = re.sub(r"\[.*?\]", "", raw)
    # Convert delimiters →, /, (, ) to comma
    clean = clean.replace("→", ",").replace("/", ",").replace("(", ",").replace(")", ",")
    clean = clean.replace(" và ", ",")

    names = [n.strip() for n in clean.split(",") if n.strip()]
    return names


def parse_smart_deadline_and_status(raw: str, today: Any) -> tuple[str | None, str]:
    """Parse deadline string and status intelligently.

    Examples:
    - "Xong 6/10" -> ("2026-10-06", "Done")
    - "Done" / "done" -> (today.isoformat(), "Done")
    - "2 tuần" -> (today + 14 days, "Not started")
    - "[DD/MM]" -> (None, "Not started")
    """
    if not raw:
        return None, "Not started"

    raw_clean = raw.strip()
    status = "Not started"

    # Check for Done / Xong
    is_done = False
    if re.search(r"\b(done|xong)\b", raw_clean, re.IGNORECASE):
        is_done = True
        status = "Done"

    # Clean words "Xong", "Done" to extract date
    date_text = re.sub(r"\b(done|xong)\b", "", raw_clean, flags=re.IGNORECASE).strip()

    # Check "N tuần"
    week_match = re.search(r"(\d+)\s*tuần", raw_clean, re.IGNORECASE)
    if week_match:
        weeks = int(week_match.group(1))
        return (today + timedelta(days=weeks * 7)).isoformat(), status

    # Check "N ngày"
    day_match = re.search(r"(\d+)\s*ngày", raw_clean, re.IGNORECASE)
    if day_match:
        days = int(day_match.group(1))
        return (today + timedelta(days=days)).isoformat(), status

    # Extract DD/MM/YYYY or DD/MM pattern
    date_match = re.search(r"(\d{1,2}/\d{1,2}(?:/\d{4})?)", raw_clean)
    if date_match:
        parsed_date = try_parse_date_simple(date_match.group(1), today)
        if parsed_date:
            return parsed_date, status

    if is_done:
        return today.isoformat(), "Done"

    return None, status


def parse_tsv_action_items(text: str) -> list[dict[str, Any]]:
    """Parse TSV / Tab-separated or space-separated Action Items table layout.

    Example columns:
    No. | Action Item / Specific Task | Expected Deliverable | PIC (Owner) | Deadline
    """
    lines = text.strip().split("\n")
    if not lines:
        return []

    tasks = []
    today = datetime.now(UTC).date()

    for i, line in enumerate(lines, start=1):
        line_str = line.strip()
        if not line_str:
            continue

        # Split by tab if present, else by 2 or more spaces
        if "\t" in line_str:
            parts = [p.strip() for p in line_str.split("\t")]
            if not any(parts):
                continue
        else:
            parts = [p.strip() for p in re.split(r"\s{2,}", line_str) if p.strip()]

        if len(parts) < 3:
            continue

        # Skip header line
        header_check = " ".join(parts).lower()
        if (
            "action item" in header_check
            or "specific task" in header_check
            or "pic (owner)" in header_check
            or "expected deliverable" in header_check
            or "no." in header_check
        ):
            continue

        # Remove leading row number or empty first column if present (e.g. "1", "1.", "1)")
        if re.match(r"^\d+[\.\)]?$", parts[0]) or parts[0] == "":
            parts = parts[1:]

        if not parts:
            continue

        title = parts[0]
        
        if len(parts) >= 4:
            description = parts[1]
            pic_raw = parts[2]
            deadline_raw = parts[3]
        elif len(parts) == 3:
            description = ""
            pic_raw = parts[1]
            deadline_raw = parts[2]
        elif len(parts) == 2:
            description = ""
            pic_raw = parts[1]
            deadline_raw = ""
        else:
            description = ""
            pic_raw = ""
            deadline_raw = ""

        # If 2 parts and part 2 looks like a status/deadline rather than PIC
        if len(parts) == 2 and ("xong" in pic_raw.lower() or "done" in pic_raw.lower() or "/" in pic_raw):
            deadline_raw = pic_raw
            pic_raw = ""

        # Parse PIC (Owner)
        assignees = parse_pic_names(pic_raw)

        # Parse Deadline and Status
        deadline, status = parse_smart_deadline_and_status(deadline_raw, today)

        # Default deadline if missing
        if not deadline:
            if status == "Done":
                deadline = today.isoformat()
            else:
                deadline = (today + timedelta(days=7)).isoformat()

        tasks.append(
            {
                "title": title,
                "description": description,
                "assignee_names_raw": assignees,
                "deadline": deadline,
                "priority": "Medium",
                "status": status,
                "task_type": "",
                "effort": "",
                "start_date": "",
                "line_num": i,
            }
        )

    return tasks


def parse_meeting_minutes(text: str) -> list[dict[str, Any]]:
    """Parse Action Items Tracker from meeting minutes format."""
    tasks = []
    lines = text.split("\n")
    in_action_items = False

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        if re.search(r"action items?\s*tracker", line_stripped, re.IGNORECASE):
            in_action_items = True
            continue

        if not in_action_items:
            continue

        if re.search(
            r"^(?:next steps?|meeting overview|key discussions?|interview|weekly)",
            line_stripped,
            re.IGNORECASE,
        ):
            break

        bullet_match = re.match(r"^[-*]\s*(.+)$", line_stripped)
        if bullet_match:
            content = bullet_match.group(1)
            task = parse_bullet_task(content, i + 1)
            if task:
                tasks.append(task)
            continue

        if "|" in line_stripped and not line_stripped.startswith("|---"):
            task = parse_table_row(line_stripped, i + 1)
            if task:
                tasks.append(task)

    return tasks


def parse_bullet_task(content: str, line_num: int) -> dict[str, Any] | None:
    """Parse a single bullet task line."""
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
    cells = [c.strip() for c in line.split("|")]
    cells = [c for c in cells if c]

    if len(cells) < 2:
        return None

    fields = {
        "task": cells[0] if len(cells) > 0 else "",
        "assignee": cells[1] if len(cells) > 1 else "",
        "deadline": cells[2] if len(cells) > 2 else "",
        "priority": cells[3] if len(cells) > 3 else "Medium",
        "status": cells[4] if len(cells) > 4 else "Not started",
    }

    if not fields["task"] or fields["task"].lower() == "task":
        return None

    return build_task_dict(fields, line_num)


def build_task_dict(fields: dict[str, str], line_num: int) -> dict[str, Any]:
    """Build standardized task dict from parsed fields."""
    today = datetime.now(UTC).date()

    deadline = None
    if fields.get("deadline"):
        deadline = try_parse_date_simple(fields["deadline"], today)
        if not deadline:
            raise TemplateParseError(
                f"Không nhận diện được deadline: {fields['deadline']}", line_num
            )

    assignees = []
    if fields.get("assignee"):
        assignee_str = fields["assignee"]
        assignees = parse_pic_names(assignee_str)

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
    """Parse CSV format task list."""
    tasks = []
    reader = csv.DictReader(io.StringIO(text))

    for i, row in enumerate(reader, start=1):
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
    """Auto-detect format and parse."""
    if format_hint == "csv" or (
        format_hint is None and ("Task," in text or "Assignee," in text)
    ):
        return parse_csv(text)

    # Try TSV / Action Item table format
    tsv_tasks = parse_tsv_action_items(text)
    if tsv_tasks:
        return tsv_tasks

    return parse_meeting_minutes(text)
