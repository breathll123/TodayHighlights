import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompactTable } from "../components/layout/CompactTable";

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
});
