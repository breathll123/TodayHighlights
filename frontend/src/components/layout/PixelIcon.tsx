// -*- coding: utf-8 -*-
import React from "react";

export type PixelIconName = "play" | "coin" | "sparkle" | "tag";

const SPRITES: Record<PixelIconName, (c: string) => React.ReactNode> = {
  play: (c) => (
    <svg width="100%" height="100%" viewBox="0 0 20 20" shapeRendering="crispEdges" aria-hidden="true">
      <rect x="0" y="0" width="4" height="20" fill={c} />
      <rect x="4" y="4" width="4" height="12" fill={c} />
      <rect x="8" y="8" width="4" height="4" fill={c} />
    </svg>
  ),
  coin: (c) => (
    <svg width="100%" height="100%" viewBox="0 0 28 28" shapeRendering="crispEdges" aria-hidden="true">
      <rect x="12" y="0" width="4" height="4" fill={c} />
      <rect x="8" y="4" width="12" height="4" fill={c} />
      <rect x="4" y="8" width="20" height="4" fill={c} />
      <rect x="0" y="12" width="28" height="4" fill={c} />
      <rect x="4" y="16" width="20" height="4" fill={c} />
      <rect x="8" y="20" width="12" height="4" fill={c} />
      <rect x="12" y="24" width="4" height="4" fill={c} />
    </svg>
  ),
  sparkle: (c) => (
    <svg width="100%" height="100%" viewBox="0 0 20 20" shapeRendering="crispEdges" aria-hidden="true">
      <rect x="8" y="0" width="4" height="20" fill={c} />
      <rect x="0" y="8" width="20" height="4" fill={c} />
    </svg>
  ),
  tag: (c) => (
    <svg width="100%" height="100%" viewBox="0 0 20 20" shapeRendering="crispEdges" aria-hidden="true">
      <rect x="0" y="0" width="16" height="20" fill={c} />
      <rect x="16" y="4" width="4" height="16" fill={c} />
      <rect x="3" y="3" width="4" height="4" fill="#161C24" />
    </svg>
  ),
};

export function PixelIcon({ name, color, size = 18 }: { name: PixelIconName; color: string; size?: number }) {
  return <span style={{ display: "inline-flex", width: size, height: size }}>{SPRITES[name](color)}</span>;
}
