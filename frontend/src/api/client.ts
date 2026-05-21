import type { Highlight, Topic } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
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
