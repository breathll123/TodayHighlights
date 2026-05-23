import type { Block } from "@/api/types";

export function hasCollision(
  a: { grid_x: number; grid_y: number; col_span: number; row_span: number },
  b: { grid_x: number; grid_y: number; col_span: number; row_span: number }
): boolean {
  return (
    a.grid_x < b.grid_x + b.col_span &&
    a.grid_x + a.col_span > b.grid_x &&
    a.grid_y < b.grid_y + b.row_span &&
    a.grid_y + a.row_span > b.grid_y
  );
}

export function findAvailablePosition(
  blocks: Block[],
  colSpan: number,
  rowSpan: number
): { x: number; y: number } {
  for (let y = 0; y < 20; y++) {
    for (let x = 0; x <= 4 - colSpan; x++) {
      const candidate = { grid_x: x, grid_y: y, col_span: colSpan, row_span: rowSpan };
      const blocked = blocks.some((b) => hasCollision(candidate, b));
      if (!blocked) return { x, y };
    }
  }
  return { x: 0, y: blocks.length };
}

export function clampSize(
  colSpan: number,
  rowSpan: number
): { col: number; row: number } {
  return {
    col: Math.max(1, Math.min(4, colSpan)),
    row: Math.max(1, Math.min(6, rowSpan)),
  };
}

export const SIZE_PRESETS = [
  { label: "小卡片", icon: "□", col: 1, row: 1 },
  { label: "中方块", icon: "□□", col: 2, row: 1 },
  { label: "大卡片", icon: "□□ / □□", col: 2, row: 2 },
  { label: "宽横幅", icon: "□□□□", col: 4, row: 1 },
  { label: "全宽", icon: "□□□□ / □□□□", col: 4, row: 2 },
] as const;
