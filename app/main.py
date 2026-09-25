"""SEE Notion — entrypoint. 1 process: FastAPI + Discord bot + APScheduler.

Chạy: python -m app.main
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.logging_conf import setup_logging

log = logging.getLogger(__name__)

container = None  # set trong lifespan — routers đọc qua main.container


@asynccontextmanager
async def lifespan(app: FastAPI):
    global container
    setup_logging(get_settings().log_level)

    from app.container import build_container
    container = build_container()
    app.state.container = container
    log.info("Container sẵn sàng (LLM=%s, email=%s)", get_settings().llm_provider,
             get_settings().email_backend)
    await container.sync_notion_users()

    # REST API
    from app.api.routers import api_router, health_router
    app.include_router(api_router(container))

    # Scheduler reminder
    from app.scheduler import make_scheduler
    scheduler = make_scheduler(container)
    scheduler.start()

    # Discord bot (cùng event loop)
    bot_task = None
    if get_settings().discord_bot_token:
        from app.adapters.discord_client import run_bot
        bot = run_bot(container)
        bot_task = asyncio.create_task(bot.start(get_settings().discord_bot_token))
    else:
        log.warning("Chưa có DISCORD_BOT_TOKEN — chỉ chạy API + scheduler")

    yield

    if bot_task:
        bot_task.cancel()
    scheduler.shutdown(wait=False)
    log.info("Đã dừng sạch")


app = FastAPI(title="SEE Notion", version="0.1.0", lifespan=lifespan)

from app.api.routers import health_router  # noqa: E402
app.include_router(health_router())


@app.get("/")
async def root():
    return {"service": "SEE Notion", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
