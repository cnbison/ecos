// v0.98.3-P1: emoji → Lucide 图标组件映射（兼容 P0 遗留的 string icon prop）。
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  BarChart,
  BookOpen,
  Brain,
  Check,
  CheckCircle,
  ClipboardList,
  Clock,
  Dna,
  Home,
  Info,
  Lightbulb,
  MapPin,
  MessageSquare,
  PartyPopper,
  PawPrint,
  Pencil,
  Settings,
  Speech,
  Target,
  TrendingUp,
  Upload,
  User,
  Users,
  UsersRound,
  X,
  XCircle,
} from "./icons";

const EMOJI_ICON_MAP: Record<string, LucideIcon> = {
  "📈": TrendingUp,
  "📊": BarChart,
  "📋": ClipboardList,
  "📚": BookOpen,
  "💡": Lightbulb,
  "🎯": Target,
  "📍": MapPin,
  "👤": User,
  "👥": Users,
  "✅": CheckCircle,
  "❌": XCircle,
  "✓": Check,
  "✗": X,
  "⚙️": Settings,
  "🎉": PartyPopper,
  "📤": Upload,
  "🕒": Clock,
  "🧠": Brain,
  "🧬": Dna,
  "✏️": Pencil,
  "🏠": Home,
  "⚠️": AlertTriangle,
  "ℹ️": Info,
  "🐾": PawPrint,
  "💭": MessageSquare,
  "👨‍👩‍👧": UsersRound,
  "👩": User,
  "👨": User,
  "👧": User,
};

/** emoji 或别名 → Lucide 组件；找不到时返回 fallback */
export function emojiToIcon(emoji: string, fallback: LucideIcon = Speech): LucideIcon {
  return EMOJI_ICON_MAP[emoji] ?? fallback;
}

/** 判断是否有对应图标 */
export function hasIcon(emoji: string): boolean {
  return emoji in EMOJI_ICON_MAP;
}
