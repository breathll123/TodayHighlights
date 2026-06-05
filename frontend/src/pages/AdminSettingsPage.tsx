import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BrainCircuit, Check, Pencil, Plus, Star } from "lucide-react";
import { fetchModelSettings, saveModelSettings, fetchAIModels, createAIModel, updateAIModel, setDefaultAIModel } from "../api/client";
import type { AIModelConfig, AIModelConfigWrite } from "../api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { cn } from "@/lib/utils";

const EMPTY_FORM: AIModelConfigWrite = {
  name: "", base_url: "", model: "", api_key: "", is_default: false, enabled: true, notes: "",
};

function ModelForm({
  form, onChange, onSave, onCancel, isPending, editingId,
}: {
  form: AIModelConfigWrite;
  onChange: (f: AIModelConfigWrite) => void;
  onSave: () => void;
  onCancel: () => void;
  isPending: boolean;
  editingId: number | null;
}) {
  return (
    <form
      className="space-y-4 rounded-xl border border-border/75 bg-card/80 p-6 shadow-sm"
      onSubmit={(e) => { e.preventDefault(); onSave(); }}
    >
      <h4 className="text-sm font-semibold">{editingId ? "编辑模型" : "新增模型"}</h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          名称
          <Input value={form.name} onChange={(e) => onChange({ ...form, name: e.target.value })} placeholder="DeepSeek 默认" required />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          模型名
          <Input value={form.model} onChange={(e) => onChange({ ...form, model: e.target.value })} placeholder="deepseek-chat" required />
        </label>
      </div>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        API Base URL
        <Input value={form.base_url} onChange={(e) => onChange({ ...form, base_url: e.target.value })} placeholder="https://api.deepseek.com/v1" required />
      </label>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          API Key
          <Input type="password" value={form.api_key} onChange={(e) => onChange({ ...form, api_key: e.target.value })} placeholder={editingId ? "已配置，留空则不修改" : "输入 API Key"} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          备注
          <Input value={form.notes} onChange={(e) => onChange({ ...form, notes: e.target.value })} placeholder="可选备注" />
        </label>
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_default} onChange={(e) => onChange({ ...form, is_default: e.target.checked })} className="rounded" />
          设为默认
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.enabled} onChange={(e) => onChange({ ...form, enabled: e.target.checked })} className="rounded" />
          启用
        </label>
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={isPending}>{isPending ? "保存中..." : "保存"}</Button>
        <Button type="button" size="sm" variant="outline" onClick={onCancel}>取消</Button>
      </div>
    </form>
  );
}

