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

export interface Block {
  id: number;
  page_route: string;
  title: string;
  sort_order: number;
  source_type: "topic" | "raw" | "hot_stocks" | "hot_events" | "xueqiu_hot_cn" | "xueqiu_hot_hk" | "xueqiu_hot_us" | "screener" | "eastmoney_sectors" | "eastmoney_longhu" | "eastmoney_industry" | "eastmoney_indices" | "eastmoney_capital_flow" | "eastmoney_announcements" | "tonghuashun_news" | "qiumiwu_matches" | "qiumiwu_fixtures" | "qiumiwu_standings" | "qiumiwu_schedule" | "datalearner_leaderboard" | "datalearner_aa_index" | "aihot_news";
  source_config: Record<string, unknown>;
  display_style: "card" | "list" | "timeline" | "schedule";
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

export interface AIModelConfig {
  id: number;
  name: string;
  base_url: string;
  model: string;
  is_default: boolean;
  enabled: boolean;
  notes: string;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIModelConfigWrite {
  name: string;
  base_url: string;
  model: string;
  api_key: string;
  is_default: boolean;
  enabled: boolean;
  notes: string;
}

export interface AIGenerationJob {
  id: number;
  job_type: string;
  trigger_type: string;
  topic_id: number | null;
  status: string;
  input_count: number;
  success_count: number;
  failed_count: number;
  error_message: string;
  log_excerpt: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AIJobListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AIGenerationJob[];
}

export interface AIJobsStats {
  today_succeeded: number;
  today_failed: number;
  today_processing: number;
  total_succeeded: number;
  total_failed: number;
  by_type: { job_type: string; count: number }[];
  by_trigger: { trigger_type: string; count: number }[];
}

export interface AIOpsStats {
  today_tokens: number;
  today_calls: number;
  active_models: number;
  today_succeeded: number;
  today_failed: number;
  daily_trend: { date: string; total_tokens: number; calls: number }[];
  by_model: { model_name: string; total_tokens: number; calls: number }[];
  job_status: { status: string; count: number }[];
}

export interface AITopicSummaryItem {
  title: string;
  reason: string;
  related: string[];
  risk: string;
  source_refs: number[];
}

export interface AITopicSummaryResponse {
  title: string;
  version: number;
  generated_at: string | null;
  items: AITopicSummaryItem[];
}

export interface BlockAIAnalysis {
  id: number;
  page_route: string;
  block_id: number;
  block_title: string;
  status: "processing" | "generated" | "failed";
  summary_points: string[];
  key_changes: string[];
  risk_points: string[];
  related_entities: string[];
  evidence_refs: { title: string; source?: string; published_at?: string | null; url?: string | null }[];
  generated_by_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  token_estimated: boolean;
  generated_at: string | null;
  expires_at: string | null;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
  status: "active" | "disabled";
  last_login_at: string | null;
  created_at: string;
}

export interface AITokenUsage {
  id: number;
  user_id: number | null;
  model_name: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated: boolean;
  request_status: string;
  created_at: string;
  block_title: string;
  topic: string;
  finished_at: string | null;
  job_status: string | null;
  job_error: string | null;
}

export interface AITokenUsageDetail extends AITokenUsage {
  prompt_text: string;
  completion_text: string;
}

export interface AITokenUsageListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AITokenUsage[];
}

export interface AIUsageStats {
  today_tokens: number;
  today_calls: number;
  active_models: number;
  daily_trend: { date: string; total_tokens: number; calls: number }[];
  by_model: { model_name: string; total_tokens: number; calls: number }[];
  by_topic: { topic_slug: string; total_tokens: number; calls: number }[];
}

export interface MarketIndexTrend {
  prev_close: number;
  high: number;
  low: number;
  date: string;
  points: { time: string; price: number }[];
}

export interface MarketIndex {
  code: string;
  name: string;
  current: number;
  change_pct: number;
  change_amount: number;
  volume: number;
  turnover: number;
  url: string;
  trend: MarketIndexTrend | null;
}

export interface AIItemEnhancement {
  status: string;
  summary: string;
  tags: string[];
  importance_score: number;
}

export function shouldShowAI(enrichment?: AIItemEnhancement): boolean {
  return Boolean(enrichment && enrichment.status === "generated" && enrichment.importance_score >= 40);
}

export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
  status: "active" | "disabled";
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export interface AIPromptTemplate {
  id: number;
  topic_slug: string;
  content_class: "news" | "rank" | "event";
  topic_context: string;
  extra_forbidden: string;
  enabled: boolean;
  template_version: number;
  updated_by_user_id: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface AIPromptTemplateWrite {
  topic_slug: string;
  content_class: "news" | "rank" | "event";
  topic_context: string;
  extra_forbidden: string;
  enabled: boolean;
  notes: string;
}
