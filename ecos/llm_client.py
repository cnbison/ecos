"""ECOS LLM Client（占位）.

Phase 4+ 实施时实现：
- 统一封装 MiniMax-M3（默认）/ Moonshot（跨 LLM 验证）
- 自动 markdown fence 处理
- stats 成本统计
- retry / warmup / timeout

参考 SelfLab sge/llm_client.py 设计（详见 references/aibeing-core-engine-reference.md）。
"""

from typing import Any, Dict, List, Optional


class ECOSLLMClient:
    """ECOS 统一 LLM 客户端（占位，Phase 4+ 实施）."""

    def __init__(self, provider: str = "minimax", model: Optional[str] = None):
        self.provider = provider
        self.model = model or self._default_model()
        self.stats = {"calls": 0, "tokens": 0, "errors": 0}

    def _default_model(self) -> str:
        if self.provider == "minimax":
            return "MiniMax-M3"
        elif self.provider == "moonshot":
            return "moonshot-v1-8k"
        return "unknown"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送 chat 请求（占位）."""
        raise NotImplementedError("ECOSLLMClient.chat 待 Phase 4+ 实施")

    def chat_json(self, messages: List[Dict[str, str]], **kwargs) -> Any:
        """发送 chat 请求并解析 JSON（占位）."""
        raise NotImplementedError("ECOSLLMClient.chat_json 待 Phase 4+ 实施")
