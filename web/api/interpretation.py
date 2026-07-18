"""学习画像解读规则引擎——为 A 端(C 端学生/家长)提供自然语言分析。

v0.47.0 引入,Phase 4 W5+ A 端任务 4 落地(详见
discussions/2026-07-17-方向选择-A先C后.md)。

设计原则:
- 纯规则,无 LLM 调用 → 离线可用、零成本、可解释
- 输入:来自 /api/state 的 state dict
- 输出:分层解读(总评 / 5D / Bloom / TC / 轨迹 / 下一步建议)
- 阈值基于 theta 值、cov_diag、bloom_levels、tc_states

阈值表:
- 5D 强: theta >= 0.6,中: 0.3 ≤ theta < 0.6,弱: theta < 0.3
- 高置信: theta_confidence >= 0.5(样本量足够)
- TC 早期: progress < 0.3,进行中: 0.3 ≤ progress < 0.7,接近 liminal: progress >= 0.7
"""

from __future__ import annotations

from typing import Any, Dict, List

# ── 阈值常量 ──────────────────────────────────────────────────────────────
_THRESH_5D_STRONG = 0.6
_THRESH_5D_WEAK = 0.3
_THRESH_HIGH_CONF = 0.5
_THRESH_TC_PROGRESS = 0.3
_THRESH_TC_NEAR_LIMINAL = 0.7
_THRESH_TRAJ_DELTA_SIG = 0.15
_THRESH_OVERALL_CONF_LOW = 0.5
_THRESH_TRAJ_MIN_SAMPLE = 5  # 5 题为最小可解读样本

# ── 5D 维度中文标签 + 名称 ─────────────────────────────────────────────────
_DIM_NAMES = {
    "K": "概念理解",
    "P": "程序知识",
    "S": "策略知识",
    "C": "元认知",
    "X": "跨域迁移",
}

# ── Bloom 层名映射 ────────────────────────────────────────────────────────
_BLOOM_LAYER_NAMES = {
    "L1": "记忆 (REMEMBER)",
    "L2": "理解 (UNDERSTAND)",
    "L3": "应用 (APPLY)",
    "L4": "分析 (ANALYZE)",
    "L5": "评价 (EVALUATE)",
    "L6": "创造 (CREATE)",
}


def _level(theta: float) -> str:
    """5D 维度分档:strong / medium / weak。"""
    if theta >= _THRESH_5D_STRONG:
        return "strong"
    if theta >= _THRESH_5D_WEAK:
        return "medium"
    return "weak"


def _level_label(level: str) -> str:
    """中文档位名:强 / 中 / 弱。"""
    return {"strong": "强", "medium": "中", "weak": "弱"}.get(level, "未知")


# ── 5D 解读 ───────────────────────────────────────────────────────────────
def _interp_5d(state: Dict[str, Any]) -> Dict[str, Any]:
    """5 维度逐项解读:档位 + 置信度 + 评语。"""
    theta = state.get("theta", {}) or {}
    conf = state.get("theta_confidence", {}) or {}
    out: Dict[str, Any] = {}
    for dim in ("K", "P", "S", "C", "X"):
        v = float(theta.get(dim, 0.0))
        c = float(conf.get(dim, 0.0))
        lvl = _level(v)
        cn = _DIM_NAMES[dim]
        if lvl == "strong":
            tag = "稳定掌握"
            if c >= _THRESH_HIGH_CONF:
                comment = f"{cn}已稳定建立(θ={v:.2f},置信度高,样本量充足)"
            else:
                comment = f"{cn}已稳定建立(θ={v:.2f}),但样本量尚少,需更多题目验证"
        elif lvl == "medium":
            tag = "发展中"
            if c >= _THRESH_HIGH_CONF:
                comment = f"{cn}部分建立(θ={v:.2f}),处于上升通道"
            else:
                comment = f"{cn}部分建立(θ={v:.2f}),但样本量不足,趋势待观察"
        else:
            tag = "薄弱"
            comment = f"{cn}尚需补强(θ={v:.2f}),可能是当前主要薄弱环节之一"
        out[dim] = {
            "name": cn,
            "theta": round(v, 4),
            "confidence": round(c, 4),
            "level": lvl,
            "level_label": _level_label(lvl),
            "tag": tag,
            "comment": comment,
        }
    return out


