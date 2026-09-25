"""Validator/Resolver: ParsedCommand -> payload sẵn sàng thực thi hoặc câu hỏi làm rõ.

100% deterministic (không LLM): validate ngày, resolve assignee, kiểm tra lifecycle/quyền.
"""
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta

from app.models.preview import ActionError, ClarifyError
from app.models.task import validate_priority
from app.models.parsed_command import ParsedCommand

log = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85  # 0-100 (rapidfuzz-style scoring qua difflib)

# Regex nhận diện ngày chuẩn — không cần gọi LLM
_RE_DDMMYYYY = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})$')
_RE_DDMM     = re.compile(r'^(\d{1,2})/(\d{1,2})$')
_RE_ISO      = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def try_parse_date_simple(text: str, today: date) -> str | None:
    """Parse ngày nhanh không cần LLM.
    Nhận: DD/MM/YYYY | DD/MM (chọn năm tương lai gần nhất) | YYYY-MM-DD.
    Trả về: YYYY-MM-DD hoặc None nếu không nhận ra."""
    text = text.strip()
    m = _RE_ISO.match(text)
    if m:
        return text
    m = _RE_DDMMYYYY.match(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = _RE_DDMM.match(text)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        for y in [today.year, today.year + 1]:
            try:
                candidate = date(y, mo, d)
                if candidate >= today:
                    return candidate.isoformat()
            except ValueError:
                continue
        return None
    return None


def _norm(s: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase để so khớp tên."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.strip().lower())
        if unicodedata.category(c) != "Mn"
    )


def validate_date(s: str | None, field: str) -> str | None:
    if s is None:
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise ActionError("VALIDATION_FAILED", f"{field} không hợp lệ: {s!r}. Định dạng YYYY-MM-DD.") from e
    return s


def resolve_assignee(name_raw: str, users: list) -> object:
    """users: list[app.db.models.User]. Trả về User hoặc raise ClarifyError."""
    if not name_raw or not name_raw.strip():
        raise ClarifyError("MISSING_ASSIGNEE", "Không rõ assignee. Bạn muốn giao cho ai?")
    norm = _norm(name_raw)
    exact = [u for u in users if _norm(u.display_name) == norm or _norm(u.full_name or "") == norm]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ClarifyError(
            "AMBIGUOUS_ASSIGNEE",
            f"Có {len(exact)} người tên {name_raw!r}. Bạn meant ai?",
            options=[u.display_name for u in exact],
        )
    # Fuzzy
    from difflib import SequenceMatcher

    def score(u) -> float:
        return max(
            SequenceMatcher(None, norm, _norm(u.display_name)).ratio() * 100,
            SequenceMatcher(None, norm, _norm(u.full_name or "")).ratio() * 100,
        )
    ranked = sorted(users, key=score, reverse=True)
    best, best_score = ranked[0], score(ranked[0])
    if best_score >= FUZZY_THRESHOLD:
        return best
    raise ClarifyError(
        "UNKNOWN_ASSIGNEE",
        f"Không tìm thấy ai tên {name_raw!r} trong team.",
        options=[u.display_name for u in ranked[:3]],
    )


def build_preview_fields(parsed: ParsedCommand, today: date) -> tuple[dict, list[str]]:
    """Trả về (fields đã validate, warnings). Raise ActionError nếu sai dữ liệu."""
    warnings: list[str] = []
    deadline = validate_date(parsed.deadline, "Deadline")
    start_date = validate_date(parsed.start_date, "Start date")
    try:
        priority = validate_priority(parsed.priority)
    except ValueError:
        priority = "Medium"
        warnings.append(f"Priority {parsed.priority!r} không hợp lệ → dùng Medium")
    if parsed.deadline_time is None:
        warnings.append("Không rõ giờ cụ thể — mặc định hết hạn 23:59 (ICT)")
    if deadline and deadline < today.isoformat() and parsed.intent == "create_task":
        warnings.append(f"Deadline {deadline} là ngày trong quá khứ so với hôm nay {today.isoformat()} — bạn chắc chứ?")
    fields = {
        "title": parsed.title,
        "description": parsed.description,
        "assignee_name_raw": parsed.assignee_name_raw,
        "start_date": parsed.start_date,
        "deadline": deadline,
        "priority": priority,
        "task_type": parsed.task_type,
        "effort": parsed.effort,
        "status": parsed.status,
        "task_ref": parsed.task_ref.model_dump(),
        "intent": parsed.intent,
    }
    return fields, warnings
