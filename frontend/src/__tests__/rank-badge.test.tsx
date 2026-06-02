import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankBadge, rankRowTone } from "../components/layout/RankBadge";

describe("RankBadge", () => {
  it.each([1, 2, 3])("renders a medal and number for rank %s", (rank) => {
    render(<RankBadge rank={rank} />);

    expect(screen.getByLabelText(`第 ${rank} 名`)).toBeInTheDocument();
    expect(screen.getByTestId(`rank-medal-${rank}`)).toBeInTheDocument();
    expect(screen.getByText(String(rank))).toBeInTheDocument();
  });

  it("renders a plain number outside the top three", () => {
    render(<RankBadge rank={4} />);

    expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
    expect(screen.queryByTestId("rank-medal-4")).not.toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders a placeholder when rank is missing", () => {
    render(<RankBadge />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("returns restrained row tones only for the top three", () => {
    expect(rankRowTone(1)).toContain("rank-row-gold");
    expect(rankRowTone(2)).toContain("rank-row-silver");
    expect(rankRowTone(3)).toContain("rank-row-bronze");
    expect(rankRowTone(4)).toBe("");
  });
});
