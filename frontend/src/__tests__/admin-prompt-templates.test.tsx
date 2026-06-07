import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AdminPromptTemplatesPage } from "@/pages/AdminPromptTemplatesPage";

vi.mock("@/api/client", () => ({
  fetchAIPromptTemplates: vi.fn().mockResolvedValue([
    {
      id: 1,
      topic_slug: "stocks",
      content_class: "news",
      topic_context: "关注政策信号",
      extra_forbidden: "不得给出买卖建议",
      enabled: true,
      template_version: 1,
      updated_by_user_id: 1,
      notes: "默认",
      created_at: "2026-06-07T00:00:00",
      updated_at: "2026-06-07T00:00:00",
    },
  ]),
  createAIPromptTemplate: vi.fn(),
  updateAIPromptTemplate: vi.fn(),
  deleteAIPromptTemplate: vi.fn(),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminPromptTemplatesPage", () => {
  it("renders prompt templates and constrained form fields", async () => {
    render(<AdminPromptTemplatesPage />, { wrapper: Wrapper });

    expect(screen.getByText("Prompt 模板")).toBeInTheDocument();
    expect(screen.getByLabelText("主题 slug")).toBeInTheDocument();
    expect(screen.getByLabelText("内容类型")).toBeInTheDocument();
    expect(screen.getByLabelText("领域背景")).toBeInTheDocument();
    expect(screen.getByLabelText("额外禁令")).toBeInTheDocument();
  });
});
