"""Quy tắc recipient của reminder phải hoạt động theo từng assignee."""
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base, NotificationLog
from app.services.notification_preferences import accepts_channel
from app.services.reminder_engine import ReminderEngine


def _user(name, email, notion_id, *, email_enabled=True):
    return SimpleNamespace(
        display_name=name,
        email=email,
        notion_user_id=notion_id,
        prefs_json='{ "email": %s }' % str(email_enabled).lower(),
    )


def test_finds_every_assignee_not_just_the_first():
    db = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    minh = _user("Minh", "minh@example.com", "notion-minh")
    cuong = _user("Cường", "cuong@example.com", "notion-cuong")
    engine = ReminderEngine(None, None, users_provider=lambda: [minh, cuong])

    recipients = engine._find_assignee_users({"assignee_ids": ["notion-minh", "notion-cuong"]})

    assert recipients == [minh, cuong]


def test_dedupe_allows_one_log_per_recipient():
    db = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db)
    session = Session(db)

    def add(recipient):
        session.add(NotificationLog(task_id="TSK-0001", rule_key="due", due_date="2026-10-16",
                                    recipient=recipient, channel="email"))
        session.commit()

    add("minh@example.com")
    add("cuong@example.com")
    session.add(NotificationLog(task_id="TSK-0001", rule_key="due", due_date="2026-10-16",
                                recipient="minh@example.com", channel="email"))
    try:
        session.commit()
        raised = False
    except IntegrityError:
        session.rollback()
        raised = True

    assert raised


def test_respects_each_users_email_preference():
    assert accepts_channel(_user("Minh", "minh@example.com", "minh"), "email")
    assert not accepts_channel(_user("Cường", "cuong@example.com", "cuong", email_enabled=False), "email")
