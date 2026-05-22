import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchSources, createSource, triggerCrawl } from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">数据源管理</h1>

      <form
        className="space-y-4 bg-card border rounded-xl p-6"
        onSubmit={(e) => {
          e.preventDefault();
          createMut.mutate(form, { onSuccess: () => setForm((f) => ({ ...f, name: "", entry_url: "", cookie: "" })) });
        }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            名称
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="雪球自选" required />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            入口 URL
            <Input value={form.entry_url} onChange={(e) => setForm({ ...form, entry_url: e.target.value })} placeholder="https://xueqiu.com/v4/..." required />
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Cookie
            <Input value={form.cookie} onChange={(e) => setForm({ ...form, cookie: e.target.value })} placeholder="xq_a_token=..." />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            爬取间隔(分)
            <Input type="number" value={form.crawl_interval_minutes} onChange={(e) => setForm({ ...form, crawl_interval_minutes: +e.target.value })} />
          </label>
        </div>
        <Button type="submit" disabled={createMut.isPending}>
          {createMut.isPending ? "保存中..." : "添加数据源"}
        </Button>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>数据源列表</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium">名称</th>
                  <th className="px-4 py-3 text-left font-medium">站点</th>
                  <th className="px-4 py-3 text-left font-medium">Cookie</th>
                  <th className="px-4 py-3 text-left font-medium">状态</th>
                  <th className="px-4 py-3 text-left font-medium">间隔</th>
                  <th className="px-4 py-3 text-left font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {sources?.map((s) => (
                  <tr key={s.id} className="border-b last:border-0">
                    <td className="px-4 py-3">{s.name}</td>
                    <td className="px-4 py-3">{s.site}</td>
                    <td className="px-4 py-3">{s.has_cookie ? "已配置" : "未配置"}</td>
                    <td className="px-4 py-3">{s.enabled ? "启用" : "禁用"}</td>
                    <td className="px-4 py-3">{s.crawl_interval_minutes}分</td>
                    <td className="px-4 py-3">
                      <Button size="sm" onClick={() => crawlMut.mutate(s.id)} disabled={crawlMut.isPending}>
                        立即爬取
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
