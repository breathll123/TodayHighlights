// -*- coding: utf-8 -*-
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { TopicTransitionOverlay } from "../components/layout/TopicTransitionOverlay";
import "@testing-library/jest-dom";

let reducedMotion = false;

// 只测本组件的触发/计时/路由逻辑，framer 的动画编排不在测试范围：
// AnimatePresence 直通、motion.div 退化为普通 div、useReducedMotion 可控。
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  motion: {
    div: ({ initial, animate, exit, transition, ...rest }: any) => <div {...rest} />,
  },
  useReducedMotion: () => reducedMotion,
}));

vi.mock("lottie-react", () => ({
  default: () => <div data-testid="lottie-anim" />,
}));

function Nav({ to }: { to: string }) {
  const navigate = useNavigate();
  return <button onClick={() => navigate(to)}>nav</button>;
}

function renderAt(path: string, navTo = "/topics/ai") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TopicTransitionOverlay />
      <Nav to={navTo} />
    </MemoryRouter>,
  );
}

// 冲刷动态 import（Lottie JSON 懒加载）的微任务链；fake timers 不影响微任务，
// 多排空几轮保证 animationData 已就位
const flushAsync = async () => {
  await act(async () => {
    for (let i = 0; i < 10; i += 1) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(0);
  });
};

beforeEach(() => {
  reducedMotion = false;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("TopicTransitionOverlay", () => {
  it("进入主题页时播放，openingDuration 后自动消失", async () => {
    renderAt("/topics/football");
    await flushAsync();
    expect(screen.getByTestId("topic-transition-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("lottie-anim")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.queryByTestId("topic-transition-overlay")).not.toBeInTheDocument();
  });

  it("非看板路由不触发", async () => {
    renderAt("/login");
    await flushAsync();
    expect(screen.queryByTestId("topic-transition-overlay")).not.toBeInTheDocument();
  });

  it("reduced motion 时完全跳过", async () => {
    reducedMotion = true;
    renderAt("/topics/football");
    await flushAsync();
    expect(screen.queryByTestId("topic-transition-overlay")).not.toBeInTheDocument();
  });

  it("快速切换主题时重置计时器", async () => {
    renderAt("/topics/football", "/topics/ai");
    await flushAsync();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    fireEvent.click(screen.getByText("nav"));
    await flushAsync();
    // 距首次播放已 500 + 500 > 900ms：若计时器没重置，此刻应已消失
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByTestId("topic-transition-overlay")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(screen.queryByTestId("topic-transition-overlay")).not.toBeInTheDocument();
  });
});
