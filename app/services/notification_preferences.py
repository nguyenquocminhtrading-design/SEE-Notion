"""Quy tắc preference thông báo dùng chung cho email và Discord DM."""
import json


def accepts_channel(user, channel: str) -> bool:
    """Mặc định nhận thông báo nếu cấu hình cũ chưa có prefs."""
    try:
        prefs = json.loads(user.prefs_json or "{}")
    except (TypeError, json.JSONDecodeError):
        prefs = {}
    return bool(prefs.get(channel, True))
