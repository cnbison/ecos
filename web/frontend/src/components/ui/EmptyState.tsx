// v0.98.3-P1: 共享空状态组件 (图标支持 ReactNode / Lucide)
import type { ReactNode } from "react";

interface EmptyStateProps {
  /** 可选图标（Lucide 组件或任意 ReactNode） */
  icon?: ReactNode;
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
