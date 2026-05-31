import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchModelSettings, saveModelSettings } from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

export function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({ queryKey: ["model-settings"], queryFn: fetchModelSettings });

  const [form, setForm] = useState({ base_url: "", api_key: "", model: "" });
  const [initialized, setInitialized] = useState(false);

  if (settings && !initialized) {
    setForm({ base_url: settings.base_url, api_key: "", model: settings.model });
    setInitialized(true);
  }

  const saveMut = useMutation({
    mutationFn: saveModelSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-settings"] });
      setForm((f) => ({ ...f, api_key: "" }));
    },
  });

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Models"
        title="模型设置"
        description="配置 OpenAI 兼容模型服务，用于不同主题的摘要、标签和重点提取。"
      />
      <form
        className="space-y-4 rounded-xl border border-border/75 bg-card/80 p-6 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault();
          saveMut.mutate(form);
        }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            API Base URL
            <Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1" required />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            模型名称
            <Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="gpt-4o" required />
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            API Key
            <Input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder={settings?.has_api_key ? "已配置，留空则不修改" : "输入 API Key"} />
          </label>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span>API Key 状态:</span>
          {settings?.has_api_key ? (
            <Badge variant="default">已配置</Badge>
          ) : (
            <Badge variant="secondary">未配置</Badge>
          )}
        </div>
        <Button type="submit" disabled={saveMut.isPending}>
          {saveMut.isPending ? "保存中..." : "保存设置"}
        </Button>
      </form>
    </div>
  );
}
