"""Long-term Session Management（长期会话管理）.

实现 ECOS 长期会话管理：
- TwinSession 类（单次学生与 ECOS 交互）
- 多轮对话的状态维护
- 滚动 epoch 计数器
- session 期间状态驻内存

借鉴 SelfLab SGE session.py（基于 AiBeing chat_agent._chat_inner 模式）。

Phase 4+ 实施细节：见 research/10-engineering/05-persistence-session.md
"""

__status__ = "placeholder"
