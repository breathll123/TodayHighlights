import { useQuery } from "@tanstack/react-query";
import { fetchHighlights } from "../api/client";

export function SummaryPage() {
  const { data: highlights, isLoading, error } = useQuery({
    queryKey: ["highlights"],
    queryFn: fetchHighlights,
  });

  if (isLoading) return <div className="page-message">加载中...</div>;
  if (error) return <div className="page-message error">加载失败</div>;

  return (
    <div className="page">
      <h1>每日摘要</h1>
      {!highlights || highlights.length === 0 ? (
        <p className="empty">暂无看点数据</p>
      ) : (
        <div className="highlight-grid">
          {highlights.map((h) => (
            <article key={h.id} className={`highlight-card ${h.is_pinned ? "pinned" : ""}`}>
              <div className="card-header">
                <h2>{h.title}</h2>
                {h.is_pinned && <span className="pin-badge">置顶</span>}
              </div>
              <p className="card-summary">{h.summary}</p>
              <div className="card-meta">
                {h.tags_json.length > 0 && (
                  <div className="tags">
                    {h.tags_json.map((tag) => (
                      <span key={tag} className="tag">{tag}</span>
                    ))}
                  </div>
                )}
                <span className="score">热度: {h.score}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
