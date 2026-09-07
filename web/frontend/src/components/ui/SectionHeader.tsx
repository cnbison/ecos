// v0.98.2-P0: 共享区块标题 (标题 + 副标题 + 可选操作)
import type { ReactNode } from "react";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export default function SectionHeader({ title, subtitle, action }: SectionHeaderProps) {
  return (
    <div className="section-header">
      <div className="section-header-main">
        <h2>{title}</h2>
        {subtitle && <span className="section-header-sub">{subtitle}</span>}
      </div>
      {action && <div className="section-header-action">{action}</div>}
    </div>
  );
}
