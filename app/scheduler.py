"""APScheduler — 1 cron job quét reminder (mô hình scan, kế hoạch §10.1)."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

log = logging.getLogger(__name__)


def make_scheduler(container) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=get_settings().tz_config)
    interval_seconds = 300  # 5 phút

    async def reminder_tick():
        from app.db.session import get_session
        session = get_session()
        try:
            await container.reminder.scan_and_dispatch(session, _today())
        except Exception:
            log.exception("Reminder tick fail — sẽ thử lại tick sau")
        finally:
            session.close()

    def _today():
        from datetime import datetime
        return datetime.now(get_settings().business_tz).date()

    scheduler.add_job(reminder_tick, "interval", seconds=interval_seconds,
                      max_instances=1, coalesce=True, id="reminder_scan",
                      next_run_time=None)  # tick đầu sau interval, không chạy ngay khi boot
    return scheduler
