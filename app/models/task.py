"""Domain task: statuses, lifecycle transitions, validation thuần (không I/O).

Status đặt tên khớp format bảng task người dùng quen (Not started / In progress / Done).
"""

# Không phụ thuộc thứ tự phần tử — chỉ là tập hợp
ALL_STATUSES = {"Not started", "In progress", "In review", "Done", "Blocked", "Cancelled"}
CLOSED_STATUSES = {"Done", "Cancelled"}
PRIORITIES = {"High", "Medium", "Low"}
TASK_TYPES = {"Feature request", "Polish", "Bug", "Documentation", "Meeting", "Other"}
EFFORT_LEVELS = {"Small", "Medium", "Large"}

# Bảng chuyển trạng thái. from -> tập hợp các to hợp lệ
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "Not started": {"In progress", "Done", "Blocked", "Cancelled"},
    "In progress": {"In review", "Done", "Blocked", "Cancelled"},
    "In review":   {"In progress", "Done", "Blocked", "Cancelled"},
    "Done":        set(),
    "Blocked":     {"Not started", "In progress", "Cancelled"},
    "Cancelled":   set(),
}

# Tạo trong Notion Status property ĐÚNG các option này (kể cả màu nếu muốn đẹp)
NOTION_STATUS_OPTIONS = ["Not started", "In progress", "In review", "Done", "Blocked", "Cancelled"]
NOTION_STATUS_GROUPS = {
    "To-do": ["Not started", "Blocked"],
    "In Progress": ["In progress", "In review"],
    "Complete": ["Done", "Cancelled"],
}


class TransitionError(ValueError):
    pass


def validate_transition(current: str, target: str) -> None:
    if target not in ALL_STATUSES:
        raise TransitionError(f"Trạng thái không hợp lệ: {target!r}")
    if current not in ALLOWED_TRANSITIONS:
        raise TransitionError(f"Trạng thái hiện tại không hợp lệ: {current!r}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise TransitionError(
            f"Không thể chuyển {current} → {target}. "
            f"Các trạng thái hợp lệ từ {current}: {sorted(ALLOWED_TRANSITIONS[current]) or '(không có — task đã đóng)'}"
        )


def is_overdue(deadline: str, today: str) -> bool:
    """deadline/today dạng YYYY-MM-DD. Overdue là trạng thái TÍNH TOÁN, không phải status."""
    return deadline < today  # so sánh ISO date = so sánh thứ tự thời gian


def validate_priority(p: str | None) -> str:
    if p is None:
        return "Medium"
    if p not in PRIORITIES:
        raise ValueError(f"Priority phải là một trong {sorted(PRIORITIES)}, nhận được: {p!r}")
    return p


def validate_enum(value: str | None, allowed: set[str], field_label: str, default: str | None = None) -> str | None:
    if value is None:
        return default
    if value not in allowed:
        raise ValueError(f"{field_label} phải là một trong {sorted(allowed)}, nhận được: {value!r}")
    return value
