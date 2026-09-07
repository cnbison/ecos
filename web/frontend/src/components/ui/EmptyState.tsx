// v0.98.2-P0: 共享空状态组件 (教师/学生/家长三端统一)
interface EmptyStateProps {
  /** 可选 emoji 或图标占位 */
  icon?: string;
  title: string;
  description?: string;
}

export default function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="empty-state" role="status" aria-live="polite">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {description && <div className="empty-state-desc">{description}</div>}
    </div>
  );
}
