import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SkillRanking } from "../components/layout/SkillRanking";
import { FIELD_DEFS } from "../lib/field-defs";

const ALL_FIELDS = FIELD_DEFS.github_skills;

describe("SkillRanking", () => {
  it("renders name + owner, compact stars, links to GitHub, and shows the full description (truncated row + hover tooltip)", () => {
    const longDesc = "一个把任意代码仓库、SQL 模式、脚本、文档转成可查询知识图谱的 skill，支持多种 AI 编码助手";
    render(
      <SkillRanking
        data={[
          {
            id: 1,
            rank: 1,
            title: "graphify",
            owner: "safishamsi",
            summary: longDesc,
            url: "https://github.com/safishamsi/graphify",
            score: 71371,
          },
        ]}
        fields={ALL_FIELDS}
      />,
    );

    expect(screen.getByRole("link")).toHaveAttribute("href", "https://github.com/safishamsi/graphify");
    expect(screen.getByText("graphify")).toBeInTheDocument();
    expect(screen.getByText("safishamsi")).toBeInTheDocument();
    expect(screen.getByText("71.4k")).toBeInTheDocument();
    // Full text is rendered (not cut to 30 chars): the visible row + the hover tooltip.
    expect(screen.getAllByText(longDesc).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("tooltip")).toHaveTextContent(longDesc);
  });

  it("hides description and stars when those fields are deselected", () => {
    render(
      <SkillRanking
        data={[{ id: 1, title: "alpha", owner: "o", summary: "desc", url: "#", score: 100 }]}
        fields={[{ key: "title", label: "名称", type: "text" }]}
      />,
    );

    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.queryByText("desc")).not.toBeInTheDocument();
    expect(screen.queryByText("100")).not.toBeInTheDocument();
  });
});
