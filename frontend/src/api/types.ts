export interface Highlight {
  id: number;
  title: string;
  summary: string;
  related_symbols_json: string[];
  tags_json: string[];
  score: number;
  is_pinned: boolean;
  is_hidden: boolean;
  created_at: string;
}

export interface Topic {
  id: number;
  name: string;
  slug: string;
  sort_order: number;
}

export interface Source {
  id: number;
  topic_id: number;
  site: string;
  name: string;
  entry_url: string;
  enabled: boolean;
  crawl_interval_minutes: number;
  last_crawled_at: string | null;
  has_cookie: boolean;
}

export interface CrawlJob {
  id: number;
  source_id: number;
  source_name: string;
  trigger_type: string;
  status: string;
  items_found: number;
  items_saved: number;
  error_message: string;
  log_excerpt: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobListResponse {
  total: number;
  page: number;
  page_size: number;
  items: CrawlJob[];
}

export interface ModelSettings {
  base_url: string;
  model: string;
  has_api_key: boolean;
}

export interface Block {
  id: number;
  page_route: string;
  title: string;
  sort_order: number;
  source_type: "topic" | "raw" | "hot_stocks" | "hot_events" | "xueqiu_hot_cn" | "xueqiu_hot_hk" | "xueqiu_hot_us" | "screener" | "eastmoney_sectors" | "eastmoney_longhu" | "eastmoney_industry" | "eastmoney_indices" | "eastmoney_capital_flow" | "eastmoney_announcements" | "tonghuashun_news" | "qiumiwu_matches" | "qiumiwu_standings" | "datalearner_leaderboard" | "datalearner_aa_index" | "aihot_news";
  source_config: Record<string, unknown>;
  display_style: "card" | "list" | "timeline";
  display_count: number;
  sort_by: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  block_key: string;
  col_span: number;
  row_span: number;
  grid_x: number;
  grid_y: number;
  status: "draft" | "published";
}

export interface PageBlocksResponse {
  blocks: (Block & { data: unknown[] })[];
}
