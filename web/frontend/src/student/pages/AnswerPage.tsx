// v0.96: 答题页 (做题时收敛 — 题目 + 一句通俗化 + 提交; 5D/Bloom 收敛到"我在哪")
// 保留 v0.95.0 的 4 行为事件: hint / idle / goal_change / reflection
import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Icon from "../../components/ui/Icon";
import { Check, Lightbulb, MessageSquare, PartyPopper, X } from "../../components/ui/icons";
import { emitEvent, fetchQuestion, fetchReport, judgeAnswer, submitAnswer } from "../api";
import type { Question } from "../types";
import CodeEditor from "../components/CodeEditor";

const IDLE_SECONDS = 20;

// v0.97.2: 提交前自评 4 档语义化 (强制无默认) → 数值映射。
// 映射锚点与 ecos/cta/calibration_view.py SELF_CONFIDENCE_SCALE 保持同步;
// 值决定校准曲线的桶 (0.1 宽), 改映射 = 改桶语义, 须两侧同步。
const SELF_CONFIDENCE_OPTIONS: { label: string; value: number }[] = [
  { label: "肯定会对", value: 0.9 },
  { label: "应该会", value: 0.7 },
  { label: "不确定", value: 0.5 },
  { label: "可能不会", value: 0.3 },
];

// v0.99.2 (F-13): LCA 决策元数据中文标签 (只读展示, 不影响选题逻辑)
const LCA_INTERVENTION_LABELS: Record<string, string> = {
  EXPLANATORY: "讲解型",
  PRACTICE: "练习型",
  INQUIRY: "探究型",
  FEEDBACK: "反馈型",
  METACOGNITIVE: "元认知型",
};
const LCA_CLT_LABELS: Record<string, string> = {
  NOVICE: "新手（完整示例）",
  DEVELOPING: "发展中（部分示例）",
  PROFICIENT: "熟练（独立解题）",
  EXPERT: "专家（延迟反馈）",
};

