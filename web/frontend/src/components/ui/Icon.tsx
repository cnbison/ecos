// v0.98.3-P1: 统一尺寸与 stroke 的 Lucide 图标包装
import type { LucideIcon } from "lucide-react";

interface IconProps {
  icon: LucideIcon;
  size?: number;
  className?: string;
}

/** 统一尺寸与 stroke 的 Lucide 图标包装 */
export default function Icon({ icon: LucideIcon, size = 16, className }: IconProps) {
  return <LucideIcon size={size} strokeWidth={1.5} className={className} aria-hidden="true" />;
}
