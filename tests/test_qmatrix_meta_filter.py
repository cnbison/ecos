"""F-03 回归: cross_subject 元问题不入学生选题池 (v0.98.6, dogfood 2026-09-08).

拦截历史:
  - dogfood 发现新学生第一题必然是 PC-C01 (warmup 游标按 topic 字母序,
    cross_subject 排最前), 且元问题走代码题渲染 + 判分锚定硬编码 lbc001,
    对新学生无校准意义 → 方案 A: 选题池过滤 (web/api/qmatrix.py
    get_selectable_problems / is_meta_question)。

数据可见性保证: get_question_detail / get_all_problems 仍返回全量
Q 矩阵 (元问题只是不入池, 不从数据层删除)。
"""

from __future__ import annotations

from web.api.qmatrix import (
    get_all_problems,
    get_question_detail,
    get_selectable_problems,
    is_meta_question,
    select_question_for_student,
)


def _meta_probs():
    return [p for p in get_all_problems() if is_meta_question(p)]


class TestMetaQuestionDetection:
    def test_meta_count_is_10(self):
        """Q 矩阵应有 10 道元问题 (PC-C01-05 + PC-X01-05) — 数据没被误删."""
        ids = sorted(p["problem_id"] for p in _meta_probs())
        assert ids == [
            "PC-C01", "PC-C02", "PC-C03", "PC-C04", "PC-C05",
            "PC-X01", "PC-X02", "PC-X03", "PC-X04", "PC-X05",
        ]

    def test_meta_detection_semantics(self):
        """判据是 cross_subject topic, 不是 c_dimension_type 字段.

        PB-C* 系列 (调试题等 20 道) 带 c_dimension_type 但有真实题目
        上下文, 必须留在选题池 (v0.98.6 实现时测试先抓出过判据过宽).
        """
        assert is_meta_question({"topic": "cross_subject"})
        assert not is_meta_question({"c_dimension_type": "self_evaluation"})
        assert not is_meta_question({"topic": "python.loops", "c_dimension_type": "调试题"})

    def test_pb_c_questions_stay_in_pool(self):
        """PB-C* 有真实题目上下文, 不受 F-03 过滤影响."""
        selectable_ids = {p["problem_id"] for p in get_selectable_problems()}
        pb_c = [p["problem_id"] for p in get_all_problems()
                if p["problem_id"].startswith("PB-C")]
        assert pb_c, "PB-C 系列应存在"
        for pid in pb_c:
            assert pid in selectable_ids, f"{pid} 有真实上下文, 不应被过滤"


class TestSelectionPoolExcludesMeta:
    def test_selectable_pool_excludes_meta(self):
        selectable_ids = {p["problem_id"] for p in get_selectable_problems()}
        for p in _meta_probs():
            assert p["problem_id"] not in selectable_ids

    def test_warmup_first_question_is_not_meta(self):
        """F-03 直接场景: 新学生 warmup 首题不再必然是 PC-C01."""
        q = select_question_for_student(answered_ids=set(), is_warmup=True, student_id="f03_warmup_a")
        assert q is not None
        assert not is_meta_question(q)

    def test_warmup_never_serves_meta_across_rotation(self):
        """warmup 游标轮完一圈也不会出元问题."""
        answered: set[str] = set()
        for _ in range(20):
            q = select_question_for_student(
                answered_ids=answered, is_warmup=True, student_id="f03_warmup_b"
            )
            assert q is not None, "选题池不应在答完 20 题前耗尽"
            assert not is_meta_question(q)
            answered.add(q["problem_id"])

    def test_adaptive_and_legacy_paths_exclude_meta(self):
        """自适应 + legacy 随机路径同样不出元问题."""
        cov = [0.1] * 5
        for _ in range(10):
            q_adaptive = select_question_for_student(
                answered_ids=set(), theta_mean=[0.0] * 5, theta_cov_diag=cov,
            )
            q_legacy = select_question_for_student(answered_ids=set())
            assert not is_meta_question(q_adaptive)
            assert not is_meta_question(q_legacy)


class TestDataVisibilityPreserved:
    def test_question_detail_still_serves_meta(self):
        """数据消费方 (教师端统计/报告) 仍能看到元问题全量数据."""
        prob = get_question_detail("PC-C01")
        assert prob is not None
        assert prob["c_dimension_type"] == "self_evaluation"
