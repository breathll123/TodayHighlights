import axios from "axios";
import type { AdminUser, AIJobsStats, AIModelConfig, AIModelConfigWrite, AIOpsStats, AIGenerationJob, AIJobListResponse, AIPromptTemplate, AIPromptTemplateWrite, AITokenUsageDetail, AITokenUsageListResponse, AITopicSummaryResponse, AIUsageStats, AuthResponse, AuthUser, Block, BlockAIAnalysis, CrawlJob, Highlight, JobListResponse, MarketIndex, PageBlocksResponse, SetupStatus, Source, Topic } from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://localhost:8000",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.detail ?? err.message;
    const error = new Error(message) as Error & { status?: number };
    error.status = err.response?.status;
    return Promise.reject(error);
  }
);

export default api;

// --- Public APIs ---

export function fetchTopics(): Promise<Topic[]> {
  return api.get<Topic[]>("/api/public/topics").then((r) => r.data);
}

export function fetchHighlights(): Promise<Highlight[]> {
  return api.get<Highlight[]>("/api/public/highlights").then((r) => r.data);
}

export function fetchPageBlocks(route: string): Promise<PageBlocksResponse> {
  return api.get<PageBlocksResponse>(`/api/public/pages/${route}/blocks`).then((r) => r.data);
}

// --- Auth APIs ---

export function fetchSetupStatus(): Promise<SetupStatus> {
  return api.get<SetupStatus>("/api/auth/setup-status").then((r) => r.data);
}

export function bootstrapAdmin(data: { username: string; email: string; password: string }): Promise<AuthResponse> {
  return api.post<AuthResponse>("/api/auth/bootstrap-admin", data).then((r) => r.data);
}

export function loginUser(data: { login: string; password: string }): Promise<AuthResponse> {
  return api.post<AuthResponse>("/api/auth/login", data).then((r) => r.data);
}

export function fetchMe(): Promise<AuthUser> {
  return api.get<AuthUser>("/api/auth/me").then((r) => r.data);
}

// --- Admin APIs ---

export interface RawSourceOption { id: number; name: string }

export function fetchRawSources(): Promise<RawSourceOption[]> {
  return api.get<RawSourceOption[]>("/api/admin/sources?type=raw").then((r) => r.data);
}

export function fetchSources(): Promise<Source[]> {
  return api.get<Source[]>("/api/admin/sources").then((r) => r.data);
}

export function createSource(data: {
  topic_id: number;
  site: string;
  name: string;
  entry_url: string;
  cookie: string;
  enabled: boolean;
  crawl_interval_minutes: number;
}): Promise<Source> {
  return api.post<Source>("/api/admin/sources", data).then((r) => r.data);
}

export function updateSource(sourceId: number, data: { name?: string; entry_url?: string; cookie?: string; enabled?: boolean; crawl_interval_minutes?: number }): Promise<Source> {
  return api.put<Source>(`/api/admin/sources/${sourceId}`, data).then((r) => r.data);
}

export function triggerCrawl(sourceId: number): Promise<{ id: number; status: string }> {
  return api.post(`/api/admin/sources/${sourceId}/crawl`, {}).then((r) => r.data);
}

export function deleteSource(sourceId: number): Promise<{ deleted: boolean }> {
  return api.delete(`/api/admin/sources/${sourceId}`).then((r) => r.data);
}

export function fetchJobs(page = 1, pageSize = 20): Promise<JobListResponse> {
  return api.get<JobListResponse>("/api/admin/jobs", { params: { page, page_size: pageSize } }).then((r) => r.data);
}

// --- Block APIs ---

export function fetchBlocks(): Promise<Block[]> {
  return api.get<Block[]>("/api/admin/blocks").then((r) => r.data);
}

export function createBlock(data: Omit<Block, "id">): Promise<Block> {
  return api.post<Block>("/api/admin/blocks", data).then((r) => r.data);
}

export function updateBlock(id: number, data: Partial<Block>): Promise<Block> {
  return api.put<Block>(`/api/admin/blocks/${id}`, data).then((r) => r.data);
}

export function deleteBlock(id: number): Promise<void> {
  return api.delete(`/api/admin/blocks/${id}`).then((r) => r.data);
}

export function reorderBlocks(items: { id: number; sort_order: number }[]): Promise<void> {
  return api.patch("/api/admin/blocks/reorder", { items }).then((r) => r.data);
}

export function fetchAdminTopics(): Promise<Topic[]> {
  return api.get<Topic[]>("/api/admin/topics").then((r) => r.data);
}

export function createTopic(data: { name: string; slug: string; sort_order?: number; enabled?: boolean }): Promise<Topic> {
  return api.post<Topic>("/api/admin/topics", data).then((r) => r.data);
}

export function updateTopic(id: number, data: { name: string; slug: string; sort_order?: number; enabled?: boolean }): Promise<Topic> {
  return api.put<Topic>(`/api/admin/topics/${id}`, data).then((r) => r.data);
}

