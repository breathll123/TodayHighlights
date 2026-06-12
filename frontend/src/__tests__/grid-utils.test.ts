import { describe, expect, it } from "vitest";

import type { Block } from "../api/types";
import {
  changedLayoutBlocks,
  hasCollision,
  insertBlockAtTop,
  reflowBlocks,
} from "../lib/grid-utils";

function block(
  id: number,
  grid_x: number,
  grid_y: number,
  col_span = 2,
  row_span = 1,
): Block {
  return {
    id,
    page_route: "/topics/stocks",
    title: `Block ${id}`,
    sort_order: id,
    source_type: "topic",
    source_config: { topic_id: 1 },
    display_style: "card",
    display_count: 5,
    sort_by: "created_at",
    enabled: true,
    created_at: "2026-06-12T00:00:00",
    updated_at: "2026-06-12T00:00:00",
    block_key: `block-${id}`,
    col_span,
    row_span,
    grid_x,
    grid_y,
    status: "draft",
  };
}

function expectNoOverlaps(blocks: Block[]) {
  for (let index = 0; index < blocks.length; index += 1) {
    for (let other = index + 1; other < blocks.length; other += 1) {
      expect(hasCollision(blocks[index], blocks[other])).toBe(false);
    }
  }
}

describe("grid reflow", () => {
  it("pushes a complete collision chain down", () => {
    const blocks = [
      block(1, 0, 0),
      block(2, 0, 1),
      block(3, 0, 2),
    ];

    const next = reflowBlocks(blocks, 3, {
      grid_x: 0,
      grid_y: 0,
      col_span: 2,
      row_span: 1,
    });

    expect(next.find((item) => item.id === 3)?.grid_y).toBe(0);
    expect(next.find((item) => item.id === 1)?.grid_y).toBe(1);
    expect(next.find((item) => item.id === 2)?.grid_y).toBe(2);
    expectNoOverlaps(next);
  });

  it("keeps blocks in unrelated columns unchanged", () => {
    const blocks = [
      block(1, 0, 0),
      block(2, 2, 0),
      block(3, 0, 2),
    ];

    const next = reflowBlocks(blocks, 3, {
      grid_x: 0,
      grid_y: 0,
      col_span: 2,
      row_span: 1,
    });

    expect(next.find((item) => item.id === 2)).toMatchObject({
      grid_x: 2,
      grid_y: 0,
    });
    expectNoOverlaps(next);
  });

  it("uses the active block resized dimensions during reflow", () => {
    const blocks = [
      block(1, 0, 0, 1, 1),
      block(2, 0, 1, 2, 1),
    ];

    const next = reflowBlocks(blocks, 1, {
      grid_x: 0,
      grid_y: 0,
      col_span: 2,
      row_span: 2,
    });

    expect(next.find((item) => item.id === 1)).toMatchObject({
      col_span: 2,
      row_span: 2,
    });
    expect(next.find((item) => item.id === 2)?.grid_y).toBe(2);
    expectNoOverlaps(next);
  });

  it("inserts a new block at the top without overlaps", () => {
    const blocks = [
      block(1, 0, 0),
      block(2, 0, 1),
      block(3, 2, 0),
    ];

    const result = insertBlockAtTop(blocks, 2, 1);

    expect(result.position).toEqual({ x: 0, y: 0 });
    expect(result.blocks.find((item) => item.id === 1)?.grid_y).toBe(1);
    expect(result.blocks.find((item) => item.id === 2)?.grid_y).toBe(2);
    expect(result.blocks.find((item) => item.id === 3)?.grid_y).toBe(0);
    expectNoOverlaps([
      ...result.blocks,
      block(-1, result.position.x, result.position.y, 2, 1),
    ]);
  });

  it("returns only blocks whose layout fields changed", () => {
    const previous = [
      block(1, 0, 0),
      block(2, 2, 0),
    ];
    const next = [
      { ...previous[0], grid_y: 1 },
      { ...previous[1], title: "Renamed outside layout" },
    ];

    expect(changedLayoutBlocks(previous, next).map((item) => item.id)).toEqual([1]);
  });
});
