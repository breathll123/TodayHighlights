// -*- coding: utf-8 -*-
import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { GameRankingList, GameDealGrid, GameReleaseList, GameItem } from "../components/layout/GameBlocks";
import "@testing-library/jest-dom";

const mockGames: GameItem[] = [
  {
    id: "1",
    title: "Terraria",
    rank: 1,
    provider: "steam",
    source: "Steam",
    external_id: "105600",
    url: "https://store.steampowered.com/app/105600/",
    cover_url: "https://example.com/cover1.jpg",
    current_price: 36,
    original_price: 36,
    discount_percent: 0,
    release_date: "2011-05-16",
  },
  {
    id: "2",
    title: "The Witcher 3",
    rank: 2,
    provider: "steam",
    source: "Steam",
    external_id: "292030",
    url: "https://store.steampowered.com/app/292030/",
    cover_url: "https://example.com/cover2.jpg",
    current_price: 25.6,
    original_price: 128,
    discount_percent: 80,
    discount_label: "-80%",
    release_date: "2015-05-18",
    summary: "在开放世界中扮演猎魔人，追踪怪物并做出关键选择。",
  },
];

const mockWeGame: GameItem[] = [
  {
    id: "2001918",
    title: "三角洲行动",
    rank: 1,
    provider: "wegame",
    source: "WeGame",
    external_id: "2001918",
    url: "https://www.wegame.com.cn/rail/game_detail.html?game_id=2001918",
    cover_url: "https://example.com/wegame.jpg",
    summary: "新一代战术射击品质标杆",
    e_game_name: "Delta Force",
    last_purchase_rank: 3,
  },
];

const mockDealOrbitGames: GameItem[] = [
  ...mockGames,
  {
    id: "3",
    title: "Hades",
    rank: 3,
    provider: "steam",
    source: "Steam",
    external_id: "1145360",
    url: "https://store.steampowered.com/app/1145360/",
    current_price: 40,
    original_price: 80,
    discount_percent: 50,
    discount_label: "-50%",
  },
  {
    id: "4",
    title: "Dead Cells",
    rank: 4,
    provider: "steam",
    source: "Steam",
    external_id: "588650",
    url: "https://store.steampowered.com/app/588650/",
    current_price: 32,
    original_price: 80,
    discount_percent: 60,
    discount_label: "-60%",
  },
  {
    id: "5",
    title: "Stardew Valley",
    rank: 5,
    provider: "steam",
    source: "Steam",
    external_id: "413150",
    url: "https://store.steampowered.com/app/413150/",
    current_price: 24,
    original_price: 48,
    discount_percent: 50,
    discount_label: "-50%",
  },
  {
    id: "6",
    title: "Celeste",
    rank: 6,
    provider: "wegame",
    source: "WeGame",
    external_id: "504230",
    url: "https://store.steampowered.com/app/504230/",
    current_price: 12,
    original_price: 60,
    discount_percent: 80,
    discount_label: "-80%",
  },
  {
    id: "7",
    title: "Balatro",
    rank: 7,
    provider: "wegame",
    source: "WeGame",
    external_id: "2379780",
    url: "https://store.steampowered.com/app/2379780/",
    current_price: 28,
    original_price: 42,
    discount_percent: 33,
    discount_label: "-33%",
  },
  {
    id: "8",
    title: "Slay the Spire",
    rank: 8,
    provider: "wegame",
    source: "WeGame",
    external_id: "646570",
    url: "https://store.steampowered.com/app/646570/",
    current_price: 20,
    original_price: 80,
    discount_percent: 75,
    discount_label: "-75%",
  },
  {
    id: "9",
    title: "Disco Elysium",
    rank: 9,
    provider: "wegame",
    source: "WeGame",
    external_id: "632470",
    url: "https://store.steampowered.com/app/632470/",
    current_price: 23.2,
    original_price: 116,
    discount_percent: 80,
    discount_label: "-80%",
  },
  {
    id: "10",
    title: "Hollow Knight",
    rank: 10,
    provider: "wegame",
    source: "WeGame",
    external_id: "367520",
    url: "https://store.steampowered.com/app/367520/",
    current_price: 24,
    original_price: 48,
    discount_percent: 50,
    discount_label: "-50%",
  },
];

