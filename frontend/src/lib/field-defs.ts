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
    { key: "score", label: "成交额", type: "number" },
    { key: "subtitle", label: "买卖", type: "text" },
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
  dongqiudi_matches: [
    { key: "title", label: "比赛", type: "text" },
    { key: "subtitle", label: "联赛", type: "text" },
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
  eastmoney_longhu: ["title", "percent", "score", "subtitle"],
  eastmoney_capital_flow: ["title", "percent", "score"],
  eastmoney_announcements: ["title", "subtitle"],
  tonghuashun_news: ["title", "subtitle"],
  dongqiudi_matches: ["title", "subtitle"],
};
