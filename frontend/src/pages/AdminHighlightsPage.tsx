import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchHighlights, updateHighlight } from "../api/client";

export function AdminHighlightsPage() {
  const queryClient = useQueryClient();
  const { data: highlights, isLoading } = useQuery({ queryKey: ["highlights"], queryFn: fetchHighlights });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ title: "", summary: "", is_pinned: false, is_hidden: false });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { title: string; summary: string; is_pinned: boolean; is_hidden: boolean } }) =>
      updateHighlight(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["highlights"] });
      setEditingId(null);
    },
  });

  if (isLoading) return <div className="page-message">加载中...</div>;

  return (
    <div className="page">
      <h1>看点审核</h1>
      <div className="highlight-grid">
        {highlights?.map((h) =>
          editingId === h.id ? (
            <form
              key={h.id}
              className="highlight-card admin-edit"
              onSubmit={(e) => {
                e.preventDefault();
                updateMut.mutate({ id: h.id, data: editForm });
              }}
            >
              <input
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                className="edit-input"
              />
              <textarea
                value={editForm.summary}
                onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                rows={3}
                className="edit-input"
              />
              <div className="edit-checks">
                <label><input type="checkbox" checked={editForm.is_pinned} onChange={(e) => setEditForm({ ...editForm, is_pinned: e.target.checked })} /> 置顶</label>
                <label><input type="checkbox" checked={editForm.is_hidden} onChange={(e) => setEditForm({ ...editForm, is_hidden: e.target.checked })} /> 隐藏</label>
              </div>
              <div className="edit-actions">
                <button type="submit" disabled={updateMut.isPending}>保存</button>
                <button type="button" onClick={() => setEditingId(null)}>取消</button>
              </div>
            </form>
          ) : (
            <div key={h.id} className={`highlight-card ${h.is_pinned ? "pinned" : ""} ${h.is_hidden ? "hidden" : ""}`}>
              <div className="card-header">
                <h2>{h.title}</h2>
                {h.is_pinned && <span className="pin-badge">置顶</span>}
                {h.is_hidden && <span className="hidden-badge">已隐藏</span>}
              </div>
              <p className="card-summary">{h.summary}</p>
              <div className="card-meta">
                <div className="tags">
                  {h.tags_json.map((tag) => (<span key={tag} className="tag">{tag}</span>))}
                </div>
                <button
                  onClick={() => {
                    setEditingId(h.id);
                    setEditForm({ title: h.title, summary: h.summary, is_pinned: h.is_pinned, is_hidden: h.is_hidden });
                  }}
                >
                  编辑
                </button>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
