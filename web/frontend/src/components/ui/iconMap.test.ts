import { describe, expect, it } from "vitest";
import { hasIcon, emojiToIcon } from "./iconMap";
import { Speech, TrendingUp, UsersRound } from "./icons";

describe("emojiToIcon", () => {
  it("maps known emojis to Lucide components", () => {
    expect(emojiToIcon("📈")).toBe(TrendingUp);
    expect(emojiToIcon("👨‍👩‍👧")).toBe(UsersRound);
  });

  it("returns fallback for unknown emoji", () => {
    expect(emojiToIcon("🤖")).toBe(Speech);
  });

  it("allows custom fallback", () => {
    expect(emojiToIcon("🤖", TrendingUp)).toBe(TrendingUp);
  });
});

describe("hasIcon", () => {
  it("returns true for mapped emojis", () => {
    expect(hasIcon("📈")).toBe(true);
    expect(hasIcon("💡")).toBe(true);
  });

  it("returns false for unmapped emojis", () => {
    expect(hasIcon("🤖")).toBe(false);
  });
});
