from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict


def _to_int(value: str | None, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _to_float(value: str | None, default: float) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).strip())
    except Exception:
        return default


@dataclass(frozen=True)
class DSConfig:
    """
    DeepSeek 调用配置（统一读取环境变量）

    推荐环境变量（你当前系统已使用前3项）：
    - DEEPSEEK_API_KEY          必填（生产/真实调用时）
    - DEEPSEEK_BASE_URL         默认 https://api.deepseek.com
    - DEEPSEEK_MODEL            默认 deepseek-chat
    - DEEPSEEK_TIMEOUT_SECONDS  默认 120
    - DEEPSEEK_MAX_RETRIES      默认 2（表示失败后再重试2次）
    - DEEPSEEK_TEMPERATURE      默认 0.0（评分任务建议更稳定）
    """

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_seconds: float = 120.0
    max_retries: int = 2
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "DSConfig":
        api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        base_url = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
        model = (os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat").strip()

        timeout_seconds = _to_float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS"), 120.0)
        max_retries = _to_int(os.environ.get("DEEPSEEK_MAX_RETRIES"), 2)
        temperature = _to_float(os.environ.get("DEEPSEEK_TEMPERATURE"), 0.0)

        # 基本容错（避免明显非法值）
        if timeout_seconds <= 0:
            timeout_seconds = 120.0
        if max_retries < 0:
            max_retries = 0
        if temperature < 0:
            temperature = 0.0
        if temperature > 2:
            temperature = 2.0

        if not base_url:
            base_url = "https://api.deepseek.com"
        if not model:
            model = "deepseek-chat"

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            temperature=temperature,
        )

    @property
    def is_ready(self) -> bool:
        """是否具备真实调用DS的最基本条件（API Key存在）"""
        return bool(self.api_key)

    def validate(self) -> tuple[bool, str]:
        """
        返回 (是否通过, 错误信息)
        不抛异常，方便上层决定“回退继续”还是“阻断任务”。
        """
        if not self.base_url:
            return False, "DEEPSEEK_BASE_URL 为空"
        if not self.model:
            return False, "DEEPSEEK_MODEL 为空"
        if self.timeout_seconds <= 0:
            return False, "DEEPSEEK_TIMEOUT_SECONDS 必须大于0"
        if self.max_retries < 0:
            return False, "DEEPSEEK_MAX_RETRIES 不能小于0"
        if not (0 <= self.temperature <= 2):
            return False, "DEEPSEEK_TEMPERATURE 必须在[0,2]范围"
        # api_key 允许为空（开发阶段/走fallback），所以这里只提示不报错
        return True, ""

    def to_dict(self, mask_secret: bool = True) -> Dict[str, Any]:
        data = asdict(self)
        if mask_secret:
            data["api_key"] = self._mask_secret(self.api_key)
        return data

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"