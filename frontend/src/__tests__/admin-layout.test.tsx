import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Block } from "../api/types";

const {
  createBlock,
  deleteBlock,
  fetchBlocks,
  fetchAdminTopics,
  publishPage,
  updateBlock,
} = vi.hoisted(() => ({
  createBlock: vi.fn(),
  deleteBlock: vi.fn(),
  fetchBlocks: vi.fn(),
  fetchAdminTopics: vi.fn(),
  publishPage: vi.fn(),
  updateBlock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  createBlock,
  deleteBlock,
  fetchBlocks,
  fetchAdminTopics,
  publishPage,
  updateBlock,
}));

vi.mock("../components/admin/CanvasEditor", () => ({
  CanvasEditor: ({
    blocks,
    onLayoutChange,
  }: {
    blocks: Block[];
    onLayoutChange: (next: Block[]) => void;
  }) => (
    <button
      type="button"
      onClick={() => onLayoutChange([
        { ...blocks[0], grid_y: blocks[0].grid_y + 1 },
        blocks[1],
        ...blocks.slice(2),
      ])}
    >
      simulate layout
    </button>
  ),
}));

vi.mock("../components/admin/SizePresetPicker", () => ({
  SizePresetPicker: ({
    open,
    onSelect,
  }: {
    open: boolean;
    onSelect: (col: number, row: number) => void;
  }) => open ? (
    <button type="button" onClick={() => onSelect(2, 1)}>
      choose size
    </button>
  ) : null,
}));

import { AdminLayoutPage } from "../pages/AdminLayoutPage";

function block(id: number, grid_x: number, grid_y: number): Block {
  return {
    id,
    page_route: "/",
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
    col_span: 2,
    row_span: 1,
    grid_x,
    grid_y,
    status: "draft",
  };
}

function Wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminLayoutPage persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createBlock.mockResolvedValue({});
    deleteBlock.mockResolvedValue({});
    fetchAdminTopics.mockResolvedValue([
      { id: 10, name: "股票", slug: "stocks", sort_order: 10 },
      { id: 20, name: "AI", slug: "ai", sort_order: 20 },
      { id: 30, name: "足球", slug: "football", sort_order: 30 },
    ]);
    publishPage.mockResolvedValue({ published: true, blocks: 0 });
    updateBlock.mockImplementation((id: number, data: Partial<Block>) => (
      Promise.resolve({ id, ...data })
    ));
  });

  it("persists only blocks whose layout changed", async () => {
    fetchBlocks.mockResolvedValue([
      block(1, 0, 0),
      block(2, 2, 0),
    ]);

    render(<AdminLayoutPage />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByRole("button", { name: "simulate layout" }));

    await waitFor(() => {
      expect(fetchBlocks).toHaveBeenCalledTimes(2);
    });
    expect(updateBlock).toHaveBeenCalledTimes(1);
    expect(updateBlock).toHaveBeenCalledWith(1, {
      grid_x: 0,
      grid_y: 1,
      col_span: 2,
      row_span: 1,
    });
  });

  it("adds a new block at the bottom without moving existing blocks", async () => {
    fetchBlocks.mockResolvedValue([
      block(1, 0, 0), // rows 0–0
      block(2, 0, 1), // rows 1–1
      block(3, 0, 2), // rows 2–2
    ]);

    render(<AdminLayoutPage />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByRole("button", { name: "添加方块" }));
    fireEvent.click(screen.getByRole("button", { name: "choose size" }));

    await waitFor(() => {
      expect(createBlock).toHaveBeenCalledTimes(1);
    });
    // Existing blocks stay exactly where they are — nothing is pushed down.
    expect(updateBlock).not.toHaveBeenCalled();
    // The new block lands on a fresh row below the lowest block (bottom = 3).
    expect(createBlock).toHaveBeenCalledWith(expect.objectContaining({
      grid_x: 0,
      grid_y: 3,
      col_span: 2,
      row_span: 1,
      source_config: { topic_id: 10 },
    }));
  });

  it("uses the page topic id when adding a football block", async () => {
    const user = userEvent.setup();
    fetchBlocks.mockResolvedValue([]);

    render(<AdminLayoutPage />, { wrapper: Wrapper });
    const footballTab = await screen.findByRole("tab", { name: "足球页" });
    await user.click(footballTab);
    await waitFor(() => expect(footballTab).toHaveAttribute("aria-selected", "true"));
    await user.click(screen.getByRole("button", { name: "添加方块" }));
    await user.click(screen.getByRole("button", { name: "choose size" }));

    await waitFor(() => {
      expect(createBlock).toHaveBeenCalledWith(expect.objectContaining({
        page_route: "/topics/football",
        source_config: { topic_id: 30 },
      }));
    });
  });
});
