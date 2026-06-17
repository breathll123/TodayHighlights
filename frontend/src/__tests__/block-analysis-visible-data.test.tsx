import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

vi.mock("../hooks/use-auth", () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

vi.mock("../api/client", () => ({
  generateBlockAIAnalysis: vi.fn().mockResolvedValue({
    id: 1,
    page_route: "/topics/football",
    block_id: 19,
    block_title: "联赛积分榜",
    status: "generated",
    summary_points: ["只分析当前联赛"],
    key_changes: [],
    risk_points: [],
    related_entities: [],
    evidence_refs: [],
    generated_by_model: "test",
    prompt_tokens: 1,
    completion_tokens: 1,
    total_tokens: 2,
    token_estimated: false,
    generated_at: null,
    expires_at: null,
  }),
}));

import { generateBlockAIAnalysis } from "../api/client";
import { GridRenderer } from "../components/layout/GridRenderer";

function renderGrid() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter initialEntries={["/topics/football"]}>
      <QueryClientProvider client={queryClient}>
        <GridRenderer
          isLoading={false}
          blocks={[
            {
              id: 19,
              page_route: "/topics/football",
              title: "联赛积分榜",
              source_type: "qiumiwu_standings",
              source_config: {},
              display_style: "table",
              display_count: 1000,
              col_span: 2,
              row_span: 1,
              data: [
                { id: 1, league: "英超", title: "阿森纳", team: "阿森纳", rank: 1, pts: "71" },
                { id: 2, league: "西甲", title: "皇马", team: "皇马", rank: 1, pts: "74" },
              ],
            },
          ]}
        />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

it("sends only the active standings tab data to block AI analysis", async () => {
  renderGrid();

  fireEvent.click(screen.getByRole("button", { name: "西甲" }));
  expect(screen.getByText("西甲 积分榜")).toBeInTheDocument();

  fireEvent.click(screen.getByText("AI 分析").closest("button")!);

  await waitFor(() => expect(generateBlockAIAnalysis).toHaveBeenCalled());

  expect(vi.mocked(generateBlockAIAnalysis).mock.calls[0][0]).toEqual({
    page_route: "/topics/football",
    block_id: 19,
    scope_label: "西甲",
    visible_data: [
      expect.objectContaining({
        league: "西甲",
        team: "皇马",
        pts: "74",
      }),
    ],
  });
});
