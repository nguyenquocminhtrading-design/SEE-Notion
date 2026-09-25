"""Factory chọn LLM theo env. Đổi provider = đổi 1 biến, không sửa code."""
from app.adapters.llm.base import LLMClient
from app.config import get_settings


def make_llm_client() -> LLMClient:
    provider = get_settings().llm_provider.lower()
    if provider == "glm":
        from app.adapters.llm.glm import GLMClient
        return GLMClient()
    if provider == "ollama":
        from app.adapters.llm.ollama import OllamaClient
        return OllamaClient()
    if provider == "openai":
        from app.adapters.llm.openai_adapter import OpenAIClient
        return OpenAIClient()
    raise ValueError(f"LLM_PROVIDER không hợp lệ: {provider} (chỉ hỗ trợ glm | ollama | openai)")
