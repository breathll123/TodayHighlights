/** Field metadata for each source_type. key = data field, type = number|text */

export interface FieldDef { key: string; label: string; type: "number" | "text" }

const STOCK_FIELDS: FieldDef[] = [
  { key: "title", label: "名称", type: "text" },
  { key: "percent", label: "涨跌", type: "number" },
  { key: "score", label: "热度", type: "number" },
];

const BOARD_FIELDS: FieldDef[] = [
  { key: "title", label: "板块", type: "text" },
  { key: "percent", label: "涨跌", type: "number" },
  { key: "subtitle", label: "领涨股", type: "text" },
];

export const FIELD_DEFS: Record<string, FieldDef[]> = {
  topic: [
    { key: "title", label: "标题", type: "text" },
    { key: "score", label: "热度", type: "number" },
  ],
  raw: [
    { key: "title", label: "名称", type: "text" },
    { key: "subtitle", label: "时间", type: "text" },
    { key: "score", label: "指标", type: "number" },
  ],
  hot_stocks: STOCK_FIELDS,
  hot_events: [
    { key: "title", label: "话题", type: "text" },
    { key: "score", label: "热度", type: "number" },
  ],
  xueqiu_hot_cn: STOCK_FIELDS,
  xueqiu_hot_hk: STOCK_FIELDS,
  xueqiu_hot_us: STOCK_FIELDS,
  screener: STOCK_FIELDS,
  eastmoney_sectors: BOARD_FIELDS,
  eastmoney_industry: BOARD_FIELDS,
  eastmoney_indices: [
    { key: "title", label: "指数", type: "text" },
    { key: "percent", label: "涨跌", type: "number" },
  ],
  eastmoney_longhu: [
    { key: "title", label: "名称", type: "text" },
    { key: "percent", label: "涨跌", type: "number" },
    { key: "net_amount", label: "净买额", type: "number" },
    { key: "reason", label: "上榜原因", type: "text" },
  ],
  eastmoney_capital_flow: [
    { key: "title", label: "名称", type: "text" },
    { key: "percent", label: "涨跌", type: "number" },
    { key: "score", label: "主力净流入", type: "number" },
  ],
  eastmoney_announcements: [
    { key: "title", label: "公告", type: "text" },
    { key: "subtitle", label: "日期", type: "text" },
  ],
  tonghuashun_news: [
    { key: "title", label: "标题", type: "text" },
    { key: "subtitle", label: "时间", type: "text" },
  ],
  qiumiwu_matches: [
    { key: "title", label: "比赛", type: "text" },
    { key: "subtitle", label: "联赛", type: "text" },
  ],
  qiumiwu_fixtures: [
    { key: "title", label: "比赛", type: "text" },
    { key: "subtitle", label: "时间", type: "text" },
  ],
  qiumiwu_standings: [
    { key: "title", label: "球队", type: "text" },
    { key: "subtitle", label: "战绩", type: "text" },
    { key: "score", label: "积分", type: "number" },
  ],
  datalearner_leaderboard: [
    { key: "title", label: "模型", type: "text" },
    { key: "subtitle", label: "公司", type: "text" },
    { key: "score", label: "HLE", type: "number" },
  ],
  datalearner_aa_index: [
    { key: "title", label: "模型", type: "text" },
    { key: "subtitle", label: "机构", type: "text" },
    { key: "score", label: "智能指数", type: "number" },
  ],
  artificial_analysis_ranking: [
    { key: "title", label: "模型", type: "text" },
    { key: "subtitle", label: "厂商", type: "text" },
    { key: "release", label: "Released", type: "text" },
    { key: "score", label: "评分", type: "number" },
  ],
  market_index_trends: [
    { key: "title", label: "指数", type: "text" },
    { key: "current", label: "点数", type: "number" },
    { key: "percent", label: "涨跌幅", type: "number" },
  ],
  aihot_news: [
    { key: "title", label: "标题", type: "text" },
    { key: "subtitle", label: "来源", type: "text" },
  ],
  github_skills: [
    { key: "title", label: "名称", type: "text" },
    { key: "summary", label: "描述", type: "text" },
    { key: "score", label: "Stars", type: "number" },
  ],
  game_top_sellers: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "rank", label: "排名", type: "number" },
    { key: "score", label: "价格", type: "number" },
  ],
  game_charts_concurrent: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "rank", label: "排名", type: "number" },
    { key: "concurrent_in_game", label: "当前玩家人数", type: "number" },
    { key: "peak_in_game", label: "今日峰值", type: "number" },
  ],
  game_specials: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "score", label: "现价", type: "number" },
    { key: "discount_percent", label: "折扣百分比", type: "number" },
  ],
  game_new_releases: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "release_date", label: "发售日期", type: "text" },
  ],
  game_wegame_popular: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "rank", label: "排名", type: "number" },
    { key: "summary", label: "简介", type: "text" },
  ],
  game_wegame_weekly_sales: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "rank", label: "排名", type: "number" },
    { key: "last_purchase_rank", label: "上周排名", type: "number" },
  ],
  game_wegame_discounts: [
    { key: "title", label: "游戏名称", type: "text" },
    { key: "rank", label: "排名", type: "number" },
    { key: "summary", label: "简介", type: "text" },
  ],
};

