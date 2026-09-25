"""Unit test reminder rules + dedupe logic (kế hoạch §10)."""
from datetime import date

import pytest

from app.services.reminder_engine import compute_due_rules, compute_reminder_window


def _offsets():
    return {"pre3": -3, "pre1": -1, "due": 0, "over1": 1, "over3": 4, "over6": 7}


def test_before_deadline():
    # deadline 30/09, hôm nay 27/09 -> pre3
    assert compute_due_rules("2026-09-30", "2026-09-27", _offsets()) == ["pre3"]


def test_due_day():
    assert compute_due_rules("2026-09-30", "2026-09-30", _offsets()) == ["due"]


def test_overdue1():
    assert compute_due_rules("2026-09-30", "2026-10-01", _offsets()) == ["over1"]


def test_overdue_repeat_covers():
    # Quá hạn 9 ngày: rule over6 (offset 7) phải phát lại (loop lắcoverN)
    due = compute_due_rules("2026-09-21", "2026-09-30", _offsets())
    assert "over6" in due


def test_nothing_due():
    # 28/09: gap = -2, không khớp rule nào (pre1 là gap -1)
    assert compute_due_rules("2026-09-30", "2026-09-28", _offsets()) == []
    # 29/09: gap = -1 -> đúng lúc phát pre1
    assert compute_due_rules("2026-09-30", "2026-09-29", _offsets()) == ["pre1"]


def test_window():
    past, future = compute_reminder_window({"scan_window_past_days": 30,
                                            "scan_window_future_days": 4}, date(2026, 9, 24))
    assert past == "2026-08-25"
    assert future == "2026-09-28"
