import type { Highlight, Topic, Source, CrawlJob, ModelSettings } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchTopics(): Promise<Topic[]> {
  return getJson<Topic[]>("/api/public/topics");
}

export function fetchHighlights(): Promise<Highlight[]> {
  return getJson<Highlight[]>("/api/public/highlights");
}

export function fetchSources(): Promise<Source[]> {
  return getJson<Source[]>("/api/admin/sources");
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
  return postJson<Source>("/api/admin/sources", data);
}

export function triggerCrawl(sourceId: number): Promise<{ id: number; status: string }> {
  return postJson(`/api/admin/sources/${sourceId}/crawl`, {});
}

export function fetchJobs(): Promise<CrawlJob[]> {
  return getJson<CrawlJob[]>("/api/admin/jobs");
}

export function fetchModelSettings(): Promise<ModelSettings> {
  return getJson<ModelSettings>("/api/admin/settings/model");
}

export function saveModelSettings(data: {
  base_url: string;
  api_key: string;
  model: string;
}): Promise<{ saved: boolean; has_api_key: boolean }> {
  return putJson("/api/admin/settings/model", data);
}

export function updateHighlight(
  id: number,
  data: { title: string; summary: string; is_pinned: boolean; is_hidden: boolean }
): Promise<{ id: number; review_status: string }> {
  return patchJson(`/api/admin/highlights/${id}`, data);
}
