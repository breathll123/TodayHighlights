import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CanvasBlock } from "../components/admin/CanvasBlock";
import type { Block } from "../api/types";

function makeBlock(): Block {
  return {
    id: 1,
    page_route: "/topics/stocks",
    title: "测试方块",
    sort_order: 1,
    source_type: "topic",
    source_config: { topic_id: 1 },
    display_style: "card",
    display_count: 5,
    sort_by: "created_at",
    enabled: true,
    created_at: "2026-06-12T00:00:00",
    updated_at: "2026-06-12T00:00:00",
    block_key: "block-1",
    col_span: 2,
    row_span: 1,
    grid_x: 0,
    grid_y: 0,
    status: "draft",
  };
}

describe("CanvasBlock action buttons", () => {
  it("fires onEdit / onDelete when the action buttons are clicked", () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(<CanvasBlock block={makeBlock()} onEdit={onEdit} onDelete={onDelete} />);

    fireEvent.click(screen.getByLabelText("编辑 测试方块"));
    expect(onEdit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText("删除 测试方块"));
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("keeps the action buttons out of the grid drag layer so touch taps survive", () => {
    render(<CanvasBlock block={makeBlock()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    const editButton = screen.getByLabelText("编辑 测试方块");

    // The buttons live inside the .drag-handle header, but must be marked
    // .no-drag so react-grid-layout's DraggableCore cancel selector leaves
    // their touchstart alone — otherwise the synthetic click is swallowed on
    // mobile/tablet and the edit panel never opens.
    expect(editButton.closest(".drag-handle")).not.toBeNull();
    expect(editButton.closest(".no-drag")).not.toBeNull();
  });
});