export function deleteTopic(id: number): Promise<{ deleted: boolean }> {
  return api.delete(`/api/admin/topics/${id}`).then((r) => r.data);
}

export function publishPage(route: string): Promise<{ published: boolean; blocks: number }> {
  return api.post(`/api/admin/pages/${route}/publish`).then((r) => r.data);
}

// --- AI Model APIs ---

export function fetchAIModels(): Promise<AIModelConfig[]> {
  return api.get<AIModelConfig[]>("/api/admin/ai-models").then((r) => r.data);
}

export function createAIModel(data: AIModelConfigWrite): Promise<AIModelConfig> {
  return api.post<AIModelConfig>("/api/admin/ai-models", data).then((r) => r.data);
}

export function updateAIModel(id: number, data: AIModelConfigWrite): Promise<AIModelConfig> {
  return api.put<AIModelConfig>(`/api/admin/ai-models/${id}`, data).then((r) => r.data);
}

export function setDefaultAIModel(id: number): Promise<AIModelConfig> {
  return api.post<AIModelConfig>(`/api/admin/ai-models/${id}/set-default`).then((r) => r.data);
}

// --- AI Job APIs ---

export function fetchAIJobs(params: { page?: number; page_size?: number; status?: string; trigger_type?: string; date_from?: string; date_to?: string } = {}): Promise<AIJobListResponse> {
  return api.get<AIJobListResponse>("/api/admin/ai-jobs", { params }).then((r) => r.data);
}

export function fetchAIJobsStats(): Promise<AIJobsStats> {
  return api.get<AIJobsStats>("/api/admin/ai-jobs/stats").then((r) => r.data);
}

export function retryAIJob(jobId: number): Promise<{ id: number; status: string; retry_count: number }> {
  return api.post(`/api/admin/ai-jobs/${jobId}/retry`).then((r) => r.data);
}

// --- Public AI APIs ---

export function fetchAITopicSummary(slug: string): Promise<AITopicSummaryResponse> {
  return api.get<AITopicSummaryResponse>(`/api/public/topics/${slug}/ai-summary`).then((r) => r.data);
}

export function fetchMarketIndices(): Promise<MarketIndex[]> {
  return api.get<MarketIndex[]>("/api/public/market-indices").then((r) => r.data);
}

// --- Block AI Analysis ---

export function generateBlockAIAnalysis(data: { page_route: string; block_id: number }): Promise<BlockAIAnalysis> {
  return api.post<BlockAIAnalysis>("/api/ai/block-analyses", data, { timeout: 120_000 }).then((r) => r.data);
}

// --- Admin Users & Usage ---

export function fetchAdminUsers(): Promise<AdminUser[]> {
  return api.get<AdminUser[]>("/api/admin/users").then((r) => r.data);
}

export function updateAdminUserStatus(id: number, status: "active" | "disabled"): Promise<{ id: number; status: string }> {
  return api.patch(`/api/admin/users/${id}`, { status }).then((r) => r.data);
}

export function fetchAITokenUsages(page = 1, pageSize = 20): Promise<AITokenUsageListResponse> {
  return api.get<AITokenUsageListResponse>("/api/admin/ai/token-usages", { params: { page, page_size: pageSize } }).then((r) => r.data);
}

export function fetchAITokenUsageDetail(id: number): Promise<AITokenUsageDetail> {
  return api.get<AITokenUsageDetail>(`/api/admin/ai/token-usages/${id}`).then((r) => r.data);
}

export function fetchAIUsageStats(): Promise<AIUsageStats> {
  return api.get<AIUsageStats>("/api/admin/ai/token-usages/stats").then((r) => r.data);
}

export function fetchAIOpsStats(): Promise<AIOpsStats> {
  return api.get<AIOpsStats>("/api/admin/ai/ops-stats").then((r) => r.data);
}

// --- Admin Prompt Templates ---

export function fetchAIPromptTemplates(): Promise<AIPromptTemplate[]> {
  return api.get<AIPromptTemplate[]>("/api/admin/ai-prompt-templates").then((r) => r.data);
}

export function createAIPromptTemplate(data: AIPromptTemplateWrite): Promise<AIPromptTemplate> {
  return api.post<AIPromptTemplate>("/api/admin/ai-prompt-templates", data).then((r) => r.data);
}

export function updateAIPromptTemplate(id: number, data: AIPromptTemplateWrite): Promise<AIPromptTemplate> {
  return api.put<AIPromptTemplate>(`/api/admin/ai-prompt-templates/${id}`, data).then((r) => r.data);
}

export function deleteAIPromptTemplate(id: number): Promise<{ deleted: boolean }> {
  return api.delete(`/api/admin/ai-prompt-templates/${id}`).then((r) => r.data);
}
