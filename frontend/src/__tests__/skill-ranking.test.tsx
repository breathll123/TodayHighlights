import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SkillRanking } from "../components/layout/SkillRanking";
import { FIELD_DEFS } from "../lib/field-defs";

const ALL_FIELDS = FIELD_DEFS.github_skills;

describe("SkillRanking", () => {
  it("renders name, owner, truncated description, compact stars, and links to GitHub", () => {
    const longDesc = "这是一个非常非常非常非常非常非常长的中文描述用来测试三十字截断逻辑是否真正生效";
    render(
      <SkillRanking
        data={[
          {
            id: 1,
            rank: 1,
            title: "frontend-slides",
            owner: "zarazhangrui",
            summary: longDesc,
            url: "https://github.com/zarazhangrui/frontend-slides",
            score: 22630,
          },
        ]}
        fields={ALL_FIELDS}
      />,
    );

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "https://github.com/zarazhangrui/frontend-slides",
    );
    expect(screen.getByText("frontend-slides")).toBeInTheDocument();
    expect(screen.getByText("zarazhangrui")).toBeInTheDocument();
    expect(screen.getByText("22.6k")).toBeInTheDocument();
    expect(screen.getByText(`${longDesc.slice(0, 30)}…`)).toBeInTheDocument();
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
