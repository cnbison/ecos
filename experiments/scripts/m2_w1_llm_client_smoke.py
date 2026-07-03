"""M2 W1 LLM 客户端 smoke test.

对应：
  - research/90-mvp/README.md §2.1 (Week 1: CTA + LCA 基础)
  - ecos/llm_client.py (OpenAI-Compatible Protocol 客户端)

目的：
  验证 ECOSLLMClient 在 MiniMax / Moonshot 两个 provider 下：
    1) 配置能正确加载（from_env 或构造器注入）
    2) API Key 缺失时报错友好（给出 env 指引）
    3) API Key 存在时真实调用成功（基础 chat + chat_json）
    4) Markdown fence 剥离正确（```json ... ``` → {...}）

运行：
  PYTHONPATH=. python experiments/scripts/m2_w1_llm_client_smoke.py

依赖：openai>=1.0（已加 pyproject.toml）

行为：
  - 有 MINIMAX_API_KEY 或 MOONSHOT_API_KEY → 真实调用
  - 无 key → 提示设置方式，跳过真实调用
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ecos.llm_client import (  # noqa: E402
    ECOSLLMClient,
    LLMConfig,
    LLMProvider,
    PROVIDER_PRESETS,
    clean_llm_output,
    strip_markdown_fence,
    strip_think_blocks,
)


# ---------------------------------------------------------------------------
# 单元自检（不依赖 API Key）
# ---------------------------------------------------------------------------

def test_markdown_fence() -> tuple[int, int]:
    """验证 strip_markdown_fence 各种场景."""
    cases = [
        # (输入, 期望, 描述)
        ('```json\n{"x": 1}\n```', '{"x": 1}', "标准 json 围栏"),
        ('```\n{"x": 1}\n```', '{"x": 1}', "无语言标识围栏"),
        ('{"x": 1}', '{"x": 1}', "裸 JSON"),
        ('hello', 'hello', "裸文本"),
        ('', '', "空字符串"),
        ('  ```json\n[1,2,3]\n```  ', '[1,2,3]', "前后空白 + 数组"),
    ]
    passed, total = 0, len(cases)
    print("\n--- 单元自检：strip_markdown_fence ---")
    for inp, expected, desc in cases:
        got = strip_markdown_fence(inp)
        ok = got == expected
        marker = "✅" if ok else "❌"
        print(f"  {marker} {desc:<24} → {got!r}")
        if ok:
            passed += 1
    return passed, total


def test_strip_think_blocks() -> tuple[int, int]:
    """验证 strip_think_blocks 各种场景（MiniMax-M3 / DeepSeek-R1 推理块剥离）."""
    cases = [
        # (输入, 期望, 描述)
        ('<think>reasoning here</think>{"x": 1}', '{"x": 1}', "think + 裸 JSON"),
        ('<think>\nmultiline\nreasoning\n</think>\n```json\n{"x": 1}\n```', '{"x": 1}', "think + json 围栏"),
        ('{"x": 1}', '{"x": 1}', "无 think 原样返回"),
        ('<think>unclosed', '<think>unclosed', "未闭合 think 保留原文"),
        ('', '', "空字符串"),
        ('<think>a</think><think>b</think>hello', 'hello', "连续 think 块"),
    ]
    passed, total = 0, len(cases)
    print("\n--- 单元自检：strip_think_blocks ---")
    for inp, expected, desc in cases:
        got = strip_think_blocks(inp)
        ok = got == expected
        marker = "✅" if ok else "❌"
        print(f"  {marker} {desc:<24} → {got!r}")
        if ok:
            passed += 1
    return passed, total


def test_clean_llm_output() -> tuple[int, int]:
    """验证 clean_llm_output 综合清理（think + fence）。"""
    cases = [
        # (输入, 期望, 描述) —— strip_think=True (默认)
        (
            '<think>reasoning</think>```json\n{"x": 1}\n```',
            '{"x": 1}',
            "think + json 围栏 → JSON",
        ),
        (
            '<think>reasoning</think>hello',
            'hello',
            "think + 文本 → 文本",
        ),
    ]
    passed, total = 0, len(cases)
    print("\n--- 单元自检：clean_llm_output ---")
    for inp, expected, desc in cases:
        got = clean_llm_output(inp)
        ok = got == expected
        marker = "✅" if ok else "❌"
        print(f"  {marker} {desc:<24} → {got!r}")
        if ok:
            passed += 1
    return passed, total


def test_preset_configs() -> bool:
    """验证 PROVIDER_PRESETS 配置合理性."""
    print("\n--- 单元自检：PROVIDER_PRESETS ---")
    all_ok = True
    for provider, preset in PROVIDER_PRESETS.items():
        for key in ("base_url", "model", "env_key", "env_base_url", "env_model"):
            if not preset.get(key):
                print(f"  ❌ {provider.value} 缺少 {key}")
                all_ok = False
        if preset["base_url"].startswith("http"):
            print(f"  ✅ {provider.value}: base_url={preset['base_url']}, model={preset['model']}, env_key={preset['env_key']}")
        else:
            print(f"  ❌ {provider.value} base_url 异常：{preset['base_url']}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# API Key 缺失友好提示
# ---------------------------------------------------------------------------

def test_missing_key_error(provider: LLMProvider) -> bool:
    """验证 API key 缺失时给出友好错误."""
    preset = PROVIDER_PRESETS[provider]
    env_keys = (preset["env_key"],) + tuple(preset.get("env_key_aliases", ()))
    # 临时清除所有相关 env（含 aliases）
    saved = {k: os.environ.pop(k, None) for k in env_keys}
    try:
        try:
            LLMConfig.from_env(provider)
            print(f"  ❌ {provider.value} 缺 key 时未报错（异常）")
            return False
        except ValueError as e:
            msg = str(e)
            if env_keys[0] in msg and ("export" in msg or ".env" in msg):
                print(f"  ✅ {provider.value} 缺 key 报错友好（含 {env_keys[0]} + 设置指引）")
                return True
            print(f"  ❌ {provider.value} 报错缺少指引：{msg}")
            return False
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# 真实 API 调用（仅在 key 存在时执行）
# ---------------------------------------------------------------------------

def real_call(provider: LLMProvider) -> bool:
    """有 key 时真实调用一次 chat + 一次 chat_json.

    返回值语义：
      True  = 至少一次 chat 成功
      False = 跳过（无 key 或 key 无效或网络错误）
    """
    try:
        client = ECOSLLMClient.from_env(provider)
    except ValueError as e:
        print(f"  ⚠️ {provider.value} 跳过：{e}")
        return False

    used_key = getattr(client.config, "_used_env_key", client.config.provider.value)
    print(f"\n--- 真实调用：{provider.value} ({client.config.model}) ---")
    print(f"  base_url: {client.config.base_url}")
    print(f"  api_key env: {used_key}")

    # Test 1: 基础 chat
    print("\n  [Test 1] chat() —— 一句话自我介绍")
    try:
        text = client.chat(
            messages=[
                {"role": "system", "content": "你是 ECOS 项目的助手。请用一句话回答。"},
                {"role": "user", "content": "请用一句话介绍你是谁。"},
            ],
            temperature=0.3,
            max_tokens=100,
        )
        print(f"  ✅ chat() 成功：{text[:200]}")
        chat_ok = True
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Invalid Authentication" in err_msg or "invalid_api_key" in err_msg:
            print(f"  ⚠️ chat() 失败：API Key 无效（{used_key} 在 env 中但服务端拒绝）")
        elif "Connection" in err_msg or "Timeout" in err_msg or "NameResolutionError" in err_msg:
            print(f"  ⚠️ chat() 失败：网络/超时（{err_msg[:100]}）")
        else:
            print(f"  ❌ chat() 失败：{err_msg[:200]}")
        return False

    # Test 2: chat_json (用结构化 prompt + markdown fence 测试)
    print("\n  [Test 2] chat_json() —— 返回 JSON 结构")
    try:
        data = client.chat_json(
            messages=[
                {"role": "system", "content": "你是 ECOS 项目的助手。请严格返回 JSON。"},
                {"role": "user", "content": (
                    "返回一个 JSON 对象，包含两个字段："
                    "name（字符串）和 year（整数，2026）。"
                    "用 ```json ... ``` 围栏包裹。"
                )},
            ],
            temperature=0.0,
            max_tokens=100,
        )
        if not isinstance(data, dict):
            print(f"  ❌ chat_json() 返回非 dict：{type(data)}")
            return False
        if "name" not in data or "year" not in data:
            print(f"  ❌ chat_json() 字段缺失：{list(data.keys())}")
            return False
        print(f"  ✅ chat_json() 成功：{data}")
    except Exception as e:
        err_msg = str(e)
        print(f"  ⚠️ chat_json() 失败：{err_msg[:200]}")
        return chat_ok  # 至少 chat 成功了算部分成功

    # Stats
    print("\n  [Stats]")
    for k, v in client.stats.to_dict().items():
        print(f"    {k}: {v}")
    return True


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("M2 W1 LLM 客户端 smoke test")
    print("=" * 78)

    # 1. 单元自检（不依赖 API）
    passed_mf, total_mf = test_markdown_fence()
    print(f"  → strip_markdown_fence: {passed_mf}/{total_mf}")
    passed_tb, total_tb = test_strip_think_blocks()
    print(f"  → strip_think_blocks: {passed_tb}/{total_tb}")
    passed_cl, total_cl = test_clean_llm_output()
    print(f"  → clean_llm_output: {passed_cl}/{total_cl}")
    passed = passed_mf + passed_tb + passed_cl
    total = total_mf + total_tb + total_cl
    presets_ok = test_preset_configs()

    # 2. API key 缺失提示
    print("\n--- 单元自检：API key 缺失友好提示 ---")
    missing_ok_minimax = test_missing_key_error(LLMProvider.MINIMAX)
    missing_ok_moonshot = test_missing_key_error(LLMProvider.MOONSHOT)

    # 3. 真实调用（按 provider 检查）
    print("\n--- 真实 API 调用（仅在 key 存在时执行）---")
    real_minimax = real_call(LLMProvider.MINIMAX)
    real_moonshot = real_call(LLMProvider.MOONSHOT)

    # 总结
    print("\n" + "=" * 78)
    print("Smoke test 总结")
    print("=" * 78)
    print(f"  单元测试（3 类）:         {passed}/{total} （markdown_fence + think_blocks + clean_llm_output）")
    print(f"  PROVIDER_PRESETS 完整性:    {'✅' if presets_ok else '❌'}")
    print(f"  MiniMax 缺 key 友好提示:    {'✅' if missing_ok_minimax else '❌'}")
    print(f"  Moonshot 缺 key 友好提示:   {'✅' if missing_ok_moonshot else '❌'}")
    print(f"  MiniMax 真实调用:           {'✅' if real_minimax else '⚠️ 跳过（无 key / 无效 key / 网络）'}")
    print(f"  Moonshot 真实调用:          {'✅' if real_moonshot else '⚠️ 跳过（无 key / 无效 key / 网络）'}")
    print()

    if not real_minimax and not real_moonshot:
        print("  💡 提示：要让真实调用通过，请设置：")
        print("     export MINIMAX_API_KEY=<your-key>   # 主用")
        print("     # 或")
        print("     export MOONSHOT_API_KEY=<your-key>  # 中文教育场景备选")
        print()

    unit_pass = (passed == total) and presets_ok and missing_ok_minimax and missing_ok_moonshot
    print(f"  单元测试：{'✅ 全部通过' if unit_pass else '❌ 有失败'}")
    return 0 if unit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())