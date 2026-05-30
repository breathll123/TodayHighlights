import axios from "axios";
import type { Highlight, Topic, Source, CrawlJob, JobListResponse, ModelSettings, Block, PageBlocksResponse } from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://localhost:8000",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.detail ?? err.message;
    return Promise.reject(new Error(message));
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

export function fetchModelSettings(): Promise<ModelSettings> {
  return api.get<ModelSettings>("/api/admin/settings/model").then((r) => r.data);
}

export function saveModelSettings(data: {
  base_url: string;
  api_key: string;
  model: string;
}): Promise<{ saved: boolean; has_api_key: boolean }> {
  return api.put("/api/admin/settings/model", data).then((r) => r.data);
}

export function updateHighlight(
  id: number,
  data: { title: string; summary: string; is_pinned: boolean; is_hidden: boolean }
): Promise<{ id: number; review_status: string }> {
  return api.patch(`/api/admin/highlights/${id}`, data).then((r) => r.data);
}

export function deleteHighlight(highlightId: number): Promise<{ deleted: boolean }> {
  return api.delete(`/api/admin/highlights/${highlightId}`).then((r) => r.data);
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
