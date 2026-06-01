import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client", () => ({
  fetchHighlights: vi.fn().mockResolvedValue([
    {
      id: 1,
      title: "资金关注新能源",
      summary: "新能源板块热度上升。",
      related_symbols_json: [],
      tags_json: ["资金"],
      score: 82,
      is_pinned: false,
      is_hidden: false,
      created_at: "2026-05-20T10:00:00",
    },
  ]),
  fetchTopics: vi.fn().mockResolvedValue([]),
  fetchSources: vi.fn().mockResolvedValue([]),
  createSource: vi.fn(),
  triggerCrawl: vi.fn(),
  deleteSource: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
  fetchModelSettings: vi.fn(),
  saveModelSettings: vi.fn(),
  updateHighlight: vi.fn(),
  deleteHighlight: vi.fn(),
  fetchPageBlocks: vi.fn().mockResolvedValue({
    blocks: [
      {
        id: 1,
        title: "今日看点",
        source_type: "topic",
        data: [
          {
            id: 1,
            title: "资金关注新能源",
            summary: "新能源板块热度上升。",
            tags_json: ["资金"],
            score: 82,
            is_pinned: false,
            created_at: "2026-05-20T10:00:00",
          },
        ],
      },
    ],
  }),
  fetchBlocks: vi.fn().mockResolvedValue([]),
  createBlock: vi.fn(),
  updateBlock: vi.fn(),
  deleteBlock: vi.fn(),
  reorderBlocks: vi.fn(),
}));

import { SummaryPage } from "../pages/SummaryPage";
import { StockTopicPage } from "../pages/StockTopicPage";
import { sourceNameFor } from "../components/layout/GridRenderer";

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

function FootballWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/topics/football"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SummaryPage", () => {
  it("renders block title and card content", async () => {
    render(<SummaryPage />, { wrapper: Wrapper });
    expect(await screen.findByText("今日看点")).toBeInTheDocument();
    expect(screen.getByText("资金关注新能源")).toBeInTheDocument();
    expect(screen.getByText("新能源板块热度上升。")).toBeInTheDocument();
    expect(screen.getByText("主题看点")).toBeInTheDocument();
    expect(screen.queryByText("Signal")).not.toBeInTheDocument();
    expect(screen.queryByText("82")).not.toBeInTheDocument();
  });
});

describe("StockTopicPage", () => {
  it("renders block title and card content", async () => {
    render(<StockTopicPage />, { wrapper: Wrapper });
    expect(await screen.findByText("今日看点")).toBeInTheDocument();
    expect(screen.getByText("资金关注新能源")).toBeInTheDocument();
  });
});

describe("FootballTopicPage", () => {
  it("names the active football data source", async () => {
    render(<StockTopicPage />, { wrapper: FootballWrapper });
    expect(await screen.findByText("足球主题看板")).toBeInTheDocument();
    expect(screen.getByText("全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。")).toBeInTheDocument();
  });
});

describe("sourceNameFor", () => {
  it.each([
    ["topic", "主题看点"],
    ["raw", "来源内容"],
    ["hot_stocks", "雪球热股"],
    ["hot_events", "雪球话题"],
    ["xueqiu_hot_cn", "雪球 A 股"],
    ["xueqiu_hot_hk", "雪球港股"],
    ["xueqiu_hot_us", "雪球美股"],
    ["screener", "行情筛选"],
    ["eastmoney_sectors", "东方财富"],
    ["eastmoney_industry", "东方财富"],
    ["eastmoney_longhu", "东方财富"],
    ["eastmoney_capital_flow", "东方财富"],
    ["eastmoney_announcements", "东方财富"],
    ["eastmoney_indices", "指数行情"],
    ["tonghuashun_news", "同花顺"],
  ])("maps %s to %s", (sourceType, sourceName) => {
    expect(sourceNameFor({}, sourceType)).toBe(sourceName);
  });

  it("uses item source before block source and falls back for unknown sources", () => {
    expect(sourceNameFor({ source: "hot_events" }, "topic")).toBe("雪球话题");
    expect(sourceNameFor({}, "unknown")).toBe("DataFlow");
  });
});
