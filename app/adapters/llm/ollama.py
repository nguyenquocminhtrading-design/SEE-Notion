"""Ollama (local) — dùng khi muốn chạy model trên máy, không tốn phí API.

Khuyến nghị model hỗ trợ JSON + tiếng Việt tốt: qwen2.5 / qwen3.
Chạy: `ollama pull qwen2.5:7b` rồi đặt LLM_PROVIDER=ollama.
"""
import logging

import httpx

from app.adapters.llm.base import LLMClient, LLMError
from app.config import get_settings

log = logging.getLogger(__name__)
TIMEOUT = 120.0  # local model có thể chậm tùy máy


class OllamaClient(LLMClient):
    def __init__(self):
        s = get_settings()
        self._model = s.llm_model  # ví dụ "qwen2.5:7b"
        self._base = s.ollama_base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=TIMEOUT)

    async def complete_json(self, system: str, user: str) -> dict:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",  # ép Ollama xuất JSON
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            resp = await self._client.post(f"{self._base}/api/chat", json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"Không kết nối được Ollama ({self._base}): {e}") from e
        if resp.status_code >= 400:
            raise LLMError(f"Ollama trả lỗi {resp.status_code}: {resp.text[:300]}")
        try:
            content = resp.json()["message"]["content"]
        except (KeyError, ValueError) as e:
            raise LLMError(f"Phản hồi Ollama sai cấu trúc: {e}") from e
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"Ollama không trả JSON hợp lệ: {content[:200]}") from e

    async def close(self) -> None:
        await self._client.aclose()
