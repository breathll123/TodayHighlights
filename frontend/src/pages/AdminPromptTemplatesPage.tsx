import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  CircleCheck,
  CirclePause,
  Database,
  FileText,
  Pencil,
  Plus,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { createAIPromptTemplate, deleteAIPromptTemplate, fetchAIPromptTemplates, updateAIPromptTemplate } from "@/api/client";
import type { AIPromptTemplate, AIPromptTemplateWrite } from "@/api/types";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { SkillsPromptsSection } from "@/components/admin/SkillsPromptsSection";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { TableSkeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const emptyForm: AIPromptTemplateWrite = {
  topic_slug: "stocks",
  content_class: "news",
  topic_context: "",
  extra_forbidden: "",
  enabled: true,
  notes: "",
};

const contentClassMeta = {
  news: { label: "资讯内容" },
  rank: { label: "榜单与行情" },
  event: { label: "赛事与事件" },
} as const;

function templateToForm(template: AIPromptTemplate): AIPromptTemplateWrite {
  return {
    topic_slug: template.topic_slug,
    content_class: template.content_class,
    topic_context: template.topic_context,
    extra_forbidden: template.extra_forbidden,
    enabled: template.enabled,
    notes: template.notes,
  };
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function AdminPromptTemplatesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AIPromptTemplate | null>(null);
  const [form, setForm] = useState<AIPromptTemplateWrite>(emptyForm);
  const [editorOpen, setEditorOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AIPromptTemplate | null>(null);
  const { data: templates = [], isLoading } = useQuery({ queryKey: ["ai-prompt-templates"], queryFn: fetchAIPromptTemplates });

  const closeEditor = () => {
    setEditorOpen(false);
    setEditing(null);
    setForm(emptyForm);
  };

  const finishSave = async (message: string) => {
    await queryClient.invalidateQueries({ queryKey: ["ai-prompt-templates"] });
    closeEditor();
    toast.success(message);
  };

  const createMutation = useMutation({
    mutationFn: createAIPromptTemplate,
    onSuccess: () => finishSave("页面分析模板已新增"),
    onError: (error: Error) => toast.error(`新增失败：${error.message}`),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AIPromptTemplateWrite }) => updateAIPromptTemplate(id, data),
    onSuccess: () => finishSave("页面分析模板已更新"),
    onError: (error: Error) => toast.error(`保存失败：${error.message}`),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteAIPromptTemplate,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["ai-prompt-templates"] });
      setPendingDelete(null);
      toast.success("模板已删除");
    },
    onError: (error: Error) => toast.error(`删除失败：${error.message}`),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setEditorOpen(true);
  };

  const openEdit = (template: AIPromptTemplate) => {
    setEditing(template);
    setForm(templateToForm(template));
    setEditorOpen(true);
  };

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = { ...form, topic_slug: form.topic_slug.trim(), notes: form.notes.trim() };
    if (!payload.topic_slug) {
      toast.error("请填写主题 slug");
      return;
    }
    if (editing) updateMutation.mutate({ id: editing.id, data: payload });
    else createMutation.mutate(payload);
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const enabledCount = templates.filter((template) => template.enabled).length;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Prompt Workspace"
        title="Prompt 模板"
        description="分别管理面向页面展示的分析规则，以及进入业务数据前的清洗与整理规则。"
      />

      <Tabs defaultValue="page" className="space-y-5">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 bg-muted/70 p-1 sm:w-fit sm:min-w-[420px]">
          <TabsTrigger value="page" className="min-h-11 gap-2 px-4">
            <FileText className="h-4 w-4" aria-hidden="true" />
            页面级分析
          </TabsTrigger>
          <TabsTrigger value="cleaning" className="min-h-11 gap-2 px-4">
            <Database className="h-4 w-4" aria-hidden="true" />
            数据清洗级
          </TabsTrigger>
        </TabsList>

        <TabsContent value="page" className="mt-0 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">页面分析模板</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                按主题与内容类型控制公开页面中区块 AI 分析的领域背景和输出边界。
              </p>
            </div>
            <Button onClick={openCreate} className="h-11 gap-2 self-start sm:h-10 sm:self-auto">
              <Plus className="h-4 w-4" aria-hidden="true" />
              新增模板
            </Button>
          </div>

          <section className="overflow-hidden rounded-lg border border-border/80 bg-card" aria-label="页面分析模板列表">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-border/70 bg-muted/25 px-4 py-3 text-xs text-muted-foreground sm:px-5">
              <span>共 <strong className="font-semibold text-foreground">{templates.length}</strong> 个模板</span>
              <span className="flex items-center gap-1.5">
                <CircleCheck className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
                {enabledCount} 个启用
              </span>
              <span>同一主题与内容类型仅保留一份生效模板</span>
            </div>

            {isLoading ? (
              <div className="overflow-x-auto"><table className="w-full"><TableSkeleton columns={5} rows={5} /></table></div>
            ) : templates.length === 0 ? (
              <div className="flex min-h-52 flex-col items-center justify-center px-6 py-10 text-center">
                <FileText className="h-8 w-8 text-muted-foreground/60" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium">还没有页面分析模板</p>
                <p className="mt-1 text-xs text-muted-foreground">新建后，系统会按主题和内容类型自动匹配。</p>
                <Button size="sm" className="mt-4 gap-2" onClick={openCreate}>
                  <Plus className="h-4 w-4" aria-hidden="true" />新增模板
                </Button>
              </div>
            ) : (
              <div>
                <div className="hidden grid-cols-[minmax(180px,1.2fr)_minmax(160px,1fr)_150px_88px] gap-4 border-b border-border/70 px-5 py-2.5 text-xs font-medium text-muted-foreground md:grid">
                  <span>模板</span><span>适用内容</span><span>状态与版本</span><span className="text-right">操作</span>
                </div>
                {templates.map((template) => {
                  const meta = contentClassMeta[template.content_class];
                  return (
                    <article
                      key={template.id}
                      className="grid gap-4 border-b border-border/60 px-4 py-4 last:border-b-0 hover:bg-muted/20 md:grid-cols-[minmax(180px,1.2fr)_minmax(160px,1fr)_150px_88px] md:items-center md:px-5"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="truncate font-mono text-sm font-semibold text-foreground">{template.topic_slug}</span>
                          {!template.enabled && <CirclePause className="h-4 w-4 shrink-0 text-muted-foreground" aria-label="已停用" />}
                        </div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">{template.notes || "未填写备注"}</p>
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-foreground">{meta.label}</div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {template.topic_context || "未配置领域背景"}
                        </p>
                      </div>
                      <div className="flex items-center justify-between gap-3 md:block">
                        <span className={template.enabled ? "text-xs font-medium text-emerald-600 dark:text-emerald-400" : "text-xs text-muted-foreground"}>
                          {template.enabled ? "正在生效" : "已停用"} · v{template.template_version}
                        </span>
                        <span className="text-xs text-muted-foreground md:mt-1 md:block">{formatUpdatedAt(template.updated_at)} 更新</span>
                      </div>
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-11 w-11 md:h-9 md:w-9"
                          aria-label={`编辑 ${template.topic_slug}`}
                          title="编辑模板"
                          onClick={() => openEdit(template)}
                        >
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-11 w-11 text-muted-foreground hover:text-destructive md:h-9 md:w-9"
                          aria-label={`删除 ${template.topic_slug}`}
                          title="删除模板"
                          onClick={() => setPendingDelete(template)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </TabsContent>

        <TabsContent value="cleaning" className="mt-0">
          <SkillsPromptsSection />
        </TabsContent>
      </Tabs>

      <Dialog open={editorOpen} onOpenChange={(open) => { if (!open && !isSaving) closeEditor(); }}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑页面分析模板" : "新增页面分析模板"}</DialogTitle>
            <DialogDescription>
              这里只配置页面区块的分析上下文，不会改动原始数据或数据清洗规则。
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={submit} className="space-y-6">
            <fieldset className="space-y-4">
              <legend className="mb-3 text-sm font-semibold text-foreground">适用范围</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="topic_slug">主题 slug</Label>
                  <Input
                    id="topic_slug"
                    value={form.topic_slug}
                    onChange={(event) => setForm({ ...form, topic_slug: event.target.value })}
                    placeholder="例如 stocks、football、ai"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">必须与页面主题路由中的 slug 保持一致。</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="content_class">内容类型</Label>
                  <Select value={form.content_class} onValueChange={(value: "news" | "rank" | "event") => setForm({ ...form, content_class: value })}>
                    <SelectTrigger id="content_class"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="news">资讯内容 · news</SelectItem>
                      <SelectItem value="rank">榜单与行情 · rank</SelectItem>
                      <SelectItem value="event">赛事与事件 · event</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">系统会根据区块数据源自动归类后匹配。</p>
                </div>
              </div>
            </fieldset>

            <fieldset className="space-y-4 border-t border-border/70 pt-5">
              <legend className="flex items-center gap-2 pr-3 text-sm font-semibold text-foreground">
                <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
                分析约束
              </legend>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="topic_context">领域背景</Label>
                  <textarea
                    id="topic_context"
                    className="min-h-44 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm leading-6 outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    value={form.topic_context}
                    onChange={(event) => setForm({ ...form, topic_context: event.target.value })}
                    placeholder="说明该领域需要重点关注的指标、事件与判断角度。"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="extra_forbidden">额外禁令</Label>
                  <textarea
                    id="extra_forbidden"
                    className="min-h-44 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm leading-6 outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    value={form.extra_forbidden}
                    onChange={(event) => setForm({ ...form, extra_forbidden: event.target.value })}
                    placeholder="补充该领域不得出现的结论、建议或表达方式。"
                  />
                </div>
              </div>
            </fieldset>

            <fieldset className="border-t border-border/70 pt-5">
              <legend className="mb-3 text-sm font-semibold text-foreground">管理信息</legend>
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_180px] sm:items-end">
                <div className="space-y-2">
                  <Label htmlFor="notes">备注</Label>
                  <Input id="notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="例如：股票资讯默认模板" />
                </div>
                <div className="flex min-h-10 items-center justify-between rounded-md border border-border/80 px-3">
                  <Label htmlFor="enabled" className="cursor-pointer">立即启用</Label>
                  <Switch id="enabled" checked={form.enabled} onCheckedChange={(checked) => setForm({ ...form, enabled: checked })} />
                </div>
              </div>
            </fieldset>

            <DialogFooter className="gap-2 border-t border-border/70 pt-5 sm:space-x-0">
              <Button type="button" variant="outline" className="h-11 sm:h-10" onClick={closeEditor} disabled={isSaving}>取消</Button>
              <Button type="submit" className="h-11 sm:h-10" disabled={isSaving || !form.topic_slug.trim()}>
                {isSaving ? "保存中..." : editing ? "保存修改" : "创建模板"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除页面分析模板？"
        description={pendingDelete ? `删除后，“${pendingDelete.topic_slug} / ${contentClassMeta[pendingDelete.content_class].label}”将回退到系统默认分析规则。` : undefined}
        confirmLabel="删除模板"
        loading={deleteMutation.isPending}
        onConfirm={() => { if (pendingDelete) deleteMutation.mutate(pendingDelete.id); }}
        onCancel={() => { if (!deleteMutation.isPending) setPendingDelete(null); }}
      />
    </div>
  );
}
