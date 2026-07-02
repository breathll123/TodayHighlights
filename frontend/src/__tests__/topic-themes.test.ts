// -*- coding: utf-8 -*-
import { describe, it, expect } from "vitest";
import { getTopicTheme } from "../lib/topic-themes";

describe("getTopicTheme", () => {
  it("已知主题映射到对应动画配置", () => {
    expect(getTopicTheme("/topics/football")?.key).toBe("football");
    expect(getTopicTheme("/topics/football")?.loadingText).toBe("足球数据加载中…");
    expect(getTopicTheme("/topics/ai")?.accent).toBe("#4DD0FF");
    expect(getTopicTheme("/topics/games")?.key).toBe("games");
    expect(getTopicTheme("/topics/stocks")?.loadingText).toBe("行情数据加载中…");
  });

  it("全局首页映射到雷达主题", () => {
    expect(getTopicTheme("/")?.key).toBe("home");
    expect(getTopicTheme("/")?.loadingText).toBe("全局看板加载中…");
  });

  it("未知主题回退到通用配置", () => {
    const theme = getTopicTheme("/topics/esports");
    expect(theme?.key).toBe("generic");
    expect(theme?.loadingText).toBe("看板数据加载中…");
  });

  it("非看板路由返回 null", () => {
    expect(getTopicTheme("/login")).toBeNull();
    expect(getTopicTheme("/admin/sources")).toBeNull();
    expect(getTopicTheme("/topics/football/extra")).toBeNull();
  });

  it("返回稳定引用且开场时长为 900ms", () => {
    expect(getTopicTheme("/topics/football")).toBe(getTopicTheme("/topics/football"));
    expect(getTopicTheme("/topics/football")?.openingDuration).toBe(900);
  });

  it("懒加载动画数据", async () => {
    const data: any = await getTopicTheme("/topics/football")!.loadAnimation();
    expect(Array.isArray(data.layers)).toBe(true);
  });
});
