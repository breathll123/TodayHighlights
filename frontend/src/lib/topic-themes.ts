// -*- coding: utf-8 -*-
// 主题看板的过场/加载动画注册表。key 与后台 topic slug 对应，
// 未收录的新主题自动落到 generic 兜底；换素材只需替换 assets/lottie 下的同名 JSON。

export interface TopicTheme {
  key: string;
  /** 过场遮罩光晕色 */
  accent: string;
  /** 加载态文案 */
  loadingText: string;
  /** 开场过场时长 ms */
  openingDuration: number;
  /** 懒加载 Lottie JSON（动态 import，不进首屏 bundle） */
  loadAnimation: () => Promise<object>;
}

const load = (importer: () => Promise<{ default: object }>) => () => importer().then((m) => m.default);

const OPENING_DURATION = 900;

const THEMES: Record<string, TopicTheme> = {
  home: {
    key: "home",
    accent: "#1EB9A8",
    loadingText: "全局看板加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/radar.json")),
  },
  stocks: {
    key: "stocks",
    accent: "#FF5A5A",
    loadingText: "行情数据加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/kline.json")),
  },
  football: {
    key: "football",
    accent: "#2BE07A",
    loadingText: "足球数据加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/football.json")),
  },
  ai: {
    key: "ai",
    accent: "#4DD0FF",
    loadingText: "AI 情报加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/robot.json")),
  },
  game: {
    key: "game",
    accent: "#9A7BFF",
    loadingText: "游戏数据加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/gamepad.json")),
  },
  generic: {
    key: "generic",
    accent: "#1EB9A8",
    loadingText: "看板数据加载中…",
    openingDuration: OPENING_DURATION,
    loadAnimation: load(() => import("@/assets/lottie/generic.json")),
  },
};

/** "/" → home；/topics/<slug> → 已知主题或 generic；其他（登录/管理页）→ null */
export function getTopicTheme(pathname: string): TopicTheme | null {
  if (pathname === "/") return THEMES.home;
  const match = pathname.match(/^\/topics\/([a-zA-Z0-9_-]+)$/);
  if (!match) return null;
  return THEMES[match[1]] ?? THEMES.generic;
}
