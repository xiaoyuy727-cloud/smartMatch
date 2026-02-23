# backend/ds_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import time

import httpx

from ds_config import DSConfig


@dataclass
class DSClientResult:
    ok: bool
    content: str = ""
    status_code: int | None = None
    error: str | None = None
    elapsed_ms: int = 0
    raw: Dict[str, Any] | None = None


class DeepSeekClient:
    """
    OpenAI-compatible chat/completions client for DeepSeek-like APIs.
    """

    def __init__(self, config: DSConfig):
        self.config = config

    def chat_json(self, system_prompt: str, user_prompt: str) -> DSClientResult:
        """
        调用 chat/completions，返回 message.content 文本
        """
        if not self.config.enabled:
            return DSClientResult(ok=False, error="DS disabled by config")

        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            # 部分兼容 OpenAI 的服务支持该字段；不支持一般会忽略/报错。
            # 如你实际环境报错，可删掉这一行。
            "response_format": {"type": "json_object"},
        }

        attempts = self.config.max_retries + 1
        last_err: str | None = None

        for i in range(attempts):
            t0 = time.time()
            try:
                with httpx.Client(timeout=self.config.timeout_ms / 1000.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                elapsed = int((time.time() - t0) * 1000)

                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:500]}"
                    # 4xx 通常无需重试；5xx 可重试
                    if 400 <= resp.status_code < 500:
                        return DSClientResult(
                            ok=False,
                            status_code=resp.status_code,
                            error=last_err,
                            elapsed_ms=elapsed,
                        )
                    if i < attempts - 1:
                        continue
                    return DSClientResult(
                        ok=False,
                        status_code=resp.status_code,
                        error=last_err,
                        elapsed_ms=elapsed,
                    )

                data = resp.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not isinstance(content, str):
                    content = str(content)

                return DSClientResult(
                    ok=True,
                    content=content,
                    status_code=resp.status_code,
                    elapsed_ms=elapsed,
                    raw=data,
                )

            except httpx.TimeoutException:
                elapsed = int((time.time() - t0) * 1000)
                last_err = "timeout"
                if i < attempts - 1:
                    continue
                return DSClientResult(ok=False, error=last_err, elapsed_ms=elapsed)

            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                last_err = f"{type(e).__name__}: {e}"
                if i < attempts - 1:
                    continue
                return DSClientResult(ok=False, error=last_err, elapsed_ms=elapsed)

        return DSClientResult(ok=False, error=last_err or "unknown error")