export function AdminSettingsPage() {
  const queryClient = useQueryClient();

  // Legacy LLM settings (kept for backward compat)
  const { data: settings, isLoading } = useQuery({ queryKey: ["model-settings"], queryFn: fetchModelSettings });
  const [legacyForm, setLegacyForm] = useState({ base_url: "", api_key: "", model: "" });
  const [legacyInit, setLegacyInit] = useState(false);
  if (settings && !legacyInit) {
    setLegacyForm({ base_url: settings.base_url, api_key: "", model: settings.model });
    setLegacyInit(true);
  }
  const legacySave = useMutation({
    mutationFn: saveModelSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-settings"] });
      setLegacyForm((f) => ({ ...f, api_key: "" }));
    },
  });

  // AI Model configs
  const { data: aiModels } = useQuery({ queryKey: ["ai-models"], queryFn: fetchAIModels });
  const [showForm, setShowForm] = useState(false);
  const [editingModel, setEditingModel] = useState<AIModelConfig | null>(null);
  const [form, setForm] = useState<AIModelConfigWrite>(EMPTY_FORM);

  const createMut = useMutation({
    mutationFn: createAIModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-models"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AIModelConfigWrite }) => updateAIModel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-models"] });
      setShowForm(false);
      setEditingModel(null);
      setForm(EMPTY_FORM);
    },
  });

  const setDefaultMut = useMutation({
    mutationFn: setDefaultAIModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-models"] }),
  });

  const handleSave = () => {
    if (editingModel) {
      updateMut.mutate({ id: editingModel.id, data: form });
    } else {
      createMut.mutate(form);
    }
  };

  const startEdit = (m: AIModelConfig) => {
    setEditingModel(m);
    setForm({ name: m.name, base_url: m.base_url, model: m.model, api_key: "", is_default: m.is_default, enabled: m.enabled, notes: m.notes });
    setShowForm(true);
  };

  const startCreate = () => {
    setEditingModel(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingModel(null);
    setForm(EMPTY_FORM);
  };

  const isPending = createMut.isPending || updateMut.isPending;

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="AI"
        title="AI 模型设置"
        description="管理 OpenAI 兼容模型配置，支持多模型切换用于内容加工和主题汇总。"
      />

      {/* AI Model Configs */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">AI 模型配置</h3>
          {!showForm && (
            <Button size="sm" variant="outline" onClick={startCreate}>
              <Plus className="h-3.5 w-3.5 mr-1" /> 新增模型
            </Button>
          )}
        </div>

        {showForm && (
          <ModelForm
            form={form}
            onChange={setForm}
            onSave={handleSave}
            onCancel={cancelForm}
            isPending={isPending}
            editingId={editingModel?.id ?? null}
          />
        )}

        {aiModels && aiModels.length > 0 && (
          <div className="space-y-2">
            {aiModels.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex items-center justify-between gap-4 rounded-lg border p-4",
                  m.is_default ? "border-primary/40 bg-primary/5" : "border-border/60 bg-card/70"
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{m.name}</span>
                    {m.is_default && (
                      <Badge variant="default" className="text-[10px] h-4 px-1.5"><Star className="h-2.5 w-2.5 mr-0.5" />默认</Badge>
                    )}
                    {m.enabled ? (
                      <Badge variant="secondary" className="text-[10px] h-4 px-1.5"><Check className="h-2.5 w-2.5 mr-0.5" />启用</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] h-4 px-1.5">禁用</Badge>
                    )}
                    {m.has_api_key && (
                      <Badge variant="outline" className="text-[10px] h-4 px-1.5">Key 已配置</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1.5">
                    {m.model} · {m.base_url}
                    {m.notes ? ` · ${m.notes}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button size="sm" variant="ghost" onClick={() => startEdit(m)}><Pencil className="h-3.5 w-3.5" /></Button>
                  {!m.is_default && (
                    <Button size="sm" variant="ghost" onClick={() => setDefaultMut.mutate(m.id)} disabled={setDefaultMut.isPending}>
                      <Star className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {aiModels && aiModels.length === 0 && !showForm && (
          <div className="text-center py-8 text-sm text-muted-foreground border border-dashed rounded-xl">
            <BrainCircuit className="h-8 w-8 mx-auto mb-2 opacity-30" />
            暂无 AI 模型配置，点击「新增模型」添加
          </div>
        )}
      </div>

      {/* Legacy LLM Settings */}
      <div className="space-y-4 pt-4 border-t border-border/50">
        <h3 className="text-sm font-semibold text-muted-foreground">旧版 LLM 设置 (兼容)</h3>
        <form
          className="space-y-4 rounded-xl border border-border/75 bg-card/80 p-6 shadow-sm"
          onSubmit={(e) => { e.preventDefault(); legacySave.mutate(legacyForm); }}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              API Base URL
              <Input value={legacyForm.base_url} onChange={(e) => setLegacyForm({ ...legacyForm, base_url: e.target.value })} placeholder="https://api.openai.com/v1" required />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              模型名称
              <Input value={legacyForm.model} onChange={(e) => setLegacyForm({ ...legacyForm, model: e.target.value })} placeholder="gpt-4o" required />
            </label>
          </div>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            API Key
            <Input type="password" value={legacyForm.api_key} onChange={(e) => setLegacyForm({ ...legacyForm, api_key: e.target.value })} placeholder={settings?.has_api_key ? "已配置，留空则不修改" : "输入 API Key"} />
          </label>
          <div className="flex items-center gap-2 text-sm">
            <span>API Key 状态:</span>
            {settings?.has_api_key ? <Badge variant="default">已配置</Badge> : <Badge variant="secondary">未配置</Badge>}
          </div>
          <Button type="submit" size="sm" disabled={legacySave.isPending}>
            {legacySave.isPending ? "保存中..." : "保存旧版设置"}
          </Button>
        </form>
      </div>
    </div>
  );
}
