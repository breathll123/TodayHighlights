import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createAIPromptTemplate, deleteAIPromptTemplate, fetchAIPromptTemplates, updateAIPromptTemplate } from "@/api/client";
import type { AIPromptTemplate, AIPromptTemplateWrite } from "@/api/types";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { TableSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const emptyForm: AIPromptTemplateWrite = {
  topic_slug: "stocks",
  content_class: "news",
  topic_context: "",
  extra_forbidden: "",
  enabled: true,
  notes: "",
};

export function AdminPromptTemplatesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AIPromptTemplate | null>(null);
  const [form, setForm] = useState<AIPromptTemplateWrite>(emptyForm);
  const { data: templates = [], isLoading } = useQuery({ queryKey: ["ai-prompt-templates"], queryFn: fetchAIPromptTemplates });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["ai-prompt-templates"] });

  const createMutation = useMutation({ mutationFn: createAIPromptTemplate, onSuccess: invalidate });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AIPromptTemplateWrite }) => updateAIPromptTemplate(id, data),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({ mutationFn: deleteAIPromptTemplate, onSuccess: invalidate });

  const submit = () => {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: form });
    } else {
      createMutation.mutate(form);
    }
    setEditing(null);
    setForm(emptyForm);
  };

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="Prompt Templates" title="Prompt 模板" description="按主题和内容类型维护区块 AI 分析的领域背景与额外禁令。" />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full min-w-[520px] text-sm stagger-rows">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">主题</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">版本</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            {isLoading ? <TableSkeleton columns={5} rows={5} /> : (
            <tbody>
              {templates.map((template) => (
                <tr key={template.id} className="border-t">
                  <td className="px-4 py-3">{template.topic_slug}</td>
                  <td className="px-4 py-3">{template.content_class}</td>
                  <td className="px-4 py-3">v{template.template_version}</td>
                  <td className="px-4 py-3">{template.enabled ? "启用" : "停用"}</td>
                  <td className="space-x-2 px-4 py-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => { setEditing(template); setForm({
                      topic_slug: template.topic_slug,
                      content_class: template.content_class,
                      topic_context: template.topic_context,
                      extra_forbidden: template.extra_forbidden,
                      enabled: template.enabled,
                      notes: template.notes,
                    }); }}>编辑</Button>
                    <Button size="sm" variant="outline" onClick={() => deleteMutation.mutate(template.id)}>删除</Button>
                  </td>
                </tr>
              ))}
            </tbody>
            )}
          </table>
        </div>

        <div className="space-y-4 rounded-lg border bg-card p-4">
          <div className="space-y-2">
            <Label htmlFor="topic_slug">主题 slug</Label>
            <Input id="topic_slug" value={form.topic_slug} onChange={(event) => setForm({ ...form, topic_slug: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="content_class">内容类型</Label>
            <Select value={form.content_class} onValueChange={(value: "news" | "rank" | "event") => setForm({ ...form, content_class: value })}>
              <SelectTrigger id="content_class"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="news">news</SelectItem>
                <SelectItem value="rank">rank</SelectItem>
                <SelectItem value="event">event</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="topic_context">领域背景</Label>
            <textarea id="topic_context" className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.topic_context} onChange={(event) => setForm({ ...form, topic_context: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="extra_forbidden">额外禁令</Label>
            <textarea id="extra_forbidden" className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.extra_forbidden} onChange={(event) => setForm({ ...form, extra_forbidden: event.target.value })} />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="enabled">启用</Label>
            <Switch id="enabled" checked={form.enabled} onCheckedChange={(checked) => setForm({ ...form, enabled: checked })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">备注</Label>
            <Input id="notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </div>
          <Button className="w-full" onClick={submit}>{editing ? "保存模板" : "新增模板"}</Button>
        </div>
      </div>
    </div>
  );
}
