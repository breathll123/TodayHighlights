import type { Block } from "@/api/types";

export interface GridRect {
  grid_x: number;
  grid_y: number;
  col_span: number;
  row_span: number;
}

export function hasCollision(
  a: GridRect,
  b: GridRect,
): boolean {
  return (
    a.grid_x < b.grid_x + b.col_span &&
    a.grid_x + a.col_span > b.grid_x &&
    a.grid_y < b.grid_y + b.row_span &&
    a.grid_y + a.row_span > b.grid_y
  );
}

function placeWithoutOverlap(block: Block, placed: GridRect[]): Block {
  let candidate = { ...block };

  while (true) {
    const collisions = placed.filter((item) => hasCollision(candidate, item));
    if (collisions.length === 0) return candidate;

    candidate = {
      ...candidate,
      grid_y: Math.max(...collisions.map((item) => item.grid_y + item.row_span)),
    };
  }
}

function reflowAfterAnchor(blocks: Block[], anchor: GridRect): Block[] {
  const placed: GridRect[] = [anchor];
  const resolved = new Map<number, Block>();
  const ordered = [...blocks].sort(
    (a, b) => a.grid_y - b.grid_y || a.grid_x - b.grid_x || a.id - b.id,
  );

  for (const block of ordered) {
    const next = placeWithoutOverlap(block, placed);
    placed.push(next);
    resolved.set(next.id, next);
  }

  return blocks.map((block) => resolved.get(block.id) ?? block);
}

export function reflowBlocks(
  blocks: Block[],
  activeId: number,
  target: GridRect,
): Block[] {
  const active = blocks.find((block) => block.id === activeId);
  if (!active) return [...blocks];

  const moved = { ...active, ...target };
  const followers = reflowAfterAnchor(
    blocks.filter((block) => block.id !== activeId),
    moved,
  );
  const byId = new Map(followers.map((block) => [block.id, block]));
  byId.set(activeId, moved);

  return blocks.map((block) => byId.get(block.id) ?? block);
}

export function insertBlockAtTop(
  blocks: Block[],
  colSpan: number,
  rowSpan: number,
): { blocks: Block[]; position: { x: 0; y: 0 } } {
  const position = { x: 0 as const, y: 0 as const };
  const anchor: GridRect = {
    grid_x: position.x,
    grid_y: position.y,
    col_span: colSpan,
    row_span: rowSpan,
  };

  return {
    blocks: reflowAfterAnchor(blocks, anchor),
    position,
  };
}

export function changedLayoutBlocks(previous: Block[], next: Block[]): Block[] {
  const previousById = new Map(previous.map((block) => [block.id, block]));

  return next.filter((block) => {
    const before = previousById.get(block.id);
    return before !== undefined && (
      before.grid_x !== block.grid_x ||
      before.grid_y !== block.grid_y ||
      before.col_span !== block.col_span ||
      before.row_span !== block.row_span
    );
  });
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
