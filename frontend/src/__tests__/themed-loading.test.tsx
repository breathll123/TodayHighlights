// -*- coding: utf-8 -*-
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ThemedLoading } from "../components/layout/ThemedLoading";
import "@testing-library/jest-dom";

let reducedMotion = false;

vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  return { ...actual, useReducedMotion: () => reducedMotion };
});

vi.mock("lottie-react", () => ({
  default: () => <div data-testid="lottie-anim" />,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemedLoading />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  reducedMotion = false;
});

describe("ThemedLoading", () => {
  it("足球主题显示专属文案与循环动画", async () => {
    renderAt("/topics/football");
    expect(screen.getByText("足球数据加载中…")).toBeInTheDocument();
    expect(await screen.findByTestId("lottie-anim")).toBeInTheDocument();
  });

  it("未知主题回退到通用文案", () => {
    renderAt("/topics/esports");
    expect(screen.getByText("看板数据加载中…")).toBeInTheDocument();
  });

  it("保留静态骨架屏打底，骨架框自身不闪烁", () => {
    const { container } = renderAt("/topics/football");
    expect(screen.getAllByTestId("block-skeleton").length).toBeGreaterThanOrEqual(4);
    // 加载动效只保留中央主题动画，背景骨架框不再 pulse，避免两套动画叠加
    expect(container.querySelectorAll(".animate-pulse").length).toBe(0);
  });

  it("reduced motion 时不渲染动画，仅骨架屏与文案", async () => {
    reducedMotion = true;
    renderAt("/topics/football");
    expect(screen.getByText("足球数据加载中…")).toBeInTheDocument();
    await act(async () => {});
    expect(screen.queryByTestId("lottie-anim")).not.toBeInTheDocument();
  });
});
