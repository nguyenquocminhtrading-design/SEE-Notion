"""Unit test validator/resolver — deterministic, không LLM, không I/O."""
from datetime import date

import pytest

from app.models.preview import ActionError, ClarifyError
from app.models.parsed_command import ParsedCommand
from app.services.validator import build_preview_fields, resolve_assignee, validate_date


class FakeUser:
    def __init__(self, name, full=""):
        self.display_name = name
        self.full_name = full
        self.email = f"{name.lower()}@x.vn"
        self.notion_user_id = f"uuid-{name}"
        self.discord_id = "1"


USERS = [FakeUser("Minh", "Minh Nguyễn"), FakeUser("Lan", "Trần Thị Lan")]
AMBIGUOUS_USERS = USERS + [FakeUser("Minh Nguyễn", "Minh Nguyễn Vũ")]


def test_resolve_exact():
    assert resolve_assignee("Lan", USERS).display_name == "Lan"


def test_resolve_exact_no_diacritics():
    assert resolve_assignee("tran thi lan", USERS).display_name == "Lan"


def test_resolve_unique_partial_name():
    # "Minh" khớp exact display_name "Minh" — "Minh Nguyễn" normalized khác nên không mơ hồ
    assert resolve_assignee("Minh", USERS).display_name == "Minh"


def test_resolve_ambiguous():
    # Hai người normalized cùng tên "Minh Nguyen" -> bắt chọn
    with pytest.raises(ClarifyError) as e:
        resolve_assignee("Minh Nguyen", AMBIGUOUS_USERS)
    assert len(e.value.options) == 2


def test_resolve_unknown_suggests():
    with pytest.raises(ClarifyError):
        resolve_assignee("Zzzz", USERS)


def test_resolve_fuzzy():
    assert resolve_assignee("Lann", USERS).display_name == "Lan"


def test_validate_date_ok_and_fail():
    assert validate_date("2026-09-30", "Deadline") == "2026-09-30"
    with pytest.raises(ActionError):
        validate_date("2026-02-30", "Deadline")


def _parsed(**kw):
    base = dict(intent="create_task", title="Báo cáo", deadline="2026-09-30")
    base.update(kw)
    return ParsedCommand(**base)


def test_preview_defaults():
    fields, warnings = build_preview_fields(_parsed(), date(2026, 9, 24))
    assert fields["priority"] == "Medium"
    assert any("23:59" in w for w in warnings)


def test_preview_past_deadline_warns():
    fields, warnings = build_preview_fields(
        _parsed(deadline="2026-09-01"), date(2026, 9, 24))
    assert any("quá khứ" in w for w in warnings)


def test_preview_bad_priority_falls_back():
    fields, warnings = build_preview_fields(_parsed(priority="Khẩn"), date(2026, 9, 24))
    assert fields["priority"] == "Medium"
    assert warnings
