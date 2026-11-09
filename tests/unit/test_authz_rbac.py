"""Tests for authz, link_discord_account, and RBAC can_edit_task."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, User
from app.services.authz import Actor, can_edit_task, link_discord_account, NotAuthorized


@pytest.fixture
def test_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test_authz.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed admin and member
        admin = User(
            display_name="AdminUser",
            full_name="Admin User Full",
            email="admin@vgu.edu.vn",
            discord_id="999999",
            notion_user_id="notion-admin-id",
            role="admin",
        )
        member = User(
            display_name="MemberUser",
            full_name="Member User Full",
            email="member@vgu.edu.vn",
            discord_id="",
            notion_user_id="notion-member-id",
            role="member",
        )
        other_member = User(
            display_name="OtherUser",
            full_name="Other User Full",
            email="other@vgu.edu.vn",
            discord_id="888888",
            notion_user_id="notion-other-id",
            role="member",
        )
        session.add_all([admin, member, other_member])
        session.commit()
        yield session


def test_can_edit_task_admin(test_session):
    admin = test_session.query(User).filter_by(role="admin").first()
    actor = Actor(admin)
    task = {"assignee_ids": ["notion-member-id"], "creator_id": "notion-other-id"}
    assert can_edit_task(actor, task) is True


def test_can_edit_task_member_assigned(test_session):
    member = test_session.query(User).filter_by(display_name="MemberUser").first()
    actor = Actor(member)
    task = {"assignee_ids": ["notion-member-id"], "creator_id": "notion-other-id"}
    assert can_edit_task(actor, task) is True


def test_can_edit_task_member_creator(test_session):
    member = test_session.query(User).filter_by(display_name="MemberUser").first()
    actor = Actor(member)
    task = {"assignee_ids": ["notion-other-id"], "creator_id": "notion-member-id"}
    assert can_edit_task(actor, task) is True


def test_can_edit_task_member_unauthorized(test_session):
    member = test_session.query(User).filter_by(display_name="MemberUser").first()
    actor = Actor(member)
    task = {"assignee_ids": ["notion-other-id"], "creator_id": "notion-other-id"}
    assert can_edit_task(actor, task) is False


def test_link_discord_account_success(test_session):
    updated = link_discord_account(test_session, "member@vgu.edu.vn", "123456789")
    assert updated.discord_id == "123456789"
    refreshed = test_session.query(User).filter_by(email="member@vgu.edu.vn").first()
    assert refreshed.discord_id == "123456789"


def test_link_discord_account_duplicate_discord_id(test_session):
    with pytest.raises(ValueError, match="đã được liên kết"):
        link_discord_account(test_session, "member@vgu.edu.vn", "888888")


def test_link_discord_account_email_not_found(test_session):
    with pytest.raises(ValueError, match="Không tìm thấy người dùng"):
        link_discord_account(test_session, "nonexistent@vgu.edu.vn", "777777")
