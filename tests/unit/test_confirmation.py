"""Unit test ConfirmationService — nonce 1-lần, TTL, đúng chủ."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.confirmation import ConfirmationService, NonceError


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()


def test_create_and_redeem(session):
    svc = ConfirmationService()
    nonce = svc.create(session, discord_user="1", channel_id="c",
                       payload={"a": 1}, summary_lines=["X"], warnings=[])
    payload = svc.redeem(session, nonce, "1")
    assert payload == {"a": 1}


def test_redeem_twice_fails(session):
    svc = ConfirmationService()
    nonce = svc.create(session, discord_user="1", channel_id="c",
                       payload={}, summary_lines=[], warnings=[])
    svc.redeem(session, nonce, "1")
    with pytest.raises(NonceError):
        svc.redeem(session, nonce, "1")


def test_redeem_by_other_user_fails(session):
    svc = ConfirmationService()
    nonce = svc.create(session, discord_user="1", channel_id="c",
                       payload={}, summary_lines=[], warnings=[])
    with pytest.raises(NonceError):
        svc.redeem(session, nonce, "999")


def test_expired_fails(session):
    from app.db.models import PendingAction
    svc = ConfirmationService()
    nonce = svc.create(session, discord_user="1", channel_id="c",
                       payload={}, summary_lines=[], warnings=[])
    pa = session.get(PendingAction, nonce)
    pa.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    session.commit()
    with pytest.raises(NonceError):
        svc.redeem(session, nonce, "1")
