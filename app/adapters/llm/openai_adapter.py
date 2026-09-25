"""OpenAI-compatible client (hỗ trợ OpenAI, OpenRouter, Groq...)."""
import logging
import json

import httpx

from app.adapters.llm.base import LLMClient, LLMError
from app.config import get_settings

log = logging.getLogger(__name__)
TIMEOUT = 25.0


class OpenAIClient(LLMClient):
    def __init__(self):
        s = get_settings()
        self._model = s.llm_model
        
        # Lấy URL tùy chỉnh nếu có, mặc định là OpenAI API
        base_url = getattr(s, "openai_base_url", "https://api.openai.com/v1")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
            
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
            # Một số model OSS không hỗ trợ strict json_object, ta thử bỏ qua nếu lỗi
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        try:
            resp = await self._client.post(self._endpoint, json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"LLM không kết nối được: {e}") from e
            
        if resp.status_code >= 400:
            # Nếu nền tảng không hỗ trợ response_format, thử lại không có format
            if "response_format" in resp.text:
                del body["response_format"]
                resp = await self._client.post(self._endpoint, json=body)
            if resp.status_code >= 400:
                raise LLMError(f"LLM trả lỗi {resp.status_code}: {resp.text[:300]}")
                
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"Phản hồi LLM sai cấu trúc: {e}") from e
            
        # Tìm block json nếu model trả về có kèm text
        content = content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM không trả JSON hợp lệ: {content[:200]}") from e

    async def close(self) -> None:
        await self._client.aclose()
