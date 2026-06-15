import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client", () => ({
  default: {
    defaults: {
      headers: {
        common: {},
      },
    },
  },
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
  generateBlockAIAnalysis: vi.fn(),
  fetchAIPromptTemplates: vi.fn().mockResolvedValue([]),
  createAIPromptTemplate: vi.fn(),
  updateAIPromptTemplate: vi.fn(),
  deleteAIPromptTemplate: vi.fn(),
}));

import { SummaryPage } from "../pages/SummaryPage";
import { TopicPage } from "../pages/TopicPage";
import App from "../App";
import { sourceNameFor } from "../components/layout/GridRenderer";
import { fetchPageBlocks } from "../api/client";

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

describe("PublicLayout", () => {
  it("gives dashboard content and the overview header the full public width", async () => {
    render(<App />);

    const main = document.querySelector("main#main-content");
    expect(main).toHaveClass("max-w-[1680px]");

    const overview = await screen.findByLabelText("全局看板概览");
    expect(overview).toHaveClass("w-full", "max-w-full");
  });
});

describe("TopicPage", () => {
  it("renders block title and card content", async () => {
    render(<TopicPage />, { wrapper: Wrapper });
    expect(await screen.findByText("今日看点")).toBeInTheDocument();
    expect(screen.getByText("资金关注新能源")).toBeInTheDocument();
  });

  it("renders Longhu net amount and listing reason columns", async () => {
    vi.mocked(fetchPageBlocks).mockResolvedValueOnce({
      blocks: [
        {
          id: 3,
          page_route: "/topics/stocks",
          title: "东方财富-龙虎榜",
          sort_order: 0,
          source_type: "eastmoney_longhu",
          source_config: { display_fields: ["title", "percent", "score"] },
          display_style: "list",
          display_count: 30,
          sort_by: "default",
          enabled: true,
          created_at: "2026-06-15T10:00:00",
          updated_at: "2026-06-15T10:00:00",
          block_key: "stocks-longhu",
          col_span: 2,
          row_span: 1,
          grid_x: 0,
          grid_y: 0,
          status: "published",
          data: [
            {
              id: 101,
              title: "光库科技",
              symbols: ["300620"],
              percent: 19.999,
              net_amount: 1537055379,
              reason: "日涨幅达到15%的前5只证券",
              url: "https://quote.eastmoney.com/300620.html",
            },
            {
              id: 102,
              title: "测试净卖出",
              symbols: ["000001"],
              percent: -6.25,
              net_amount: -820000000,
              reason: "日跌幅偏离值达到7%的前5只证券",
              url: "https://quote.eastmoney.com/000001.html",
            },
          ],
        },
      ],
    });

    render(<TopicPage />, { wrapper: Wrapper });

    expect(await screen.findByText("东方财富-龙虎榜")).toBeInTheDocument();
    expect(screen.getAllByText("净买额")).not.toHaveLength(0);
    expect(screen.getAllByText("上榜原因")).not.toHaveLength(0);
    expect(screen.getAllByText("+15.4亿")).not.toHaveLength(0);
    expect(screen.getAllByText("-8.2亿")).not.toHaveLength(0);
    expect(screen.getAllByText("日涨幅达到15%的前5只证券")).not.toHaveLength(0);
  });
});

describe("FootballTopicPage", () => {
  it("renders a compact football overview with match metadata", async () => {
    vi.mocked(fetchPageBlocks).mockResolvedValueOnce({
      blocks: [
        {
          id: 2,
          page_route: "/topics/football",
          title: "今日赛程",
          sort_order: 0,
          source_type: "qiumiwu_matches",
          source_config: {},
          display_style: "list",
          display_count: 20,
          sort_by: "default",
          enabled: true,
          created_at: "2026-06-01T10:00:00",
          updated_at: "2026-06-01T10:00:00",
          block_key: "football-matches",
          col_span: 1,
          row_span: 1,
          grid_x: 0,
          grid_y: 0,
          status: "published",
          data: [
            {
              id: 1,
              league: "英超",
              status: 1,
              team_a: "阿森纳",
              team_b: "切尔西",
              start_time: "2026-06-01T20:30:00",
            },
          ],
        },
      ],
    });

    render(<TopicPage />, { wrapper: FootballWrapper });

    expect(await screen.findByText("今日赛程")).toBeInTheDocument();
    expect(screen.getByText("足球主题看板")).toBeInTheDocument();
    expect(screen.getByText("比分、赛程、积分榜")).toBeInTheDocument();
    expect(screen.getByText("足球 · 实时看板")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("1 个模块")).toBeInTheDocument();
    expect(screen.getByText(/\d{2}\/\d{2} \d{2}:\d{2} 更新/)).toBeInTheDocument();
    expect(screen.queryByText("当前主题")).not.toBeInTheDocument();
    expect(screen.queryByText("观测时间")).not.toBeInTheDocument();
    expect(screen.queryByText("平台状态")).not.toBeInTheDocument();
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
    ["eastmoney_indices", "新浪财经"],
    ["tonghuashun_news", "同花顺"],
  ])("maps %s to %s", (sourceType, sourceName) => {
    expect(sourceNameFor({}, sourceType)).toBe(sourceName);
  });

  it("uses item source before block source and falls back for unknown sources", () => {
    expect(sourceNameFor({ source: "hot_events" }, "topic")).toBe("雪球话题");
    expect(sourceNameFor({}, "unknown")).toBe("今日看点");
  });
});
