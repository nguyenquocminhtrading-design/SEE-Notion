"""GLM (Z.ai) — OpenAI-compatible chat completions với JSON mode."""
import logging

import httpx

from app.adapters.llm.base import LLMClient, LLMError
from app.config import get_settings

log = logging.getLogger(__name__)
GLM_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
TIMEOUT = 25.0


class GLMClient(LLMClient):
    def __init__(self):
        s = get_settings()
        self._model = s.llm_model
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {s.llm_api_key}"},
            timeout=TIMEOUT,
        )

    async def complete_json(self, system: str, user: str) -> dict:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        try:
            resp = await self._client.post(GLM_ENDPOINT, json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"LLM không kết nối được: {e}") from e
        if resp.status_code >= 400:
            raise LLMError(f"LLM trả lỗi {resp.status_code}: {resp.text[:300]}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"Phản hồi LLM sai cấu trúc: {e}") from e
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM không trả JSON hợp lệ: {content[:200]}") from e

    async def close(self) -> None:
        await self._client.aclose()
