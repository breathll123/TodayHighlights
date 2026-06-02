import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompactTable } from "../components/layout/CompactTable";
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
