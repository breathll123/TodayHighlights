import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchModelSettings, saveModelSettings } from "../api/client";

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

  if (isLoading) return <div className="page-message">加载中...</div>;

  return (
    <div className="page">
      <h1>模型设置</h1>
      <form
        className="admin-form"
        onSubmit={(e) => {
          e.preventDefault();
          saveMut.mutate(form);
        }}
      >
        <div className="form-row">
          <label>
            API Base URL
            <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1" required />
          </label>
          <label>
            模型名称
            <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="gpt-4o" required />
          </label>
        </div>
        <div className="form-row">
          <label>
            API Key
            <input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder={settings?.has_api_key ? "已配置，留空则不修改" : "输入 API Key"} />
          </label>
        </div>
        <p className="form-hint">API Key 状态: {settings?.has_api_key ? "已配置" : "未配置"}</p>
        <button type="submit" disabled={saveMut.isPending}>
          {saveMut.isPending ? "保存中..." : "保存设置"}
        </button>
      </form>
    </div>
  );
}
