from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ds_config import DSConfig


@dataclass
class DSUsage:
    """
    统一 usage 结构（不同SDK版本字段可能有差异，因此做容错提取）
    """
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DSChatResult:
    """
    统一返回结构（无论成功/失败都返回这个）
    """
    ok: bool
    content: str = ""                 # 成功时模型文本输出；失败时通常为空
    error_type: str = ""              # 失败时错误类型（如 TimeoutError / APIError 等）
    error_message: str = ""           # 失败时错误信息
    model: str = ""
    attempts: int = 0                 # 实际尝试次数（首次+重试）
    latency_ms: int = 0               # 总耗时（含重试）
    finish_reason: str = ""
    usage: DSUsage = field(default_factory=DSUsage)

    # 便于上层调试/日志（不建议直接持久化整个对象）
    raw_response: Any = None

    def to_dict(self, include_raw_response: bool = False) -> Dict[str, Any]:
        data = {
            "ok": self.ok,
            "content": self.content,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "model": self.model,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "usage": self.usage.to_dict(),
        }
        if include_raw_response:
            data["raw_response"] = self.raw_response
        return data


class DSClient:
    """
    DeepSeek 统一客户端封装（基于 OpenAI SDK）
    目标：
    1) 统一返回结构
    2) 统一异常处理
    3) 统一重试逻辑
    4) 给上层（如 ds_scoring_service）提供稳定接口
    """

    def __init__(self, config: Optional[DSConfig] = None) -> None:
        self.config = config or DSConfig.from_env()

        # 允许 api_key 为空（上层可走fallback逻辑）
        # 为避免 SDK 初始化时报错，这里给一个占位值。
        self._client = OpenAI(
            api_key=self.config.api_key or "EMPTY_KEY",
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
        )

    @property
    def is_ready(self) -> bool:
        return self.config.is_ready

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        extra_create_kwargs: Optional[Dict[str, Any]] = None,
    ) -> DSChatResult:
        """
        统一聊天接口（当前系统评分场景主要用这个）

        参数：
        - messages: OpenAI SDK 标准 messages
        - model: 可覆盖默认模型
        - temperature: 可覆盖默认温度（评分任务一般建议0）
        - stream: 当前系统默认 False
        - extra_create_kwargs: 透传给 create(...) 的额外参数（可选）

        返回：
        - DSChatResult（统一结构）
        """
        started = time.perf_counter()
        final_model = (model or self.config.model).strip() or self.config.model
        final_temp = self.config.temperature if temperature is None else float(temperature)
        max_retries = max(0, int(self.config.max_retries))
        extra_kwargs = extra_create_kwargs or {}

        # 如果没有key，让上层能识别并决定fallback，而不是这里抛异常中断。
        if not self.is_ready:
            return DSChatResult(
                ok=False,
                content="",
                error_type="ConfigError",
                error_message="DEEPSEEK_API_KEY 未配置",
                model=final_model,
                attempts=0,
                latency_ms=self._elapsed_ms(started),
                finish_reason="",
                usage=DSUsage(),
                raw_response=None,
            )

        last_err_type = ""
        last_err_msg = ""

        for attempt_idx in range(max_retries + 1):  # 首次 + 重试
            try:
                resp = self._client.chat.completions.create(
                    model=final_model,
                    messages=messages,
                    stream=stream,
                    temperature=final_temp,
                    **extra_kwargs,
                )

                # 当前系统使用 stream=False；若后续需要stream，可扩展。
                if stream:
                    # 暂不支持流式统一聚合，明确返回错误，避免静默异常
                    return DSChatResult(
                        ok=False,
                        content="",
                        error_type="NotImplementedError",
                        error_message="DSClient.chat 当前仅支持 stream=False",
                        model=final_model,
                        attempts=attempt_idx + 1,
                        latency_ms=self._elapsed_ms(started),
                        finish_reason="",
                        usage=DSUsage(),
                        raw_response=resp,
                    )

                content = self._extract_content(resp)
                finish_reason = self._extract_finish_reason(resp)
                usage = self._extract_usage(resp)

                return DSChatResult(
                    ok=True,
                    content=content,
                    error_type="",
                    error_message="",
                    model=final_model,
                    attempts=attempt_idx + 1,
                    latency_ms=self._elapsed_ms(started),
                    finish_reason=finish_reason,
                    usage=usage,
                    raw_response=resp,
                )

            except Exception as e:
                last_err_type = type(e).__name__
                last_err_msg = str(e)
                # 继续重试；最后一次失败后统一返回
                continue

        return DSChatResult(
            ok=False,
            content="",
            error_type=last_err_type or "UnknownError",
            error_message=last_err_msg or "DS 调用失败",
            model=final_model,
            attempts=max_retries + 1,
            latency_ms=self._elapsed_ms(started),
            finish_reason="",
            usage=DSUsage(),
            raw_response=None,
        )

    # -------------------------
    # 内部工具方法（容错提取）
    # -------------------------

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _extract_content(resp: Any) -> str:
        try:
            # 标准路径：resp.choices[0].message.content
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _extract_finish_reason(resp: Any) -> str:
        try:
            return str(resp.choices[0].finish_reason or "")
        except Exception:
            return ""

    @staticmethod
    def _extract_usage(resp: Any) -> DSUsage:
        try:
            u = getattr(resp, "usage", None)
            if not u:
                return DSUsage()
            return DSUsage(
                prompt_tokens=getattr(u, "prompt_tokens", None),
                completion_tokens=getattr(u, "completion_tokens", None),
                total_tokens=getattr(u, "total_tokens", None),
            )
        except Exception:
            return DSUsage()