const DEFAULT_STOCK = ["title", "percent", "score"];
const DEFAULT_BOARD = ["title", "percent", "subtitle"];

export const DEFAULT_FIELDS: Record<string, string[]> = {
  topic: ["title", "score"],
  raw: ["title", "subtitle"],
  hot_stocks: DEFAULT_STOCK,
  hot_events: ["title", "score"],
  xueqiu_hot_cn: DEFAULT_STOCK,
  xueqiu_hot_hk: DEFAULT_STOCK,
  xueqiu_hot_us: DEFAULT_STOCK,
  screener: DEFAULT_STOCK,
  eastmoney_sectors: DEFAULT_BOARD,
  eastmoney_industry: DEFAULT_BOARD,
  eastmoney_indices: ["title", "percent"],
  eastmoney_longhu: ["title", "percent", "net_amount", "reason"],
  eastmoney_capital_flow: ["title", "percent", "score"],
  eastmoney_announcements: ["title", "subtitle"],
  tonghuashun_news: ["title", "subtitle"],
  qiumiwu_matches: ["title", "subtitle"],
  qiumiwu_fixtures: ["title", "subtitle"],
  qiumiwu_standings: ["title", "subtitle", "score"],
  datalearner_leaderboard: ["title", "subtitle", "score"],
  datalearner_aa_index: ["title", "subtitle", "score"],
  artificial_analysis_ranking: ["title", "subtitle", "release", "score"],
  market_index_trends: ["title", "current", "percent"],
  aihot_news: ["title", "subtitle"],
  github_skills: ["title", "summary", "score"],
  game_top_sellers: ["title", "rank", "score"],
  game_charts_concurrent: ["title", "rank", "concurrent_in_game", "peak_in_game"],
  game_specials: ["title", "score", "discount_percent"],
  game_new_releases: ["title", "release_date"],
  game_wegame_popular: ["title", "rank", "summary"],
  game_wegame_weekly_sales: ["title", "rank", "last_purchase_rank"],
  game_wegame_discounts: ["title", "rank", "summary"],
};

export function resolveDisplayFieldKeys(sourceType: string, configuredFields?: unknown): string[] {
  const configured = Array.isArray(configuredFields)
    ? configuredFields.filter((field): field is string => typeof field === "string")
    : [];

  if (
    sourceType === "eastmoney_longhu"
    && configured.some((field) => field === "score" || field === "subtitle")
  ) {
    return DEFAULT_FIELDS.eastmoney_longhu;
  }

  if (configured.length > 0) {
    return configured;
  }

  return DEFAULT_FIELDS[sourceType] || (FIELD_DEFS[sourceType] || []).map((field) => field.key);
}
