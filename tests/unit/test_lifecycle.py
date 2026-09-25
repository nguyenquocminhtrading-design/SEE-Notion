"""Unit test lifecycle transitions — bảng §7.4 phải đúng 100%."""
import pytest

from app.models.task import ALLOWED_TRANSITIONS, validate_transition, TransitionError, is_overdue

VALID = [
    ("Pending", "In Progress"), ("Pending", "Done"), ("Pending", "Blocked"), ("Pending", "Cancelled"),
    ("In Progress", "In Review"), ("In Progress", "Done"), ("In Progress", "Blocked"),
    ("In Progress", "Cancelled"),
    ("In Review", "In Progress"), ("In Review", "Done"), ("In Review", "Blocked"),
    ("In Review", "Cancelled"),
    ("Blocked", "Pending"), ("Blocked", "In Progress"), ("Blocked", "Cancelled"),
]
INVALID = [
    ("Pending", "In Review"),
    ("In Progress", "Pending"),
    ("In Review", "Pending"),
    ("Done", "In Progress"), ("Done", "Pending"), ("Done", "Cancelled"),
    ("Blocked", "In Review"), ("Blocked", "Done"),
    ("Cancelled", "Anything"),
]


@pytest.mark.parametrize("frm,to", VALID)
def test_valid_transitions(frm, to):
    validate_transition(frm, to)  # không raise


@pytest.mark.parametrize("frm,to", INVALID)
def test_invalid_transitions(frm, to):
    with pytest.raises(TransitionError):
        validate_transition(frm, to)


def test_done_is_terminal():
    assert ALLOWED_TRANSITIONS["Done"] == set()
    assert ALLOWED_TRANSITIONS["Cancelled"] == set()


def test_overdue():
    assert is_overdue("2026-09-23", "2026-09-24")
    assert not is_overdue("2026-09-24", "2026-09-24")  # đúng hạn chưa overdue
    assert not is_overdue("2026-09-30", "2026-09-24")
