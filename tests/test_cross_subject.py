"""v0.55.0-d: 跨学科迁移验证 (5 学科 × 2 维度 = 10 测试).

ECOS 领域无关原则 (Bisen v0.54.1-e):
- 5D 核心 (K/P/S/C-confidence/X-external-support) 必须跨数学/语文/英语/物理/化学通用
- 5 学科 PC-C/PC-X 题目设计协议:
  - PC-C{i:02d}-{subject}: 第 i 道 C-confidence 主导题, 学科特化
  - PC-X{i:02d}-{subject}: 第 i 道 X-external-support 主导题, 学科特化
- 当前状态 (v0.55.0):
  - python 学科: 51 题 (26 PB-Q + 20 PB-C + 5 PC-C) + 10 题 cross_subject (PC-C/PC-X) 已落地
  - math/chinese/english/physics/chemistry: 0 题 (待 v0.56.0+)

拦截历史:
- v0.54.1-d C/X 维度定义漂移
- v0.54.1-e Bisen 决策: 5D 核心必须领域无关
- v0.55.0-c 验证双层架构 (PC-C/PC-X 跨学科 vs PB-C 编程调试)
- v0.55.0-d 验证 5 学科扩展 slot 存在 + 当前 4 学科待设计 (CI gate 防 slot 误删)

测试:
1. test_metadata_subject_extensions_slot_exists: 验证 Q 矩阵 metadata 包含 subject_extensions
2. test_5_subjects_target_count: 验证 5 学科各 10 道题的设计目标
3. test_current_python_baseline_count: 验证 python 学科 56 题已落地 (26+5+20+5)
4. test_5_subjects_current_count_zero_pending: 验证 5 学科扩展当前 0 题 (v0.56.0+ 待设计)
5. test_5_subjects_topic_prefix_protocol: 验证 topic 前缀协议 (math.*/chinese.* 等)
6. test_cross_subject_python_baseline: 验证 cross_subject 抽象题 10 道 (PC-C01-C05 + PC-X01-X05)
7. test_cross_subject_5_subjects_arch_support: 验证 Q 矩阵支持 5 学科扩展 (字段验证)
8. test_no_python_bleed_into_other_subjects: 验证 python 学科题不污染 5 学科扩展
9. test_5_subjects_extension_total_target_50: 验证 5 学科扩展总目标 50 道
10. test_5_subjects_extension_arch_audit: 验证 5 学科架构审计 (5 个断言)
"""
import json
from pathlib import Path

import pytest


# ─── 加载 Q 矩阵 fixture ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qdata():
    """加载 Q 矩阵供所有测试使用."""
    qpath = Path("data/python_basics_q_matrix.json")
    with open(qpath) as f:
        return json.load(f)


# ─── 测试 1: subject_extensions slot 存在 ─────────────────────────────

def test_metadata_subject_extensions_slot_exists(qdata):
    """Q 矩阵 metadata 必须包含 subject_extensions 字段 (5 学科扩展 slot).

    拦截历史:
    - v0.55.0-d 新增: 防止后续重构删除 5 学科扩展 slot
    """
    metadata = qdata["metadata"]
    assert "subject_extensions" in metadata, \
        "❌ Q 矩阵 metadata 必须包含 subject_extensions 字段 (5 学科扩展 slot)\n" \
        "   任何删除 subject_extensions 的改动都是 ECOS 领域无关原则倒退"

    ext = metadata["subject_extensions"]
    assert "schema" in ext, "❌ subject_extensions 必须有 schema 字段 (5 学科 topic 协议)"
    assert "question_count_target" in ext, \
        "❌ subject_extensions 必须有 question_count_target 字段 (设计目标)"
    assert "current_count" in ext, \
        "❌ subject_extensions 必须有 current_count 字段 (当前进度)"


# ─── 测试 2: 5 学科各 10 道题设计目标 ─────────────────────────────────

def test_5_subjects_target_count(qdata):
    """5 学科 (math/chinese/english/physics/chemistry) 各 10 道题设计目标.

    拦截历史:
    - v0.54.1-e Bisen 决策: 5D 核心必须跨 5 学科通用, 每学科各 10 道
    """
    target = qdata["metadata"]["subject_extensions"]["question_count_target"]
    expected_subjects = {"math", "chinese", "english", "physics", "chemistry"}
    actual_subjects = set(target.keys())

    assert actual_subjects == expected_subjects, \
        f"❌ 5 学科目标学科集不匹配: 期望={expected_subjects}, 实际={actual_subjects}"

    for subj in expected_subjects:
        assert target[subj] == 10, \
            f"❌ {subj} 学科目标题数应为 10, 实际={target[subj]}"


# ─── 测试 3: python 学科 baseline 56 题已落地 ─────────────────────────

