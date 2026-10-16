from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            # sqlite cần check_same_thread=False vì FastAPI + bot chạy nhiều thread/task
            _engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(url)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal()


def init_db() -> None:
    from pathlib import Path
    get_engine()
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_engine)
    _migrate_notification_log_dedupe()


def _migrate_notification_log_dedupe() -> None:
    """SQLite cannot alter a UNIQUE constraint in place.

    Older installs deduplicated by task/rule/channel only, which prevented a
    reminder for the second assignee. Rebuild this small operational log table
    once so the recipient also participates in the unique key.
    """
    if not str(get_settings().database_url).startswith("sqlite:///"):
        return
    with _engine.begin() as connection:
        schema = connection.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='notification_log'"
        )).scalar() or ""
        normalized_schema = " ".join(schema.replace('"', '').split())
        if "UNIQUE (task_id, rule_key, due_date, recipient, channel)" in normalized_schema:
            return
        # The named constraint is retained verbatim in SQLite's table DDL.
        if "CONSTRAINT uq_dedupe UNIQUE (task_id, rule_key, due_date, channel)" not in normalized_schema:
            return
        connection.execute(text("ALTER TABLE notification_log RENAME TO notification_log_legacy"))
        Base.metadata.tables["notification_log"].create(connection)
        connection.execute(text(
            "INSERT INTO notification_log "
            "(id, task_id, rule_key, due_date, recipient, channel, status, attempts, error, created_at, delivered_at) "
            "SELECT id, task_id, rule_key, due_date, recipient, channel, status, attempts, error, created_at, delivered_at "
            "FROM notification_log_legacy"
        ))
        connection.execute(text("DROP TABLE notification_log_legacy"))
