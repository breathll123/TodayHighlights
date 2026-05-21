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
  trigger_type: string;
  status: string;
  items_found: number;
  items_saved: number;
  error_message: string;
  log_excerpt: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ModelSettings {
  base_url: string;
  model: string;
  has_api_key: boolean;
}
