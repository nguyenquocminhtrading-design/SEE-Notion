"""Preview object trả về cho Discord/web (kế hoạch §8)."""
from typing import Any, Optional

from pydantic import BaseModel


class Preview(BaseModel):
    nonce: str
    expires_in_seconds: int
    intent: str
    summary_lines: list[str]
    warnings: list[str] = []
    payload: dict[str, Any]


class ActionError(Exception):
    """Lỗi nghiệp vụ có thông điệp thân thiện hiển thị thẳng cho người dùng."""

    def __init__(self, code: str, message: str, options: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.options = options or []


class ClarifyError(ActionError):
    """Cần người dùng làm rõ (gán người mơ hồ, task trùng tên...)."""

    def __init__(self, code: str, message: str, options: list[str] | None = None):
        super().__init__(code, message, options)
