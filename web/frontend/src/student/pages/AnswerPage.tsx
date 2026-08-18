// v0.96: 答题页 (做题时收敛 — 题目 + 一句通俗化 + 提交; 5D/Bloom 收敛到"我在哪")
// 保留 v0.95.0 的 4 行为事件: hint / idle / goal_change / reflection
import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { emitEvent, fetchQuestion, fetchReport, judgeAnswer, submitAnswer } from "../api";
import type { Question } from "../types";
import CodeEditor from "../components/CodeEditor";

const IDLE_SECONDS = 20;

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
  const [reflection, setReflection] = useState("");
  const [reflectionSent, setReflectionSent] = useState(false);

  const goalBaseline = useRef<string | null>(null);
  const idleTimer = useRef<number | null>(null);
  const lastInput = useRef<number>(Date.now());

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
    setReflection("");
    setReflectionSent(false);
    lastInput.current = Date.now();
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

  const onHint = () => {
    if (hintUsed || !q) return;
    setHintUsed(true);
    void emitEvent("hint", {
      student_id: studentId,
      problem_id: q.problem_id,
      hint_level: 1,
    });
  };

  const onSubmit = async () => {
    if (!q || !answer.trim()) return;
    setJudging(true);
    try {
      const jd = await judgeAnswer({
        student_id: studentId,
        problem_id: q.problem_id,
        user_answer: answer,
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
      });
      if (res && (res as { persisted?: boolean }).persisted === false) {
        window.alert("⚠️ 持久化失败，刷新后此题结果可能丢失");
      }
      setResult({
        correct: jd.correct,
        score: jd.score ?? (jd.correct ? 1 : 0),
        reasoning: jd.reasoning ?? "",
      });
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
          <h2>🎉 所有题目已完成</h2>
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
          <div className="one-liner">💡 {report.data.interpretation.overall}</div>
        )}
        <CodeEditor value={answer} onChange={onAnswerChange} />
        <div className="btns" style={{ display: "flex", gap: 10 }}>
          <button className="amber" onClick={onHint} disabled={hintUsed}>
            {hintUsed ? "已请求提示 ✓" : "💡 提示"}
          </button>
          <button onClick={onSubmit} disabled={judging || !answer.trim()}>
            {judging ? "AI 评判中…" : "提交答案"}
          </button>
        </div>
      </div>

      {result && (
        <div className="feedback-box">
          <div className="verdict" style={{ color: result.correct ? "var(--ok)" : "var(--danger)" }}>
            {result.correct ? "✅ 正确" : "❌ 错误"} · 得分 {(result.score * 100).toFixed(0)}%
          </div>
          <div className="reasoning">AI 评判：{result.reasoning || "—"}</div>
          <div className="refl-row">
            <textarea
              className="plain"
              value={reflection}
              onChange={(e) => setReflection(e.target.value)}
              disabled={reflectionSent}
              placeholder="💭 课后反思（可选）：这道题你学到了什么？还有哪里不清楚？"
            />
            <div style={{ marginTop: 10, display: "flex", gap: 10 }}>
              <button className="amber" onClick={onReflection} disabled={reflectionSent || !reflection.trim()}>
                {reflectionSent ? "已记录 ✓" : "记录反思"}
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
