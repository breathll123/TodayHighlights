import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompactTable } from "../components/layout/CompactTable";
import { GridRenderer } from "../components/layout/GridRenderer";
import { LeaderboardTable } from "../components/layout/LeaderboardTable";
import { StandingsTable } from "../components/layout/StandingsTable";

const fields = [
  { key: "title", label: "模型", type: "text" as const },
  { key: "score", label: "智能指数", type: "number" as const },
];

describe("CompactTable rankings", () => {
  it("renders an optional rank column with top-three medals", () => {
    render(
      <CompactTable
        showRank
        data={[
          { id: 1, rank: 1, title: "Claude", score: 61 },
          { id: 2, rank: 4, title: "Gemini", score: 57 },
        ]}
        fields={fields}
      />,
    );

    expect(screen.getByText("排名")).toBeInTheDocument();
    expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
    expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  });

  it("uses restrained top-three glow hooks", () => {
    render(<CompactTable showRank data={[{ id: 1, rank: 1, title: "Claude", score: 61 }]} fields={fields} />);

    expect(screen.getByLabelText("第 1 名").closest("[data-rank-row]")).toHaveClass("rank-row-gold");
  });
});

it("renders medals in the AI multi-benchmark leaderboard", () => {
  render(
    <LeaderboardTable
      data={[
        { id: 1, title: "Claude", summary: "", rank: 1, HLE: "61" },
        { id: 2, title: "Gemini", summary: "", rank: 4, HLE: "57" },
      ]}
    />,
  );

  expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
  expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  expect(screen.getByText("AI 模型排行榜")).toBeInTheDocument();
});

it("renders medals in football standings but keeps fourth place plain", () => {
  render(
    <StandingsTable
      data={[
        { id: 1, title: "", summary: "", league: "英超", rank: 1, team: "阿森纳" },
        { id: 2, title: "", summary: "", league: "英超", rank: 4, team: "切尔西" },
      ]}
    />,
  );

  expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
  expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  expect(screen.queryByTestId("rank-medal-4")).not.toBeInTheDocument();
});

it("re-ranks the domestic AA intelligence view after filtering", () => {
  render(
    <GridRenderer
      isLoading={false}
      blocks={[
        {
          id: 1,
          title: "AI模型排行",
          source_type: "datalearner_aa_index",
          source_config: {},
          data: [
            { id: 1, title: "Claude", rank: 1, region: "global", score: 61, description: "综合指数" },
            { id: 2, title: "Qwen", rank: 7, region: "china", score: 56, description: "综合指数" },
            { id: 3, title: "Kimi", rank: 10, region: "china", score: 54, description: "综合指数" },
            { id: 4, title: "DeepSeek", rank: 17, region: "china", score: 52, description: "综合指数" },
          ],
        },
      ]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "国产排名" }));

  expect(screen.getByLabelText("第 1 名")).toBeInTheDocument();
  expect(screen.getByLabelText("第 2 名")).toBeInTheDocument();
  expect(screen.getByLabelText("第 3 名")).toBeInTheDocument();
  expect(screen.getAllByTestId(/^rank-medal-/)).toHaveLength(3);
});