describe("GameBlocks Components", () => {
  it("renders GameRankingList correctly and triggers onAnalysisDataChange", () => {
    const mockCallback = vi.fn();
    render(<GameRankingList data={mockGames} onAnalysisDataChange={mockCallback} />);

    // 检查游戏名是否成功呈现在屏幕上
    expect(screen.getByText("Terraria")).toBeInTheDocument();
    expect(screen.getByText("The Witcher 3")).toBeInTheDocument();

    // 检查价格与降价标签呈现
    expect(screen.getByText("¥36.00")).toBeInTheDocument();
    expect(screen.getByText("¥25.60")).toBeInTheDocument();
    expect(screen.getByText("-80%")).toBeInTheDocument();
    expect(screen.queryByText("在开放世界中扮演猎魔人，追踪怪物并做出关键选择。")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /The Witcher 3/i })).toHaveAttribute(
      "title",
      "The Witcher 3\n在开放世界中扮演猎魔人，追踪怪物并做出关键选择。",
    );

    // 验证 AI 数据回传回调成功触发，并且携带完整数据
    expect(mockCallback).toHaveBeenCalledWith(mockGames, "全部热门");
  });

  it("renders GameRankingList in WeGame mode", () => {
    const mockCallback = vi.fn();
    render(<GameRankingList data={mockWeGame} mode="wegame" onAnalysisDataChange={mockCallback} />);

    expect(screen.getByText("三角洲行动")).toBeInTheDocument();
    expect(screen.queryByText("新一代战术射击品质标杆")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /三角洲行动/i })).toHaveAttribute(
      "title",
      "三角洲行动\n新一代战术射击品质标杆",
    );
    expect(screen.getByText("WeGame")).toBeInTheDocument();
    expect(screen.getByText("上周 #3")).toBeInTheDocument();
    expect(screen.queryByText("发布日期未知")).not.toBeInTheDocument();
    expect(screen.queryByText("未定价")).not.toBeInTheDocument();
    expect(mockCallback).toHaveBeenCalledWith(mockWeGame, "WeGame榜单");
  });

  it("renders GameDealGrid correctly and triggers onAnalysisDataChange", () => {
    const mockCallback = vi.fn();
    render(<GameDealGrid data={mockGames} onAnalysisDataChange={mockCallback} />);

    // n=2 时占据前两个旅程槽位：谢幕位（下）+ hero（左一），两者都承载完整信息
    expect(screen.getByText("Terraria")).toBeInTheDocument();
    expect(screen.getByText("The Witcher 3")).toBeInTheDocument();
    expect(screen.getByText("¥36.00")).toBeInTheDocument();
    expect(screen.getByText("¥25.60")).toBeInTheDocument();
    expect(screen.getAllByText("-80%").length).toBeGreaterThan(0);       // 封面折扣角标（所有卡片保留）

    expect(mockCallback).toHaveBeenCalledWith(mockGames, "全部优惠");
  });

  it("GameDealGrid 菱形轮播：外侧进场、向内推进、上下谢幕后归一到中心", () => {
    render(<GameDealGrid data={mockDealOrbitGames} />);
    const orbit = screen.getByTestId("deal-orbit");
    expect(orbit.className).toContain("overflow-hidden");
    // 旅程槽位：下/上（谢幕）→ 左一/右一（hero）→ 左二三四（预告，越靠外越淡）
    expect(screen.getByLabelText("Steam 下侧折扣：Terraria")).toBeInTheDocument();
    expect(screen.getByLabelText("Steam 左一侧折扣：The Witcher 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Steam 左四侧折扣：Stardew Valley")).toBeInTheDocument();
    expect(screen.getByLabelText("上侧折扣：Celeste")).toBeInTheDocument();
    expect(screen.getByLabelText("右四侧折扣：Hollow Knight")).toBeInTheDocument();
    expect(screen.getAllByText("Steam").length).toBeGreaterThan(0);
    expect(screen.getAllByText("WeGame").length).toBeGreaterThan(0);
    expect(screen.getByTestId("deal-orbit-progress-line")).toBeInTheDocument();
    expect(screen.queryByText("折扣轮播")).not.toBeInTheDocument();
    expect(screen.queryByText("下一组")).not.toBeInTheDocument();
    expect(screen.queryByText("上一组")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "前进切换折扣游戏" }));

    // 前进一步：hero 移入谢幕位，后排各进一站，新卡从最外侧（左四/右四）进场
    expect(screen.getByLabelText("Steam 下侧折扣：The Witcher 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Steam 左一侧折扣：Hades")).toBeInTheDocument();
    expect(screen.getByLabelText("Steam 左四侧折扣：Terraria")).toBeInTheDocument();
    expect(screen.getByLabelText("上侧折扣：Balatro")).toBeInTheDocument();
  });

  it("悬停空白区域不暂停自动轮播，悬停游戏卡片才暂停", () => {
    vi.useFakeTimers();
    try {
      render(<GameDealGrid data={mockDealOrbitGames} />);
      expect(screen.getByLabelText("Steam 下侧折扣：Terraria")).toBeInTheDocument();

      // 悬停外层大框（空白处）：不应暂停，10s 后照常前进一站
      fireEvent.mouseEnter(screen.getByTestId("deal-orbit"));
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      expect(screen.getByLabelText("Steam 下侧折扣：The Witcher 3")).toBeInTheDocument();

      // 悬停一张游戏卡片：暂停，再过 10s 也不前进
      fireEvent.mouseEnter(screen.getByLabelText("Steam 下侧折扣：The Witcher 3"));
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      expect(screen.getByLabelText("Steam 下侧折扣：The Witcher 3")).toBeInTheDocument();
      expect(screen.queryByLabelText("Steam 下侧折扣：Hades")).not.toBeInTheDocument();

      // 移开鼠标：恢复轮播
      fireEvent.mouseLeave(screen.getByLabelText("Steam 下侧折扣：The Witcher 3"));
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      expect(screen.getByLabelText("Steam 下侧折扣：Hades")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("GameRankingList realtime 模式默认按当前在线排序，可切换今日峰值", () => {
    const realtimeData: GameItem[] = [
      {
        id: "r1",
        title: "Concurrent King",
        rank: 1,
        provider: "steam",
        source: "Steam",
        external_id: "730",
        url: "https://store.steampowered.com/app/730/",
        concurrent_in_game: 1000,
        peak_in_game: 1500,
      },
      {
        id: "r2",
        title: "Peak Master",
        rank: 2,
        provider: "steam",
        source: "Steam",
        external_id: "570",
        url: "https://store.steampowered.com/app/570/",
        concurrent_in_game: 900,
        peak_in_game: 2000,
      },
    ];
    const mockCallback = vi.fn();
    const { container } = render(
      <GameRankingList data={realtimeData} mode="realtime" onAnalysisDataChange={mockCallback} />,
    );

    // 默认按当前在线：Concurrent King 在前，主指标显示当前在线人数
    let titles = Array.from(container.querySelectorAll("h4")).map((el) => el.textContent);
    expect(titles[0]).toBe("Concurrent King");
    expect(screen.getByText("1,000")).toBeInTheDocument();
    expect(mockCallback).toHaveBeenLastCalledWith(expect.anything(), "实时热玩·当前在线");

    // 切到今日峰值：Peak Master 升到第一，回调范围标签同步
    fireEvent.click(screen.getByRole("button", { name: "今日峰值" }));
    titles = Array.from(container.querySelectorAll("h4")).map((el) => el.textContent);
    expect(titles[0]).toBe("Peak Master");
    expect(screen.getByText("2,000")).toBeInTheDocument();
    expect(mockCallback).toHaveBeenLastCalledWith(expect.anything(), "实时热玩·今日峰值");
  });

  it("renders GameReleaseList correctly and triggers onAnalysisDataChange", () => {
    const mockCallback = vi.fn();
    render(<GameReleaseList data={mockGames} onAnalysisDataChange={mockCallback} />);

    expect(screen.getByText("Terraria")).toBeInTheDocument();
    expect(screen.getByText("2011-05-16 发售")).toBeInTheDocument();

    expect(mockCallback).toHaveBeenCalledWith(mockGames, "最新发布");
  });
});
