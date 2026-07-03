"""ECOS 统一 LLM 客户端（OpenAI-Compatible Protocol）.

设计原则：
  1. 可配置：provider / model / base_url / api_key 都可由构造器或 env 注入
  2. 多 LLM 支持：默认 MiniMax-M3（项目标配），备选 Moonshot Kimi（中文教育场景）
  3. 健壮性：markdown fence 剥离、retry + 指数退避、stats（calls/tokens/errors）
  4. 教学友好：清晰的错误提示（缺 key 时给出 env 设置指引）

使用：
    from ecos.llm_client import ECOSLLMClient
    client = ECOSLLMClient.from_env(provider="minimax")
    text = client.chat([{"role": "user", "content": "你好"}])
    data = client.chat_json([{"role": "user", "content": "返回 {\"x\": 1}"}])

参考：
  SelfLab sge/llm_client.py（详见 references/aibeing-core-engine-reference.md）
  research/90-mvp/README.md §2.1 M2 工程实现
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LLMProvider(Enum):
    """支持的 LLM 提供商（OpenAI-Compatible Protocol）."""

    MINIMAX = "minimax"   # 项目默认；Base URL: https://api.minimax.io/v1
    MOONSHOT = "moonshot"  # Moonshot Kimi；中文教育场景友好


# 提供商预设配置（用户/项目约定）
PROVIDER_PRESETS: Dict[LLMProvider, Dict[str, Any]] = {
    LLMProvider.MINIMAX: {
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M3",
        "env_key": "MINIMAX_API_KEY",
        "env_base_url": "MINIMAX_BASE_URL",
        "env_model": "MINIMAX_MODEL",
        "env_key_aliases": (),  # MiniMax 无别名
    },
    LLMProvider.MOONSHOT: {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "env_key": "MOONSHOT_API_KEY",
        "env_base_url": "MOONSHOT_BASE_URL",
        "env_model": "MOONSHOT_MODEL",
        "env_key_aliases": ("KIMI_API_KEY",),  # 接受 Moonshot 的两个常用命名
    },
}


@dataclass
class LLMConfig:
    """LLM 客户端配置.

    Attributes:
        provider: 提供商枚举
        model: 模型名（如 'MiniMax-M3' / 'moonshot-v1-8k'）
        base_url: OpenAI-Compatible base URL
        api_key: API Key（缺失时构造器抛错）
        timeout: 请求超时（秒）
        max_retries: 最大重试次数（指数退避）
        temperature: 默认温度
        max_tokens: 默认最大生成 token
    """

    provider: LLMProvider
    model: str
    base_url: str
    api_key: str
    timeout: float = 30.0
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int = 1024

    @classmethod
    def from_env(cls, provider: str | LLMProvider = "minimax") -> "LLMConfig":
        """从环境变量构造配置（找不到 key 时抛错并给出指引）."""
        if isinstance(provider, str):
            provider = LLMProvider(provider.lower())

        preset = PROVIDER_PRESETS[provider]
        # 主 key + aliases（如 MOONSHOT 接受 KIMI_API_KEY）
        env_keys = (preset["env_key"],) + tuple(preset.get("env_key_aliases", ()))
        api_key = ""
        used_env_key = ""
        for env_key in env_keys:
            candidate = os.environ.get(env_key, "").strip()
            if candidate:
                api_key = candidate
                used_env_key = env_key
                break
        if not api_key:
            all_keys = ", ".join(env_keys)
            raise ValueError(
                f"未找到 {provider.value} 的 API Key。\n"
                f"  设置方式：export {env_keys[0]}=<your-key>\n"
                f"  接受的 env 变量：{all_keys}\n"
                f"  或在 .env 文件中：{env_keys[0]}=<your-key>\n"
                f"  参考：.env.example"
            )
        base_url = os.environ.get(preset["env_base_url"], preset["base_url"]).strip()
        model = os.environ.get(preset["env_model"], preset["model"]).strip()
        config = cls(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        config._used_env_key = used_env_key  # type: ignore[attr-defined]
        return config


@dataclass
class LLMStats:
    """调用统计（按 client 累计）."""

    calls: int = 0
    successes: int = 0
    errors: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def record_success(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.calls += 1
        self.successes += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens

    def record_error(self) -> None:
        self.calls += 1
        self.errors += 1

    def to_dict(self) -> Dict[str, int]:
        return {
            "calls": self.calls,
            "successes": self.successes,
            "errors": self.errors,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


_MARKDOWN_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n(?P<body>.*?)\n```\s*$",
    re.DOTALL,
)


def strip_markdown_fence(text: str) -> str:
    """剥离 LLM 输出中常见的 ```json ... ``` 围栏.

    兼容情况：
      - ```json\\n{...}\\n```     → {...}
      - ```\\n{...}\\n```         → {...}
      - 裸 JSON / 裸文本           → 原样返回
    """
    if not text:
        return text
    m = _MARKDOWN_FENCE_RE.match(text.strip())
    if m:
        return m.group("body").strip()
    return text.strip()


class ECOSLLMClient:
    """ECOS 统一 LLM 客户端（OpenAI-Compatible Protocol）.

    用法：
        client = ECOSLLMClient(LLMConfig.from_env("minimax"))
        text = client.chat([{"role": "user", "content": "你好"}])
        data = client.chat_json([{"role": "user", "content": "返回 JSON"}])

    也可用 from_env 工厂：
        client = ECOSLLMClient.from_env(provider="minimax")
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.stats = LLMStats()
        # 延迟导入 openai（避免在无 key 的环境 import 失败）
        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(
                base_url=config.base_url,
                api_key=config.api_key,
                timeout=config.timeout,
            )
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "openai 包未安装。请运行：pip install openai>=1.0"
            ) from e

    @classmethod
    def from_env(cls, provider: str | LLMProvider = "minimax") -> "ECOSLLMClient":
        """从环境变量构造客户端（找不到 key 时抛错并给出指引）."""
        return cls(LLMConfig.from_env(provider))

    # ---------------------------------------------------------------
    # 主接口
    # ---------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """发送 chat 请求，返回文本响应.

        Args:
            messages: OpenAI 格式消息列表 [{"role": ..., "content": ...}]
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大 token
            **kwargs: 透传给 openai SDK

        Returns:
            LLM 生成的文本（已 strip 前后空白）
        """
        response = self._call_with_retry(
            messages=messages,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.config.max_tokens,
            **kwargs,
        )
        text = self._extract_text(response)
        self._record_usage(response, success=True)
        return text

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        """发送 chat 请求，解析 JSON 返回.

        自动剥离 ```json ... ``` 围栏。解析失败时抛 ValueError 含原始文本。

        Returns:
            Python 对象（dict / list / 基本类型）
        """
        text = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        cleaned = strip_markdown_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM 输出无法解析为 JSON：{e}\n原始文本：\n{text}\n清理后：\n{cleaned}"
            ) from e

    # ---------------------------------------------------------------
    # 内部
    # ---------------------------------------------------------------

    def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> Any:
        """带指数退避的 API 调用."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return response
            except Exception as e:  # 覆盖网络/限流/服务端错误
                last_exc = e
                if attempt < self.config.max_retries - 1:
                    sleep_s = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(sleep_s)
                    continue
        self.stats.record_error()
        raise RuntimeError(
            f"LLM 调用失败（重试 {self.config.max_retries} 次后仍失败）：{last_exc}"
        ) from last_exc

    @staticmethod
    def _extract_text(response: Any) -> str:
        """从 OpenAI response 提取文本."""
        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError, KeyError) as e:
            raise RuntimeError(f"无法解析 LLM 响应结构：{response}") from e

    def _record_usage(self, response: Any, success: bool) -> None:
        """记录 token 用量到 stats."""
        if not success:
            return
        try:
            usage = response.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            self.stats.record_success(prompt_tokens, completion_tokens)
        except AttributeError:
            # 某些 LLM 不返回 usage，至少记录一次成功
            self.stats.record_success()

    def __repr__(self) -> str:
        return (
            f"ECOSLLMClient(provider={self.config.provider.value}, "
            f"model={self.config.model!r}, base_url={self.config.base_url!r})"
        )


# 公开 API
__all__ = [
    "ECOSLLMClient",
    "LLMConfig",
    "LLMProvider",
    "LLMStats",
    "PROVIDER_PRESETS",
    "strip_markdown_fence",
]