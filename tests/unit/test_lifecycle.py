"""Unit test lifecycle transitions — bảng §7.4 phải đúng 100%."""
import pytest

from app.models.task import ALLOWED_TRANSITIONS, validate_transition, TransitionError, is_overdue

VALID = [
    ("Not started", "In progress"), ("Not started", "Done"), ("Not started", "Blocked"), ("Not started", "Cancelled"),
    ("In progress", "In review"), ("In progress", "Done"), ("In progress", "Blocked"),
    ("In progress", "Cancelled"),
    ("In review", "In progress"), ("In review", "Done"), ("In review", "Blocked"),
    ("In review", "Cancelled"),
    ("Blocked", "Not started"), ("Blocked", "In progress"), ("Blocked", "Cancelled"),
]
INVALID = [
    ("Not started", "In review"),
    ("In progress", "Not started"),
    ("In review", "Not started"),
    ("Done", "In progress"), ("Done", "Not started"), ("Done", "Cancelled"),
    ("Blocked", "In review"), ("Blocked", "Done"),
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
