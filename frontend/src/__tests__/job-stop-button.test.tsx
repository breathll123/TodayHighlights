import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// 注意：vi.mock 工厂被提升到文件顶部，内部不能引用顶层变量；mock fn 在工厂内定义，
// 再通过 import 拿到同一个 mock 实例做断言。
vi.mock("../api/client", () => ({
  fetchJobs: vi.fn().mockResolvedValue({
    total: 1,
    page: 1,
    page_size: 20,
    stats: { total: 1, success: 0, failed: 0, running: 1, pending: 0 },
    items: [
      {
        id: 7,
        source_id: 3,
        source_name: "卡住的源",
        trigger_type: "manual",
        status: "running",
        items_found: 0,
        items_saved: 0,
        error_message: "",
        log_excerpt: "",
        started_at: "2026-06-25T10:00:00",
        finished_at: null,
      },
    ],
  }),
  fetchJobLogs: vi.fn().mockResolvedValue({
    job: { id: 7, status: "running", started_at: null, finished_at: null,
           items_found: 0, items_saved: 0, error_message: "" },
    entries: [], latest_id: 0, done: false,
  }),
  stopJob: vi.fn().mockResolvedValue({ id: 7, status: "stopped" }),
}));

import { AdminJobsPage } from "../pages/AdminJobsPage";
import { stopJob } from "../api/client";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminJobsPage stop button", () => {
  it("shows 停止 for a running job and calls stopJob on click", async () => {
    render(<AdminJobsPage />, { wrapper: Wrapper });
    expect(await screen.findByText("卡住的源")).toBeInTheDocument();

    const stopBtn = screen.getByRole("button", { name: "停止" });
    fireEvent.click(stopBtn);

    await waitFor(() => expect(stopJob).toHaveBeenCalledWith(7));
  });
});
