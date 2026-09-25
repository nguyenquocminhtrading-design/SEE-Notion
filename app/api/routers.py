"""FastAPI routers — health + REST cơ bản (bot dùng service layer trực tiếp)."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings

log = logging.getLogger(__name__)


def require_token(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {get_settings().app_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Sai token")


def _container():
    from app.main import container
    if container is None:
        raise HTTPException(status_code=503, detail="Ứng dụng đang khởi động")
    return container


def _today():
    return datetime.now(get_settings().business_tz).date()


def health_router() -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz():
        from app.db.session import get_session
        from app.adapters.notion_gateway import NotionError
        checks = {"db": "ok", "notion": "ok"}
        try:
            session = get_session()
            session.execute(text("SELECT 1"))
            session.close()
        except Exception as e:
            checks["db"] = f"error: {e}"
        try:
            await _container().gateway.list_users()
        except NotionError as e:
            checks["notion"] = f"error: {e}"
        except Exception as e:
            checks["notion"] = f"error: {e}"
        ok = all(v == "ok" for v in checks.values())
        body = {"status": "ok" if ok else "degraded", "checks": checks}
        return JSONResponse(status_code=200 if ok else 503, content=body)

    return router


def api_router(container) -> APIRouter:
    """REST cho web app sau này + tích hợp ngoài. Auth: Bearer APP_TOKEN."""
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])

    @router.get("/tasks")
    async def list_tasks(status: str | None = None, overdue: bool = False,
                         due_within_days: int | None = None):
        from app.adapters.notion_gateway import NotionError
        try:
            pages = await container.gateway.query_open_tasks()
        except NotionError as e:
            raise HTTPException(status_code=502, detail=f"Notion unavailable: {e}")
        today = _today().isoformat()
        tasks = [container.gateway.parse_task(p) for p in pages]
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        if overdue:
            tasks = [t for t in tasks if t.get("deadline") and t["deadline"] < today]
        if due_within_days is not None:
            limit = (_today() + timedelta(days=due_within_days)).isoformat()
            tasks = [t for t in tasks if t.get("deadline") and t["deadline"] <= limit]
        return {"count": len(tasks), "tasks": tasks}

    @router.get("/audit")
    async def audit(task_ref: str | None = None, limit: int = 50):
        from app.db.models import AuditLog
        from app.db.session import get_session
        from sqlalchemy import select
        session = get_session()
        try:
            q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
            if task_ref:
                q = q.where(AuditLog.task_ref == task_ref)
            rows = session.scalars(q).all()
            return [{"ts": r.ts, "actor": r.actor, "action": r.action,
                     "task_ref": r.task_ref, "diff": r.diff_json, "result": r.result}
                    for r in rows]
        finally:
            session.close()

    return router
