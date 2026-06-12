import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Block } from "../api/types";

const { toastError } = vi.hoisted(() => ({
  toastError: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    error: toastError,
  },
}));

vi.mock("../components/admin/CanvasBlock", () => ({
  CanvasBlock: ({ block }: { block: Block }) => <div>{block.title}</div>,
}));

vi.mock("react-grid-layout", () => ({
  default: ({
    children,
    onDragStop,
    onResizeStop,
  }: {
    children: ReactNode;
    onDragStop: (layout: unknown[], oldItem: null, newItem: object) => void;
    onResizeStop: (layout: unknown[], oldItem: null, newItem: object) => void;
  }) => (
    <div>
      <button
        type="button"
        onClick={() => onDragStop([], null, {
          i: "3",
          x: 0,
          y: 0,
          w: 2,
          h: 1,
        })}
      >
        finish drag
      </button>
      <button
        type="button"
        onClick={() => onResizeStop([], null, {
          i: "1",
          x: 0,
          y: 0,
          w: 2,
          h: 2,
        })}
      >
        finish resize
      </button>
      {children}
    </div>
  ),
  noCompactor: {},
  useContainerWidth: () => ({
    width: 800,
    containerRef: { current: null },
    mounted: true,
  }),
}));

import { CanvasEditor } from "../components/admin/CanvasEditor";

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

describe("CanvasEditor collision reflow", () => {
  beforeEach(() => {
    toastError.mockReset();
  });

  it("pushes the full collision chain after dragging to the top", () => {
    const onLayoutChange = vi.fn();
    const blocks = [
      block(1, 0, 0),
      block(2, 0, 1),
      block(3, 0, 2),
    ];

    render(
      <CanvasEditor
        blocks={blocks}
        onLayoutChange={onLayoutChange}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "finish drag" }));

    const next = onLayoutChange.mock.calls[0][0] as Block[];
    expect(next.find((item) => item.id === 3)?.grid_y).toBe(0);
    expect(next.find((item) => item.id === 1)?.grid_y).toBe(1);
    expect(next.find((item) => item.id === 2)?.grid_y).toBe(2);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("pushes colliding blocks after resize", () => {
    const onLayoutChange = vi.fn();
    const blocks = [
      block(1, 0, 0, 1, 1),
      block(2, 0, 1, 2, 1),
    ];

    render(
      <CanvasEditor
        blocks={blocks}
        onLayoutChange={onLayoutChange}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "finish resize" }));

    const next = onLayoutChange.mock.calls[0][0] as Block[];
    expect(next.find((item) => item.id === 1)).toMatchObject({
      col_span: 2,
      row_span: 2,
    });
    expect(next.find((item) => item.id === 2)?.grid_y).toBe(2);
    expect(toastError).not.toHaveBeenCalled();
  });
});
