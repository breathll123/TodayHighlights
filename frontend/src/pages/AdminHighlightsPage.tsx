import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchHighlights, updateHighlight } from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

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

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Highlights"
        title="看点审核"
        description="审核 AI 生成的跨主题信息摘要，控制置顶、隐藏和前台展示质量。"
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {highlights?.map((h) =>
          editingId === h.id ? (
            <form
              key={h.id}
              className="space-y-3 bg-card border rounded-xl p-6"
              onSubmit={(e) => {
                e.preventDefault();
                updateMut.mutate({ id: h.id, data: editForm });
              }}
            >
              <Input
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              />
              <textarea
                value={editForm.summary}
                onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                rows={3}
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={editForm.is_pinned} onChange={(e) => setEditForm({ ...editForm, is_pinned: e.target.checked })} /> 置顶
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={editForm.is_hidden} onChange={(e) => setEditForm({ ...editForm, is_hidden: e.target.checked })} /> 隐藏
                </label>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={updateMut.isPending}>保存</Button>
                <Button type="button" variant="outline" onClick={() => setEditingId(null)}>取消</Button>
              </div>
            </form>
          ) : (
            <div key={h.id} className={`bg-card border rounded-xl p-6 space-y-3 ${h.is_pinned ? "ring-2 ring-orange-500" : ""} ${h.is_hidden ? "opacity-50" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold">{h.title}</h2>
                <div className="flex gap-1 flex-shrink-0">
                  {h.is_pinned && <span className="text-xs bg-orange-500 text-white px-2 py-0.5 rounded-full font-medium">置顶</span>}
                  {h.is_hidden && <Badge variant="secondary">已隐藏</Badge>}
                </div>
              </div>
              <p className="text-sm text-muted-foreground">{h.summary}</p>
              <div className="flex items-center justify-between pt-2">
                <div className="flex flex-wrap gap-1">
                  {h.tags_json.map((tag: string) => (<span key={tag} className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{tag}</span>))}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditingId(h.id);
                    setEditForm({ title: h.title, summary: h.summary, is_pinned: h.is_pinned, is_hidden: h.is_hidden });
                  }}
                >
                  编辑
                </Button>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
