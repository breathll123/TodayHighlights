import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
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
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });

    render(<AdminSourcesPage />, { wrapper: Wrapper });

    expect(await screen.findByText("数据源管理")).toBeInTheDocument();
  });
});

describe("AdminJobsPage", () => {
  it("renders job log page with success status", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 1,
            source_id: 1,
            trigger_type: "manual",
            status: "success",
            items_found: 5,
            items_saved: 5,
            error_message: "",
            log_excerpt: "",
            started_at: "2026-05-20T10:00:00",
            finished_at: "2026-05-20T10:01:00",
          },
        ]),
    });

    render(<AdminJobsPage />, { wrapper: Wrapper });

    expect(await screen.findByText("任务日志")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
  });
});