export default function AnswerPage({ studentId }: { studentId: string }) {
  const [answer, setAnswer] = useState("");
  const [judging, setJudging] = useState(false);
  const [result, setResult] = useState<{
    correct: boolean;
    score: number;
    reasoning: string;
    theta?: Record<string, number>;
    misc_triggered?: boolean;
    misc_id?: string;
  } | null>(null);
  const [hintUsed, setHintUsed] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [reflection, setReflection] = useState("");
  const [reflectionSent, setReflectionSent] = useState(false);
  // v0.97.2: 提交前自评 (null = 未选, 强制无默认)
  const [selfConf, setSelfConf] = useState<number | null>(null);

  const goalBaseline = useRef<string | null>(null);
  const idleTimer = useRef<number | null>(null);
  const lastInput = useRef<number>(Date.now());
  // v0.99.0 (F-09): 题目加载→提交的时延计时 (evidence raw_response_time)
  const questionLoadedAt = useRef<number>(Date.now());

  const question = useQuery({
    queryKey: ["question", studentId],
    queryFn: () => fetchQuestion(studentId),
  });
  const report = useQuery({
    queryKey: ["report", studentId],
    queryFn: () => fetchReport(studentId),
  });

  const q: Question | undefined = question.data as Question | undefined;

  // goal_change: 题目 topic:bloom_layer 组合切换时 emit (新会话/退出 reset 基线)
  useEffect(() => {
    if (!q) return;
    const goalId = `${q.topic}:${q.bloom_layer}`;
    if (goalBaseline.current === null) {
      goalBaseline.current = goalId;
    } else if (goalBaseline.current !== goalId) {
      void emitEvent("goal_change", {
        student_id: studentId,
        old_goal_id: goalBaseline.current,
        new_goal_id: goalId,
      });
      goalBaseline.current = goalId;
    }
    // 新题目重置答题态
    setAnswer("");
    setResult(null);
    setHintUsed(false);
    setHint(null);
    setReflection("");
    setReflectionSent(false);
    setSelfConf(null);
    lastInput.current = Date.now();
    questionLoadedAt.current = Date.now();  // v0.99.0 (F-09)
  }, [q?.problem_id, studentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetIdle = useCallback(() => {
    lastInput.current = Date.now();
    if (idleTimer.current !== null) {
      window.clearTimeout(idleTimer.current);
    }
    if (!result) {
      idleTimer.current = window.setTimeout(() => {
        void emitEvent("idle", {
          student_id: studentId,
          idle_seconds: IDLE_SECONDS,
        });
      }, IDLE_SECONDS * 1000);
    }
  }, [studentId, result]);

  const onAnswerChange = (v: string) => {
    setAnswer(v);
    resetIdle();
  };

  const onHint = async () => {
    if (hintUsed || !q) return;
    setHintUsed(true);
    const res = await emitEvent("hint", {
      student_id: studentId,
      problem_id: q.problem_id,
      hint_level: 1,
    });
    const h = (res as { hint?: string } | undefined)?.hint;
    setHint(
      h ??
        "提示已记录。先通读题目、回顾这道题考查的概念，把思路写出来再作答。",
    );
  };

  const onSubmit = async () => {
    // F-04: 出结果后禁止重复提交 (二次点击会重复计 evidence/信念更新)
    if (!q || !answer.trim() || selfConf === null || result) return;
    setJudging(true);
    try {
      const jd = await judgeAnswer({
        student_id: studentId,
        problem_id: q.problem_id,
        student_answer: answer,
      });
      if (!jd.judged || jd.correct === undefined) {
        window.alert(jd.error ?? "AI 评判失败，请重试或跳过此题");
        return;
      }
      const res = await submitAnswer({
        student_id: studentId,
        problem_id: q.problem_id,
        skill_id: q.topic,
        correct: jd.correct,
        score: jd.score ?? (jd.correct ? 1 : 0),
        bloom_layer: q.bloom_layer,
        user_answer: answer,
        correct_answer: "",
        reasoning: jd.reasoning ?? "",
        self_confidence: selfConf,
        response_time: Math.max(0, Math.round((Date.now() - questionLoadedAt.current) / 1000)),
      });
      if (res && (res as { persisted?: boolean }).persisted === false) {
        window.alert("持久化失败，刷新后此题结果可能丢失");
      }
      setResult({
        correct: jd.correct,
        score: jd.score ?? (jd.correct ? 1 : 0),
        reasoning: jd.reasoning ?? "",
      });
      // F-07: 刷新通俗化备注 (report query 只在挂载时 fetch, 不刷会冻结在进页快照)
      void report.refetch();
      if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
    } catch (e) {
      window.alert((e as Error).message);
    } finally {
      setJudging(false);
    }
  };

  const onReflection = () => {
    if (!reflection.trim()) return;
    void emitEvent("reflection", {
      student_id: studentId,
      problem_id: q?.problem_id,
      reflection_text: reflection,
    });
    setReflectionSent(true);
  };

  const onNext = () => {
    void question.refetch();
  };

  if (question.isError) return <div className="error-box">题目加载失败（请稍后重试）</div>;
  if (question.isLoading) return <p className="muted">加载题目…</p>;
  if ((q as unknown as { done?: boolean }).done) {
    return (
      <div className="answer-page">
        <div className="card">
          <h2><Icon icon={PartyPopper} size={22} /> 所有题目已完成</h2>
          <p className="muted">
            去看看你的成长吧。
            <NavLink className="go-link" to="/growth">→ 成长</NavLink>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="answer-page">
      <div className="card">
        <div className="answer-meta">
          <span className="badge">{q!.bloom_layer}</span>
          <span className="badge">{q!.topic}</span>
          {q!.is_probe && <span className="badge" style={{ background: "#fdeee6", color: "#dc2626" }}>探针题</span>}
          {q!.is_warmup && <span className="badge cold">热身</span>}
        </div>
        <div className="prob">{q!.problem_text}</div>
        {report.data && (
          <div className="one-liner">
            <Icon icon={Lightbulb} size={16} /> {report.data.interpretation.overall}
          </div>
        )}
        <CodeEditor value={answer} onChange={onAnswerChange} />
        {/* v0.97.2: 提交前自评 (pre-outcome, 看到判分结果前选择才有校准意义) */}
        <div className="self-conf-row" style={{ margin: "10px 0" }}>
          <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
            提交前先猜一猜：这道题你觉得自己能做对吗？
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {SELF_CONFIDENCE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`chip${selfConf === opt.value ? " selected" : ""}`}
                onClick={() => setSelfConf(opt.value)}
                disabled={!!result}
              >
                {selfConf === opt.value ? <><Icon icon={Check} size={14} /> </> : null}{opt.label}
              </button>
            ))}
          </div>
        </div>
        <div className="btns" style={{ display: "flex", gap: 10 }}>
          <button className="amber" onClick={onHint} disabled={hintUsed}>
            {hintUsed ? (
              <>
                已请求提示 <Icon icon={Check} size={14} />
              </>
            ) : (
              <>
                <Icon icon={Lightbulb} size={16} /> 提示
              </>
            )}
          </button>
          <button
            onClick={onSubmit}
            disabled={judging || !answer.trim() || selfConf === null || !!result}
            title={selfConf === null ? "先选一个把握程度" : undefined}
          >
            {result ? "已提交 ✓" : selfConf === null ? "先选把握程度 → 提交" : judging ? "AI 评判中…" : "提交答案"}
          </button>
        </div>
        {hint && (
          <div className="hint-box">
            <div className="hint-title"><Icon icon={Lightbulb} size={16} /> 提示</div>
            <div className="hint-text">{hint}</div>
          </div>
        )}
        {/* v0.99.2 (F-13): LCA 干预决策只读展示（试点观测用; 后端 passthrough 元数据,
            不影响选题。折叠默认收起, 不打断答题流） */}
        {q!.lca_decision && (
          <details className="muted" style={{ marginTop: 10, fontSize: 13 }}>
            <summary style={{ cursor: "pointer" }}>系统决策（LCA）</summary>
            <div style={{ marginTop: 6, lineHeight: 1.8 }}>
              干预类型：{LCA_INTERVENTION_LABELS[q!.lca_decision.intervention_type] ?? q!.lca_decision.intervention_type}
              <br />
              目标层级：{q!.lca_decision.bloom_target} · 呈现级别：{LCA_CLT_LABELS[q!.lca_decision.clt_level] ?? q!.lca_decision.clt_level}
              <br />
              预期增益：{q!.lca_decision.expected_gain} · 预期风险：{q!.lca_decision.expected_risk}
            </div>
          </details>
        )}
      </div>

      {result && (
        <div className="feedback-box">
          <div className="verdict" style={{ color: result.correct ? "var(--ok)" : "var(--danger)" }}>
            {result.correct ? <><Icon icon={Check} size={18} /> 正确</> : <><Icon icon={X} size={18} /> 错误</>} · 得分 {(result.score * 100).toFixed(0)}%
          </div>
          <div className="reasoning">AI 评判：{result.reasoning || "—"}</div>
          <div className="refl-row">
            <textarea
              className="plain"
              value={reflection}
              onChange={(e) => setReflection(e.target.value)}
              disabled={reflectionSent}
              placeholder="课后反思（可选）：这道题你学到了什么？还有哪里不清楚？"
            />
            <div style={{ marginTop: 10, display: "flex", gap: 10 }}>
              <button className="amber" onClick={onReflection} disabled={reflectionSent || !reflection.trim()}>
                {reflectionSent ? (
                  <>
                    已记录 <Icon icon={Check} size={14} />
                  </>
                ) : (
                  <>
                    <Icon icon={MessageSquare} size={16} /> 记录反思
                  </>
                )}
              </button>
              <button className="green" onClick={onNext}>
                下一题 →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
