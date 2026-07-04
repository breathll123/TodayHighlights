// -*- coding: utf-8 -*-
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { getBlockSkin } from "../lib/block-themes";
import { PixelIcon } from "../components/layout/PixelIcon";
import "@testing-library/jest-dom";

describe("block-themes", () => {
  it("returns null for default theme (unchanged look)", () => {
    expect(getBlockSkin("default", "game_top_sellers")).toBeNull();
    expect(getBlockSkin(undefined, "game_top_sellers")).toBeNull();
  });

  it("maps arcade game boards to per-board skins", () => {
    expect(getBlockSkin("arcade", "game_charts_concurrent")?.eyebrow).toBe("NOW PLAYING");
    expect(getBlockSkin("arcade", "game_top_sellers")?.icon).toBe("coin");
    expect(getBlockSkin("arcade", "game_specials")?.accent).toBe("#FF4D8D");
  });

  it("arcade falls back for a non-game block that opts in", () => {
    const skin = getBlockSkin("arcade", "topic");
    expect(skin).not.toBeNull();
    expect(skin?.icon).toBe("coin");
  });
});

describe("PixelIcon", () => {
  it("renders an svg for a known sprite", () => {
    render(<PixelIcon name="coin" color="#FFC53D" />);
    expect(document.querySelector("svg")).toBeInTheDocument();
  });
});