# ── Bloom 解读 ────────────────────────────────────────────────────────────
def _interp_bloom(state: Dict[str, Any]) -> Dict[str, Any]:
    """Bloom 6 层解读:主导层定位 + 下一层 gap + 未探及层。"""
    bp = state.get("bloom_profile", {}) or {}
    levels = bp.get("bloom_levels", {}) or {}
    dom = bp.get("dominant", "—")
    dist = state.get("bloom_layer_distance", {}) or {}
    next_layer = dist.get("next")
    gap = dist.get("gap", 0.0)  # next - current(负=未跨越)

    layer_label = _BLOOM_LAYER_NAMES.get(dom, dom)

    # 未探及层(主层之上的更高层,值仍为 0.5 中性初值)
    unprobed = []
    layer_order = ["L1", "L2", "L3", "L4", "L5", "L6"]
    if dom in layer_order:
        dom_idx = layer_order.index(dom)
        for higher in layer_order[dom_idx + 1:]:
            if levels.get(higher, 0.5) == 0.5:
                unprobed.append(higher)

    parts: List[str] = [f"当前主导层 {layer_label},整体认知深度处于较浅阶段"]
    if next_layer:
        if gap is not None and gap < 0:
            parts.append(
                f"下一层 {next_layer} 掌握度仍低于当前层(gap={gap:+.3f}),尚未形成跨层跃迁"
            )
        else:
            parts.append(
                f"下一层 {next_layer} 已初步显现掌握(gap={gap:+.3f}),具备上推条件"
            )
    if unprobed:
        parts.append(f"更深的 {','.join(unprobed)} 层尚未探及,样本有限")
    return {
        "dominant": dom,
        "dominant_label": layer_label,
        "levels": {k: round(v, 4) for k, v in levels.items()},
        "next_layer": next_layer,
        "gap_to_next": round(gap, 4) if gap is not None else None,
        "unprobed_layers": unprobed,
        "comment": "。".join(parts) + "。",
    }


# ── TC 解读 ───────────────────────────────────────────────────────────────
def _interp_tc(state: Dict[str, Any]) -> Dict[str, Any]:
    """TC(threshold concept)状态解读:逐 topic 进展 + 整体分布。"""
    tcs = state.get("tc_states", []) or []
    out_topics: List[Dict[str, Any]] = []
    approaching: List[str] = []
    progressing: List[str] = []
    untouched: List[str] = []
    for tc in tcs:
        prog = float(tc.get("progress", 0.0))
        tid = tc.get("id", "")
        status = tc.get("status", "pre_liminal")
        if prog >= _THRESH_TC_NEAR_LIMINAL:
            tag = "接近 liminal"
            approaching.append(tid)
        elif prog >= _THRESH_TC_PROGRESS:
            tag = "进行中"
            progressing.append(tid)
        else:
            tag = "未触及"
            untouched.append(tid)
        out_topics.append({
            "id": tid,
            "progress": round(prog, 4),
            "status": status,
            "tag": tag,
        })

    if approaching:
        comment = (
            f"已触及 {len(tcs)} 个阈值概念,{','.join(approaching)} 接近 liminal,"
            f"持续练习可触发质变"
        )
    elif progressing:
        comment = (
            f"已触及 {len(tcs)} 个阈值概念,{','.join(progressing)} 已取得一定进展,"
            f"整体仍在前概念阶段"
        )
    elif untouched and len(untouched) == len(tcs):
        comment = "尚未深度触及任何阈值概念,建议加强相关基础练习"
    else:
        comment = f"已覆盖 {len(tcs)} 个阈值概念,均处于早期阶段"

    return {
        "topics": out_topics,
        "approaching_liminal": approaching,
        "progressing": progressing,
        "untouched": untouched,
        "comment": comment,
    }


# ── Trajectory 解读 ───────────────────────────────────────────────────────
def _interp_trajectory(state: Dict[str, Any]) -> Dict[str, Any]:
    """时间线趋势:首末 5D 差值 + 主要变化维度。"""
    traj = state.get("trajectory", []) or []
    if len(traj) < 2:
        return {
            "length": len(traj),
            "trend": "数据不足",
            "comment": f"样本量<2(当前 {len(traj)}),无法判断趋势,建议继续作答",
        }
    first = traj[0].get("theta_5d", [0] * 5)
    last = traj[-1].get("theta_5d", [0] * 5)
    if len(first) != 5 or len(last) != 5:
        return {
            "length": len(traj),
            "trend": "数据异常",
            "comment": "theta_5d 长度异常,无法解读",
        }
    dim_names = ["K", "P", "S", "C", "X"]
    diffs = [last[i] - first[i] for i in range(5)]
    max_idx = max(range(5), key=lambda i: abs(diffs[i]))
    max_diff = diffs[max_idx]
    sig_dims = [dim_names[i] for i in range(5) if abs(diffs[i]) >= _THRESH_TRAJ_DELTA_SIG]

    if max_diff >= _THRESH_TRAJ_DELTA_SIG:
        trend = f"{dim_names[max_idx]} 维度显著上升 (+{max_diff:.2f})"
    elif max_diff <= -_THRESH_TRAJ_DELTA_SIG:
        trend = f"{dim_names[max_idx]} 维度显著下降 ({max_diff:+.2f})"
    else:
        trend = "各维度整体平稳,无显著突变"

    comment = f"完成 {len(traj)} 次答题;{trend}。"
    if sig_dims:
        comment += f"主要变化维度: {','.join(sig_dims)}。"
    else:
        comment += "整体波动较小,建议加大探针密度或高难度题目刺激变化。"

    return {
        "length": len(traj),
        "first_timestamp": traj[0].get("timestamp"),
        "last_timestamp": traj[-1].get("timestamp"),
        "delta_5d": {dim_names[i]: round(diffs[i], 4) for i in range(5)},
        "trend": trend,
        "significant_dims": sig_dims,
        "comment": comment,
    }


