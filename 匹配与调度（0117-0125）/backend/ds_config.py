# backend/ds_config.py
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class DSConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout_ms: int = 15000
    max_retries: int = 1
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "DSConfig":
        return cls(
            enabled=_env_bool("DS_ENABLED", False),
            api_key=os.getenv("DS_API_KEY", "").strip(),
            base_url=os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1").strip().rstrip("/"),
            model=os.getenv("DS_MODEL", "deepseek-chat").strip(),
            timeout_ms=_env_int("DS_TIMEOUT_MS", 15000),
            max_retries=_env_int("DS_MAX_RETRIES", 1),
            temperature=float(os.getenv("DS_TEMPERATURE", "0.0") or 0.0),
        )

    def validate(self) -> tuple[bool, str | None]:
        if not self.enabled:
            return True, None
        if not self.api_key:
            return False, "DS_ENABLED=true 但未配置 DS_API_KEY"
        if not self.base_url:
            return False, "DS_BASE_URL 为空"
        if not self.model:
            return False, "DS_MODEL 为空"
        if self.timeout_ms <= 0:
            return False, "DS_TIMEOUT_MS 必须 > 0"
        if self.max_retries < 0:
            return False, "DS_MAX_RETRIES 不能 < 0"
        return True, None