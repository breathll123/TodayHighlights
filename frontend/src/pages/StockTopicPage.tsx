import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { fetchHighlights } from "../api/client";

export function StockTopicPage() {
  const { data: highlights, isLoading, error } = useQuery({
    queryKey: ["highlights"],
    queryFn: fetchHighlights,
  });

  const [filterTag, setFilterTag] = useState("");
  const [sortBy, setSortBy] = useState<"score" | "time">("score");

  const filtered = useMemo(() => {
    if (!highlights) return [];
    let items = [...highlights];
    if (filterTag) {
      items = items.filter((h) => h.tags_json.includes(filterTag));
    }
    items.sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
      if (sortBy === "score") return b.score - a.score;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
    return items;
  }, [highlights, filterTag, sortBy]);

  const allTags = useMemo(() => {
    if (!highlights) return [];
    const tags = new Set<string>();
    highlights.forEach((h) => h.tags_json.forEach((t) => tags.add(t)));
    return [...tags];
  }, [highlights]);

  if (isLoading) return <div className="page-message">加载中...</div>;
  if (error) return <div className="page-message error">加载失败</div>;

  return (
    <div className="page">
      <h1>股票看点</h1>
      <div className="filters">
        <select value={filterTag} onChange={(e) => setFilterTag(e.target.value)}>
          <option value="">全部标签</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag}>{tag}</option>
          ))}
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as "score" | "time")}>
          <option value="score">按热度排序</option>
          <option value="time">按时间排序</option>
        </select>
      </div>
      {filtered.length === 0 ? (
        <p className="empty">暂无匹配的看点</p>
      ) : (
        <div className="highlight-grid">
          {filtered.map((h) => (
            <article key={h.id} className={`highlight-card ${h.is_pinned ? "pinned" : ""}`}>
              <div className="card-header">
                <h2>{h.title}</h2>
                {h.is_pinned && <span className="pin-badge">置顶</span>}
              </div>
              <p className="card-summary">{h.summary}</p>
              {h.related_symbols_json.length > 0 && (
                <div className="symbols">
                  {h.related_symbols_json.map((s) => (
                    <span key={s} className="symbol">{s}</span>
                  ))}
                </div>
              )}
              <div className="card-meta">
                <div className="tags">
                  {h.tags_json.map((tag) => (
                    <span key={tag} className="tag">{tag}</span>
                  ))}
                </div>
                <span className="score">热度: {h.score}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
