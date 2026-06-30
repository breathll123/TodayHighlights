// -*- coding: utf-8 -*-
import { render, screen } from "@testing-library/react";
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
  },
];

const mockMostPlayed: GameItem[] = [
  {
    id: "730",
    title: "Counter-Strike 2",
    rank: 1,
    provider: "steam",
    source: "Steam",
    external_id: "730",
    url: "https://store.steampowered.com/app/730/",
    cover_url: "https://example.com/cs2.jpg",
    peak_in_game: 1234567,
    last_week_rank: 2,
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

    // 验证 AI 数据回传回调成功触发，并且携带完整数据
    expect(mockCallback).toHaveBeenCalledWith(mockGames, "全部热门");
  });

  it("renders GameRankingList in most played mode", () => {
    const mockCallback = vi.fn();
    render(<GameRankingList data={mockMostPlayed} mode="most_played" onAnalysisDataChange={mockCallback} />);

    expect(screen.getByText("Counter-Strike 2")).toBeInTheDocument();
    const peakText = screen.getByText("1,234,567");
    expect(peakText).toBeInTheDocument();
    expect(peakText.className).toContain("arcade-score");
    expect(screen.getByText("峰值在线")).toBeInTheDocument();
    expect(screen.getByText("上周 #2")).toBeInTheDocument();
    expect(mockCallback).toHaveBeenCalledWith(mockMostPlayed, "在线热玩");
  });

  it("renders GameDealGrid correctly and triggers onAnalysisDataChange", () => {
    const mockCallback = vi.fn();
    render(<GameDealGrid data={mockGames} onAnalysisDataChange={mockCallback} />);

    expect(screen.getByText("Terraria")).toBeInTheDocument();
    expect(screen.getByText("The Witcher 3")).toBeInTheDocument();
    expect(screen.getByText("¥25.60")).toBeInTheDocument();
    expect(screen.getAllByText("-80%").length).toBeGreaterThan(0);

    expect(mockCallback).toHaveBeenCalledWith(mockGames, "全部优惠");
  });

  it("renders GameReleaseList correctly and triggers onAnalysisDataChange", () => {
    const mockCallback = vi.fn();
    render(<GameReleaseList data={mockGames} onAnalysisDataChange={mockCallback} />);

    expect(screen.getByText("Terraria")).toBeInTheDocument();
    expect(screen.getByText("2011-05-16 发售")).toBeInTheDocument();

    expect(mockCallback).toHaveBeenCalledWith(mockGames, "最新发布");
  });
});
