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

  it("保留骨架屏打底", () => {
    const { container } = renderAt("/topics/football");
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThanOrEqual(4);
  });

  it("reduced motion 时不渲染动画，仅骨架屏与文案", async () => {
    reducedMotion = true;
    renderAt("/topics/football");
    expect(screen.getByText("足球数据加载中…")).toBeInTheDocument();
    await act(async () => {});
    expect(screen.queryByTestId("lottie-anim")).not.toBeInTheDocument();
  });
});
