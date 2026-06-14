import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client", () => ({
  fetchHighlights: vi.fn().mockResolvedValue([]),
  fetchTopics: vi.fn().mockResolvedValue([]),
  fetchAdminTopics: vi.fn().mockResolvedValue([
    { id: 10, name: "股票", slug: "stocks", sort_order: 10 },
    { id: 20, name: "AI", slug: "ai", sort_order: 20 },
    { id: 30, name: "足球", slug: "football", sort_order: 30 },
  ]),
  fetchSources: vi.fn().mockResolvedValue([]),
  createSource: vi.fn(),
  triggerCrawl: vi.fn(),
  deleteSource: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue({
    total: 1,
    page: 1,
    page_size: 20,
    items: [
      {
        id: 1,
        source_id: 3,
        source_name: "雪球自选",
        trigger_type: "manual",
        status: "success",
        items_found: 5,
        items_saved: 5,
        error_message: "",
        log_excerpt: "",
        started_at: "2026-05-20T10:00:00",
        finished_at: "2026-05-20T10:01:00",
      },
    ],
  }),
  fetchPageBlocks: vi.fn().mockResolvedValue({ blocks: [] }),
  fetchBlocks: vi.fn().mockResolvedValue([]),
  createBlock: vi.fn(),
  updateBlock: vi.fn(),
  deleteBlock: vi.fn(),
  reorderBlocks: vi.fn(),
  generateBlockAIAnalysis: vi.fn(),
  fetchAIPromptTemplates: vi.fn().mockResolvedValue([]),
  createAIPromptTemplate: vi.fn(),
  updateAIPromptTemplate: vi.fn(),
  deleteAIPromptTemplate: vi.fn(),
}));

import { AdminSourcesPage } from "../pages/AdminSourcesPage";
import { AdminJobsPage } from "../pages/AdminJobsPage";

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

describe("AdminSourcesPage", () => {
  it("renders source management page", async () => {
    render(<AdminSourcesPage />, { wrapper: Wrapper });
    expect(await screen.findByText("数据源管理")).toBeInTheDocument();
    expect(screen.getByText("所属主题")).toBeInTheDocument();
    expect(screen.getByText("适配器")).toBeInTheDocument();
  });
});

describe("AdminJobsPage", () => {
  it("renders job log page with success status", async () => {
    render(<AdminJobsPage />, { wrapper: Wrapper });
    expect(await screen.findByText("任务日志")).toBeInTheDocument();
    expect(screen.getByText("成功")).toBeInTheDocument();
    expect(screen.getByText("雪球自选")).toBeInTheDocument();
  });
});
