import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { fetchAdminTopics, createTopic, updateTopic, deleteTopic } from "@/api/client";
import type { Topic } from "@/api/types";
import { toast } from "sonner";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

export function AdminTopicsPage() {
  const queryClient = useQueryClient();
  const { data: topics = [], isLoading } = useQuery({ queryKey: ["admin-topics"], queryFn: fetchAdminTopics });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [form, setForm] = useState({ name: "", slug: "", sort_order: 0, enabled: true });

  const createMut = useMutation({
    mutationFn: createTopic,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["admin-topics"] }); setOpen(false); toast.success("话题已创建"); },
    onError: (err: Error) => toast.error(err.message),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => updateTopic(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["admin-topics"] }); setOpen(false); setEditing(null); toast.success("话题已更新"); },
    onError: (err: Error) => toast.error(err.message),
  });
  const deleteMut = useMutation({
    mutationFn: deleteTopic,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["admin-topics"] }); toast.success("话题已删除"); },
  });

  const openCreate = () => { setEditing(null); setForm({ name: "", slug: "", sort_order: 0, enabled: true }); setOpen(true); };
  const openEdit = (t: Topic) => { setEditing(t); setForm({ name: t.name, slug: t.slug, sort_order: t.sort_order, enabled: true }); setOpen(true); };

  const handleSave = () => {
    if (editing) updateMut.mutate({ id: editing.id, data: form });
    else createMut.mutate(form);
  };

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Topics"
        title="话题管理"
        description="管理平台顶层垂类。股票是当前样板，AI、足球等主题可以按相同方式加入导航和版面。"
        action={<Button onClick={openCreate}><Plus className="w-4 h-4 mr-2" />添加话题</Button>}
      />

      {topics.length === 0 ? (
        <p className="text-sm text-muted-foreground py-12 text-center">暂无话题</p>
      ) : (
        <div className="grid gap-3">
          {topics.map((t: Topic) => (
            <Card key={t.id}>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{t.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">/{t.slug} · 排序 {t.sort_order}</div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => openEdit(t)}><Pencil className="w-4 h-4" /></Button>
                <Button variant="ghost" size="icon" onClick={() => { if (confirm("确定删除？")) deleteMut.mutate(t.id); }}><Trash2 className="w-4 h-4 text-destructive" /></Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>{editing ? "编辑话题" : "添加话题"}</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2"><Label>名称</Label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="AI" /></div>
            <div className="space-y-2"><Label>Slug</Label><Input value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })} placeholder="ai" /></div>
            <div className="space-y-2"><Label>排序</Label><Input type="number" value={form.sort_order} onChange={e => setForm({ ...form, sort_order: +e.target.value })} /></div>
            <div className="flex items-center gap-2"><Switch checked={form.enabled} onCheckedChange={v => setForm({ ...form, enabled: v })} /><Label>启用</Label></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={handleSave}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
