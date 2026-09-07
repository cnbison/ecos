// v0.98.4-P1: 家长端 URL query 参数纯函数 helper
// 与 react-router useSearchParams 配合使用，把 selectedId 持久化为 ?student=<id>

export const STUDENT_QUERY_KEY = "student";

/** 从 query string 读取学生 id；空/空白返回 null */
export function readStudentParam(search: string): string | null {
  const value = new URLSearchParams(search).get(STUDENT_QUERY_KEY);
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed || null;
}

/** 判断 id 是否在学生列表中 */
export function isKnownStudent(
  id: string | null,
  students: readonly { student_id: string }[],
): boolean {
  if (!id) return false;
  return students.some((s) => s.student_id === id);
}

/** 构建用于 setSearchParams 的 query 对象；id 为 null 时返回空对象（清空参数） */
export function studentSearch(id: string | null): Record<string, string> {
  return id ? { [STUDENT_QUERY_KEY]: id } : {};
}
