"""ĐIỂM DUY NHẤT gọi Notion API: rate limit + retry + pagination (kế hoạch §7.6).

Chỉ cho phép method có sẵn ở đây — services không tự gọi HTTP Notion.
"""
import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
RETRY_BACKOFFS = [1.0, 5.0, 15.0]


class NotionError(Exception):
    def __init__(self, status: int, message: str, hint: str = ""):
        super().__init__(f"Notion {status}: {message} {hint}".strip())
        self.status = status


class NotionGateway:
    def __init__(self, max_rps: float = 2.5):
        s = get_settings()
        self._client = httpx.AsyncClient(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {s.notion_token}",
                "Notion-Version": s.notion_version,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._min_interval = 1.0 / max_rps
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, json_body: dict | None = None,
                       params: dict | None = None) -> dict:
        for attempt in range(len(RETRY_BACKOFFS) + 1):
            async with self._lock:  # token bucket đơn giản: cách đều các call
                wait = self._min_interval - (time.monotonic() - self._last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_call = time.monotonic()
            resp = await self._client.request(method, path, json=json_body, params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", RETRY_BACKOFFS[0]))
                log.warning("Notion 429 — chờ %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= 500 and attempt < len(RETRY_BACKOFFS):
                await asyncio.sleep(RETRY_BACKOFFS[attempt])
                continue
            break

        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message", resp.text)
                code = body.get("code", "")
            except Exception:
                msg, code = resp.text, ""
            hint = "— kiểm tra: DB đã share cho integration? NOTION_DATABASE_ID đúng?" \
                if resp.status_code in (401, 404) else ""
            raise NotionError(resp.status_code, f"{code} {msg}", hint)
        return resp.json() if resp.content else {}

    # ---------- Users ----------

    async def list_users(self) -> list[dict]:
        """GET /v1/users (endpoint danh sách user dùng GET + query params)."""
        out, cursor = [], None
        while True:
            params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = await self._request("GET", "/users", params=params)
            out.extend(data.get("results", []))
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    # ---------- Database query ----------

    async def query_open_tasks(self, *, deadline_on_or_before: str | None = None) -> list[dict]:
        """Task có status ∉ {Done, Cancelled}. deadline_on_or_before: YYYY-MM-DD."""
        flt: dict[str, Any] = {
            "and": [
                {"property": "Status", "status": {"does_not_equal": "Done"}},
                {"property": "Status", "status": {"does_not_equal": "Cancelled"}},
            ]
        }
        if deadline_on_or_before:
            flt["and"].append({"property": "Due date", "date": {"on_or_before": deadline_on_or_before}})
        return await self._query_database(flt)

    async def query_by_title(self, title_hint: str) -> list[dict]:
        return await self._query_database(
            {"property": "Task name", "title": {"contains": title_hint}}
        )

    async def query_by_task_id(self, task_id: str) -> dict | None:
        pages = await self._query_database(
            {"property": "Task ID (system)", "rich_text": {"equals": task_id}}
        )
        return pages[0] if pages else None

    async def _query_database(self, filter_obj: dict) -> list[dict]:
        out, cursor = [], None
        while True:
            body: dict[str, Any] = {"page_size": 100, "filter": filter_obj}
            if cursor:
                body["start_cursor"] = cursor
            data = await self._request("POST", f"/databases/{get_settings().notion_database_id}/query", body)
            out.extend(data.get("results", []))
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    # ---------- Pages ----------

    async def create_task_page(self, properties: dict) -> dict:
        body = {"parent": {"database_id": get_settings().notion_database_id}, "properties": properties}
        return await self._request("POST", "/pages", body)

    async def update_task_page(self, page_id: str, properties: dict, archived: bool = False) -> dict:
        body: dict[str, Any] = {"properties": properties, "archived": archived}
        return await self._request("PATCH", f"/pages/{page_id}", body)

    # ---------- Parse property -> dict gọn ----------

    @staticmethod
    def parse_task(page: dict) -> dict:
        """Page Notion -> dict gọn cho nghiệp vụ.
        Schema thực tế của user: Task name / Status / Assignee / Due date / Priority /
        Task type (multi_select) / Effort level / Description + property hệ thống thêm qua API."""
        p = page.get("properties", {})
        def rt(name):
            return "".join(t.get("plain_text", "") for t in p.get(name, {}).get("rich_text", []))
        def date_of(name):
            d = p.get(name, {}).get("date")
            return d.get("start") if d else None
        status_obj = p.get("Status", {}).get("status", {})
        people = [u.get("id") for u in p.get("Assignee", {}).get("people", [])]
        task_types = [o.get("name") for o in p.get("Task type", {}).get("multi_select", [])]
        return {
            "page_id": page.get("id"),
            "task_id": rt("Task ID (system)") or None,
            "title": "".join(t.get("plain_text", "") for t in p.get("Task name", {}).get("title", [])),
            "status": status_obj.get("name"),
            "assignee_ids": people,
            "deadline": date_of("Due date"),
            "start_date": date_of("Start Date"),
            "priority": (p.get("Priority", {}).get("select") or {}).get("name"),
            "task_type": ", ".join(task_types) if task_types else None,
            "effort": (p.get("Effort level", {}).get("select") or {}).get("name"),
            "description": rt("Description"),
            "url": page.get("url"),
            "last_edited_time": page.get("last_edited_time"),
        }

    async def close(self) -> None:
        await self._client.aclose()
