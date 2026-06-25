// -*- coding: utf-8 -*-
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobLogModal } from "@/components/admin/JobLogModal";

// 模拟 API 客户端方法 fetchJobLogs，直接返回模拟的任务日志时序数据
vi.mock("@/api/client", () => ({
  fetchJobLogs: vi.fn().mockResolvedValue({
    job: {
      id: 1,
      status: "failed",
      started_at: "2026-06-25T10:00:00",
      finished_at: "2026-06-25T10:01:00",
      items_found: 0,
      items_saved: 0,
      error_message: "Boom: connection refused",
    },
    entries: [
      {
        id: 1,
        ts: "2026-06-25T10:00:00",
        level: "INFO",
        event: "crawl.started",
        category: "crawler",
        stage: "fetch",
        message: "抓取任务开始",
        fields: {}
      },
      {
        id: 2,
        ts: "2026-06-25T10:00:01",
        level: "WARNING",
        event: "upstream.failed",
        category: "crawler",
        stage: "status",
        message: "上游请求失败",
        fields: {
          status: 403,
          url: "https://x.test/api",
          duration_ms: 12.3,
          response_bytes: 88,
          response_preview: "forbidden"
        }
      },
      {
        id: 3,
        ts: "2026-06-25T10:00:02",
        level: "ERROR",
        event: "crawl.failed",
        category: "crawler",
        stage: "fetch",
        message: "抓取任务失败",
        fields: {
          error_type: "ConnectionError",
          error: "Boom: connection refused"
        }
      },
    ],
    latest_id: 3,
    done: true,
  }),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  // 包裹组件以提供 react-query 所需的 QueryClientContext
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

describe("JobLogModal", () => {
  it("renders the timeline, the failure block, and expands an HTTP row", async () => {
    // 渲染 JobLogModal，并传入模拟属性
    render(<JobLogModal jobId={1} open onOpenChange={() => {}} />, { wrapper: Wrapper });

    // 断言各项核心日志与属性均能被渲染出来
    expect(await screen.findByText("抓取任务开始")).toBeInTheDocument();
    expect(screen.getByText("上游请求失败")).toBeInTheDocument();
    // 错误原因概览区块展示正确的异常消息
    expect(screen.getByText(/connection refused/)).toBeInTheDocument();
    // HTTP 特殊行正常展示状态码与脱敏后的 URL
    expect(screen.getByText(/403/)).toBeInTheDocument();
    expect(screen.getByText(/x\.test\/api/)).toBeInTheDocument();

    // 模拟点击上游请求失败这行，由于其可展开，点击后应当渲染具体的 response preview 细节
    fireEvent.click(screen.getByText("上游请求失败"));
    await waitFor(() => expect(screen.getByText("forbidden")).toBeInTheDocument());
  });

  it("does not fetch when closed", () => {
    // 测试当弹窗未打开时，不应该向接口拉取或渲染日志数据
    render(<JobLogModal jobId={1} open={false} onOpenChange={() => {}} />, { wrapper: Wrapper });
    expect(screen.queryByText("抓取任务开始")).not.toBeInTheDocument();
  });
});