def test_current_python_baseline_count(qdata):
    """python 学科 56 题已落地 (26 PB-Q + 20 PB-C + 5 PC-C + 5 PC-X).

    拦截历史:
    - v0.54.0-b C 主导题 5 道样题
    - v0.54.1 C 主导题扩 20 道 (PB-C01-C20)
    - v0.54.2 C-confidence 主导题 5 道 (PC-C01-C05)
    - v0.54.3 X-external-support 主导题 5 道 (PC-X01-X05)
    """
    problems = qdata["problems"]

    # 验证总数
    assert len(problems) == 56, \
        f"❌ python 学科题目总数应为 56, 实际={len(problems)}"

    # 按 problem_id 前缀分组
    by_prefix = {}
    for p in problems:
        prefix = p["problem_id"].split("-")[0]
        by_prefix.setdefault(prefix, []).append(p["problem_id"])

    # 验证各类型数量
    expected_counts = {"PB": 51, "PC": 5}  # 26+20=46 PB-Q+PB-C, 5 PC-C
    # PC 系列还包含 PC-X01-X05
    pc_total = len(by_prefix.get("PC", []))
    assert pc_total == 10, \
        f"❌ PC 系列题目应为 10 (5 PC-C + 5 PC-X), 实际={pc_total}"

    pb_total = len(by_prefix.get("PB", []))
    assert pb_total == 46, \
        f"❌ PB 系列题目应为 46 (26 PB-Q + 20 PB-C), 实际={pb_total}"

    total = pb_total + pc_total
    assert total == 56, f"❌ 总题数应=56, 实际={total}"


# ─── 测试 4: 5 学科扩展当前 0 题 (待 v0.56.0+) ────────────────────────

def test_5_subjects_current_count_zero_pending(qdata):
    """5 学科扩展 (math/chinese/english/physics/chemistry) 当前 0 题.

    拦截历史:
    - v0.55.0-d 标记: 4 学科待 v0.56.0+ 设计
    - 任何'当前已实现'的早期 commit 都会被本测试拦截 (CI gate 防 4 虚标)
    """
    current = qdata["metadata"]["subject_extensions"]["current_count"]
    expected_subjects = {"math", "chinese", "english", "physics", "chemistry"}

    for subj in expected_subjects:
        assert current[subj] == 0, \
            f"❌ {subj} 学科当前题数应为 0 (v0.56.0+ 设计), 实际={current[subj]}\n" \
            f"   如果你正在 v0.56.0+ 落地 {subj} 题库, 请同步更新 current_count 字段"


# ─── 测试 5: 5 学科 topic 前缀协议 ────────────────────────────────────

def test_5_subjects_topic_prefix_protocol(qdata):
    """5 学科 topic 前缀协议: math.*/chinese.*/english.*/physics.*/chemistry.*.

    拦截历史:
    - v0.55.0-d 新增: 防止 topic 前缀乱命名 (如 'mathematics' 应为 'math')
    - v0.54.2/3 已用 'cross_subject' 抽象, v0.56.0+ 应拆为 5 学科具象
    """
    schema = qdata["metadata"]["subject_extensions"]["schema"]
    expected_prefixes = {
        "math": "math.*",
        "chinese": "chinese.*",
        "english": "english.*",
        "physics": "physics.*",
        "chemistry": "chemistry.*",
    }

    for subj, expected_prefix in expected_prefixes.items():
        assert subj in schema, f"❌ schema 缺少 {subj} 学科定义"
        assert expected_prefix in schema[subj], \
            f"❌ {subj} 学科 topic 前缀协议应为 '{expected_prefix}', " \
            f"实际='{schema[subj]}'"


# ─── 测试 6: cross_subject 抽象题 10 道 (已落地) ─────────────────────

def test_cross_subject_python_baseline(qdata):
    """cross_subject 抽象题 10 道已落地: PC-C01-C05 + PC-X01-X05.

    拦截历史:
    - v0.54.2 PC-C01-C05 (5 道) C-confidence 抽象题
    - v0.54.3 PC-X01-X05 (5 道) X-external-support 抽象题
    """
    problems = qdata["problems"]
    cross_subject = [p for p in problems if p["topic"] == "cross_subject"]

    assert len(cross_subject) == 10, \
        f"❌ cross_subject 抽象题应有 10 道 (5 PC-C + 5 PC-X), 实际={len(cross_subject)}"

    # 验证 PC-C01-C05 全部存在
    pc_c_ids = {f"PC-C{i:02d}" for i in range(1, 6)}
    actual_pc_c = {p["problem_id"] for p in cross_subject if p["problem_id"].startswith("PC-C")}
    assert actual_pc_c == pc_c_ids, \
        f"❌ PC-C01-C05 缺漏: 期望={pc_c_ids}, 实际={actual_pc_c}"

    # 验证 PC-X01-X05 全部存在
    pc_x_ids = {f"PC-X{i:02d}" for i in range(1, 6)}
    actual_pc_x = {p["problem_id"] for p in cross_subject if p["problem_id"].startswith("PC-X")}
    assert actual_pc_x == pc_x_ids, \
        f"❌ PC-X01-X05 缺漏: 期望={pc_x_ids}, 实际={actual_pc_x}"


