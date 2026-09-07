// v0.98.3-P1: 可折叠区块（标题 + 展开/折叠按钮 + 内容区）
import { useCallback, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown, ChevronUp } from "./icons";

interface CollapsibleSectionProps {
  title: string;
  subtitle?: string;
  children?: ReactNode;
  defaultExpanded?: boolean;
}

export default function CollapsibleSection({
  title,
  subtitle,
  children,
  defaultExpanded = false,
}: CollapsibleSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const toggle = useCallback(() => setExpanded((v) => !v), []);

  return (
    <div className={`collapsible-section${expanded ? " expanded" : ""}`}>
      <button
        type="button"
        className="collapsible-header"
        onClick={toggle}
        aria-expanded={expanded}
      >
        <span className="collapsible-title">{title}</span>
        {subtitle && <span className="collapsible-subtitle">{subtitle}</span>}
        <span className="collapsible-chevron">
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>
      {expanded && <div className="collapsible-body">{children}</div>}
    </div>
  );
}
