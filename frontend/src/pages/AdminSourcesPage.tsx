import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchSources, createSource, triggerCrawl } from "../api/client";

export function AdminSourcesPage() {
  const queryClient = useQueryClient();
  const { data: sources, isLoading } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });

  const [form, setForm] = useState({
    topic_id: 1,
    site: "xueqiu",
    name: "",
    entry_url: "",
    cookie: "",
    enabled: true,
    crawl_interval_minutes: 60,
  });

  const createMut = useMutation({
    mutationFn: createSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  });

  const crawlMut = useMutation({
    mutationFn: triggerCrawl,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  if (isLoading) return <div className="page-message">加载中...</div>;

  return (
    <div className="page">
      <h1>数据源管理</h1>

      <form
        className="admin-form"
        onSubmit={(e) => {
          e.preventDefault();
          createMut.mutate(form, { onSuccess: () => setForm((f) => ({ ...f, name: "", entry_url: "", cookie: "" })) });
        }}
      >
        <div className="form-row">
          <label>
            名称
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="雪球自选" required />
          </label>
          <label>
            入口 URL
            <input value={form.entry_url} onChange={(e) => setForm({ ...form, entry_url: e.target.value })} placeholder="https://xueqiu.com/v4/..." required />
          </label>
        </div>
        <div className="form-row">
          <label>
            Cookie
            <input value={form.cookie} onChange={(e) => setForm({ ...form, cookie: e.target.value })} placeholder="xq_a_token=..." />
          </label>
          <label>
            爬取间隔(分)
            <input type="number" value={form.crawl_interval_minutes} onChange={(e) => setForm({ ...form, crawl_interval_minutes: +e.target.value })} />
          </label>
        </div>
        <button type="submit" disabled={createMut.isPending}>
          {createMut.isPending ? "保存中..." : "添加数据源"}
        </button>
      </form>

      <table className="admin-table">
        <thead>
          <tr><th>名称</th><th>站点</th><th>Cookie</th><th>状态</th><th>间隔</th><th>操作</th></tr>
        </thead>
        <tbody>
          {sources?.map((s) => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td>{s.site}</td>
              <td>{s.has_cookie ? "已配置" : "未配置"}</td>
              <td>{s.enabled ? "启用" : "禁用"}</td>
              <td>{s.crawl_interval_minutes}分</td>
              <td>
                <button onClick={() => crawlMut.mutate(s.id)} disabled={crawlMut.isPending}>
                  立即爬取
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