# ── 总评 ──────────────────────────────────────────────────────────────────
def _interp_overall(
    state: Dict[str, Any],
    five_d: Dict[str, Any],
    bloom: Dict[str, Any],
    tc: Dict[str, Any],
    traj: Dict[str, Any],
) -> str:
    """学习画像总评(一段话,1-2 句覆盖全貌)。"""
    strong = [k for k, v in five_d.items() if v["level"] == "strong"]
    weak = [k for k, v in five_d.items() if v["level"] == "weak"]
    medium = [k for k, v in five_d.items() if v["level"] == "medium"]
    oc = state.get("overall_confidence", 0.0)
    answered = traj.get("length", 0)

    parts: List[str] = []
    if strong:
        parts.append(f"{','.join(strong)} 维度已建立稳定掌握")
    if medium:
        parts.append(f"{','.join(medium)} 维度处于发展期")
    if weak:
        parts.append(f"{','.join(weak)} 仍是主要薄弱环节")
    if not parts:
        parts.append("5 个维度均处于早期阶段")

    parts.append(f"已完成 {answered} 次答题,整体置信度 {oc:.2f}")
    parts.append(f"认知深度处于 {bloom['dominant_label']}")
    return ";".join(parts) + "。"


# ── 下一步建议 ────────────────────────────────────────────────────────────
def _next_steps(
    state: Dict[str, Any],
    five_d: Dict[str, Any],
    bloom: Dict[str, Any],
    tc: Dict[str, Any],
    traj: Dict[str, Any],
) -> List[str]:
    """3-5 条可操作建议(按优先级:补弱 → 跃层 → 拓概念 → 提样本)。"""
    steps: List[str] = []
    # 1) 最弱 5D 维度
    weak = sorted(
        [k for k, v in five_d.items() if v["level"] == "weak"],
        key=lambda d: five_d[d]["theta"],
    )
    if weak:
        d = weak[0]
        steps.append(
            f"优先补强【{_DIM_NAMES[d]}】维度——这是当前最薄弱环节,"
            f"可增加相关 {bloom['dominant']} 层练习题"
        )
    # 2) 中间档位中最低的(可选)
    if not weak:
        medium = sorted(
            [k for k, v in five_d.items() if v["level"] == "medium"],
            key=lambda d: five_d[d]["theta"],
        )
        if medium:
            d = medium[0]
            steps.append(
                f"推升【{_DIM_NAMES[d]}】维度向强档跃迁,可通过更高 Bloom 层题目带动"
            )
    # 3) Bloom 推进
    if bloom.get("next_layer") and (bloom.get("gap_to_next") or 0) < 0:
        steps.append(
            f"尝试 {bloom['next_layer']} 层题目,跨过当前主导层进入更深认知阶段"
        )
    # 4) TC 未触及
    if tc.get("untouched"):
        unt = tc["untouched"][:2]
        steps.append(
            f"开始接触 {','.join(unt)} 等阈值概念,避免后期一次性冲击"
        )
    # 5) 整体置信度低 / 样本不足
    oc = state.get("overall_confidence", 0.0)
    answered = traj.get("length", 0)
    if answered < _THRESH_TRAJ_MIN_SAMPLE:
        steps.append(
            f"样本量较小(当前 {answered} 题),建议至少完成 {_THRESH_TRAJ_MIN_SAMPLE} 题再下诊断"
        )
    elif oc < _THRESH_OVERALL_CONF_LOW:
        steps.append(
            f"整体置信度 {oc:.2f} 偏低,继续作答以提高画像稳定性(目标 ≥ 0.5)"
        )
    return steps[:5]


# ── 入口 ──────────────────────────────────────────────────────────────────
def build_interpretation(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成完整个人学习画像解读。

    参数:
        state: 来自 /api/state 的学生状态 dict
    返回:
        {
            "overall": str,        # 总评
            "five_d": {...},       # 5D 逐维解读
            "bloom": {...},        # Bloom 解读
            "tc": {...},           # TC 解读
            "trajectory": {...},   # 时间线趋势
            "next_steps": [...],   # 下一步建议(3-5 条)
        }
    """
    five_d = _interp_5d(state)
    bloom = _interp_bloom(state)
    tc = _interp_tc(state)
    traj = _interp_trajectory(state)
    overall = _interp_overall(state, five_d, bloom, tc, traj)
    next_steps = _next_steps(state, five_d, bloom, tc, traj)
    return {
        "overall": overall,
        "five_d": five_d,
        "bloom": bloom,
        "tc": tc,
        "trajectory": traj,
        "next_steps": next_steps,
    }
