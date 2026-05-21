import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { SummaryPage } from "../pages/SummaryPage";
import { StockTopicPage } from "../pages/StockTopicPage";

function Wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SummaryPage", () => {
  it("renders highlight cards", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            title: "资金关注新能源",
            summary: "新能源板块热度上升。",
            related_symbols_json: [],
            tags_json: ["资金"],
            score: 82,
            is_pinned: false,
            created_at: "2026-05-20T10:00:00",
          },
        ]),
    });

    render(<SummaryPage />, { wrapper: Wrapper });

    expect(await screen.findByText("资金关注新能源")).toBeInTheDocument();
    expect(screen.getByText("新能源板块热度上升。")).toBeInTheDocument();
  });
});

describe("StockTopicPage", () => {
  it("renders highlight cards with symbols", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            title: "新能源板块午后走强",
            summary: "资金关注度明显提升。",
            related_symbols_json: ["宁德时代", "比亚迪"],
            tags_json: ["新能源"],
            score: 90,
            is_pinned: true,
            created_at: "2026-05-20T10:00:00",
          },
        ]),
    });

    render(<StockTopicPage />, { wrapper: Wrapper });

    expect(await screen.findByText("新能源板块午后走强")).toBeInTheDocument();
    expect(screen.getByText("宁德时代")).toBeInTheDocument();
    expect(screen.getByText("置顶")).toBeInTheDocument();
  });
});
