import axios from "axios";
import type { Highlight, Topic, Source, CrawlJob, ModelSettings, Block, PageBlocksResponse } from "./types";

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

export function triggerCrawl(sourceId: number): Promise<{ id: number; status: string }> {
  return api.post(`/api/admin/sources/${sourceId}/crawl`, {}).then((r) => r.data);
}

export function fetchJobs(): Promise<CrawlJob[]> {
  return api.get<CrawlJob[]>("/api/admin/jobs").then((r) => r.data);
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