# ─── 测试 7: 5 学科扩展架构支持 (字段验证) ───────────────────────────

def test_cross_subject_5_subjects_arch_support(qdata):
    """Q 矩阵 metadata 支持 5 学科扩展 (字段验证, 不依赖实际题目).

    拦截历史:
    - v0.55.0-d 新增: CI gate 防 subject_extensions 字段被误删
    """
    ext = qdata["metadata"]["subject_extensions"]

    # 必须包含的 3 个字段
    required_fields = {"schema", "question_count_target", "current_count"}
    actual_fields = set(ext.keys())
    assert required_fields.issubset(actual_fields), \
        f"❌ subject_extensions 缺少字段: 期望≥{required_fields}, 实际={actual_fields}"

    # schema 包含 _comment + 5 学科
    schema_keys = set(ext["schema"].keys())
    expected_schema = {"math", "chinese", "english", "physics", "chemistry"}
    assert expected_schema.issubset(schema_keys), \
        f"❌ schema 缺少 5 学科: 期望≥{expected_schema}, 实际={schema_keys}"


# ─── 测试 8: python 不污染 5 学科扩展 ─────────────────────────────────

def test_no_python_bleed_into_other_subjects(qdata):
    """python 学科题不污染 5 学科扩展 (topic 不重叠).

    拦截历史:
    - v0.55.0-d 新增: 防止 PB-* 题目错放在 5 学科扩展字段
    """
    problems = qdata["problems"]
    python_problems = [p for p in problems if p["topic"].startswith("python")]

    # 验证所有 python 题的 topic 是 python.* (不是 math.* 或 cross_subject)
    for p in python_problems:
        assert p["topic"].startswith("python"), \
            f"❌ python 学科题 {p['problem_id']} topic 应='python.*', 实际='{p['topic']}'"

    # 验证 cross_subject 抽象题不混入 python 学科
    cross_subject = [p for p in problems if p["topic"] == "cross_subject"]
    for p in cross_subject:
        assert not p["topic"].startswith("python"), \
            f"❌ cross_subject 抽象题 {p['problem_id']} 污染了 python 学科"


# ─── 测试 9: 5 学科扩展总目标 50 道 ───────────────────────────────────

def test_5_subjects_extension_total_target_50(qdata):
    """5 学科扩展总设计目标 50 道 (5 学科 × 10 道/学科).

    拦截历史:
    - v0.55.0-d 新增: 5 学科迁移设计目标基线
    """
    target = qdata["metadata"]["subject_extensions"]["question_count_target"]
    total_target = sum(target.values())

    assert total_target == 50, \
        f"❌ 5 学科扩展总设计目标应为 50 (5 × 10), 实际={total_target}"


# ─── 测试 10: 5 学科架构审计 (5 断言) ────────────────────────────────

def test_5_subjects_extension_arch_audit(qdata):
    """5 学科架构综合审计 — 5 断言, 任何 1 个失败都阻止 CI 通过.

    拦截历史:
    - v0.55.0-d 综合审计: 防 5 学科扩展 slot 在未来重构中被破坏
    """
    metadata = qdata["metadata"]
    ext = metadata["subject_extensions"]
    target = ext["question_count_target"]
    current = ext["current_count"]

    # 断言 1: target 和 current 学科集一致
    assert set(target.keys()) == set(current.keys()), \
        "❌ target 和 current 学科集必须一致"

    # 断言 2: 5 学科扩展当前总数 = 0 (待 v0.56.0+)
    assert sum(current.values()) == 0, \
        f"❌ 5 学科扩展当前总题数应为 0 (v0.56.0+), 实际={sum(current.values())}"

    # 断言 3: 5 学科扩展目标总数 = 50
    assert sum(target.values()) == 50, \
        f"❌ 5 学科扩展目标总题数应为 50, 实际={sum(target.values())}"

    # 断言 4: 每学科 current ≤ target (防 current 超过 target 报错)
    for subj in target:
        assert current[subj] <= target[subj], \
            f"❌ {subj} 学科 current={current[subj]} 超过 target={target[subj]}"

    # 断言 5: metadata.subject='python_basics' (主学科)
    assert metadata["subject"] == "python_basics", \
        f"❌ metadata.subject 应='python_basics', 实际='{metadata['subject']}'"
