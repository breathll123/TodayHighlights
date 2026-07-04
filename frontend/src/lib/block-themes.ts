// -*- coding: utf-8 -*-
import type { PixelIconName } from "@/components/layout/PixelIcon";

export interface BoardSkin {
  accent: string;
  accentSoft: string;
  eyebrow: string;
  icon: PixelIconName;
}

const ARCADE: Record<string, BoardSkin> = {
  game_charts_concurrent: { accent: "#2BE07A", accentSoft: "rgba(43,224,122,0.08)", eyebrow: "NOW PLAYING", icon: "play" },
  game_top_sellers: { accent: "#FFC53D", accentSoft: "rgba(255,197,61,0.08)", eyebrow: "TOP SELLERS", icon: "coin" },
  game_new_releases: { accent: "#4DD0FF", accentSoft: "rgba(77,208,255,0.08)", eyebrow: "NEW DROPS", icon: "sparkle" },
  game_specials: { accent: "#FF4D8D", accentSoft: "rgba(255,77,141,0.08)", eyebrow: "ON SALE", icon: "tag" },
};

const ARCADE_FALLBACK: BoardSkin = { accent: "#9A7BFF", accentSoft: "rgba(154,123,255,0.08)", eyebrow: "ARCADE", icon: "coin" };

export function getBlockSkin(theme: string | undefined, sourceType: string): BoardSkin | null {
  if (theme === "arcade") return ARCADE[sourceType] ?? ARCADE_FALLBACK;
  return null; // default / 未选主题 → 现有外观
}
