// -*- coding: utf-8 -*-
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Star } from "lucide-react";
import { SectionHeading } from "../components/layout/SectionHeading";
import "@testing-library/jest-dom";

describe("SectionHeading skin", () => {
  it("renders the eyebrow + pixel icon when skinned", () => {
    render(
      <SectionHeading
        icon={Star}
        title="在线热玩榜"
        skin={{ accent: "#2BE07A", accentSoft: "rgba(43,224,122,0.08)", eyebrow: "NOW PLAYING", icon: "play" }}
      />
    );
    expect(screen.getByText("NOW PLAYING")).toBeInTheDocument();
    expect(screen.getByText("在线热玩榜")).toBeInTheDocument();
    // 像素图标用 svg；lucide 默认图标不应再渲染
    expect(screen.queryByTestId("section-heading-icon")).not.toBeInTheDocument();
  });

  it("keeps the lucide icon when not skinned (unchanged)", () => {
    render(<SectionHeading icon={Star} title="普通方块" />);
    expect(screen.getByTestId("section-heading-icon")).toBeInTheDocument();
  });
});
