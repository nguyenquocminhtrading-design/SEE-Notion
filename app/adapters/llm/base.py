"""LLMClient: CHỈ có một việc — nhận text, trả JSON dict. Không tool, không action."""
from abc import ABC, abstractmethod


class LLMError(Exception):
    pass


class LLMClient(ABC):
    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict:
        """Gửi prompt, nhận về dict JSON. Raise LLMError khi fail."""
