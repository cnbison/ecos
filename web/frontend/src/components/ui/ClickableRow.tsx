// v0.98.2-P0: 键盘可访问的表格行 (role=button + Enter/Space 触发)
import type { KeyboardEvent, ReactNode } from "react";

interface ClickableRowProps {
  children: ReactNode;
  onClick: () => void;
  className?: string;
  ariaLabel?: string;
}

export default function ClickableRow({
  children,
  onClick,
  className = "",
  ariaLabel,
}: ClickableRowProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <tr
      className={`clickable ${className}`.trim()}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      aria-label={ariaLabel}
    >
      {children}
    </tr>
  );
}
