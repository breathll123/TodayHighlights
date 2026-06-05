import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchSources, createSource, updateSource, triggerCrawl } from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { Pencil } from "lucide-react";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const defaultForm = { topic_id: 1, site: "xueqiu", name: "", entry_url: "", cookie: "", enabled: true, crawl_interval_minutes: 60, enable_highlight: false };

interface EditState {
  id: number;
  name: string;
  entry_url: string;
  enabled: boolean;
  enable_highlight: boolean;
  crawl_interval_minutes: number;
}

export function AdminSourcesPage() {
  const queryClient = useQueryClient();
  const { data: sources, isLoading } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });

  const [form, setForm] = useState(defaultForm);
  const [editSource, setEditSource] = useState<EditState | null>(null);
  const [editCookie, setEditCookie] = useState("");

  const createMut = useMutation({
    mutationFn: createSource,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["sources"] }); setForm(defaultForm); toast.success("数据源已添加"); },
    onError: (err: Error) => toast.error(`添加失败: ${err.message}`),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateSource>[1] }) => updateSource(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["sources"] }); setEditSource(null); toast.success("已更新"); },
    onError: (err: Error) => toast.error(`更新失败: ${err.message}`),
  });

  const crawlMut = useMutation({
    mutationFn: triggerCrawl,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["jobs"] }); toast.success("爬取已触发"); },
    onError: (err: Error) => toast.error(`爬取失败: ${err.message}`),
  });

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  const openEdit = (s: EditState) => {
    setEditSource(s);
    setEditCookie("");
  };

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Sources"
        title="数据源管理"
        description="维护各主题的数据入口、采集周期和访问凭证。新增 AI、足球等垂类时，只需要继续扩展来源适配器。"
      />

      <form
        className="space-y-4 rounded-xl border border-border/75 bg-card/80 p-6 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault();
          createMut.mutate({ ...form });
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
        <div className="flex items-center gap-3">
          <Switch checked={form.enable_highlight} onCheckedChange={(v) => setForm({ ...form, enable_highlight: v })} id="new-hl" />
          <Label htmlFor="new-hl" className="text-sm cursor-pointer">启用 AI 内容加工 (enable_highlight)</Label>
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
                  <th className="px-4 py-3 text-left font-medium">AI 加工</th>
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
                    <td className="px-4 py-3">{s.enable_highlight ? "已开启" : "未开启"}</td>
                    <td className="px-4 py-3">{s.crawl_interval_minutes}分</td>
                    <td className="px-4 py-3 flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={() => openEdit({
                        id: s.id, name: s.name, entry_url: s.entry_url,
                        enabled: s.enabled, enable_highlight: s.enable_highlight,
                        crawl_interval_minutes: s.crawl_interval_minutes,
                      })}>
                        <Pencil className="w-3 h-3 mr-1" />编辑
                      </Button>
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

      <Dialog open={editSource !== null} onOpenChange={() => setEditSource(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>编辑数据源 — {editSource?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Cookie（留空不修改）</Label>
              <Input
                value={editCookie}
                onChange={(e) => setEditCookie(e.target.value)}
                placeholder="粘贴新的 Cookie..."
              />
              <p className="text-xs text-muted-foreground">粘贴浏览器 Cookie 后点击保存即可更新</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>爬取间隔(分)</Label>
                <Input
                  type="number"
                  value={editSource?.crawl_interval_minutes ?? 60}
                  onChange={(e) => setEditSource((s) => s ? { ...s, crawl_interval_minutes: +e.target.value } : null)}
                />
              </div>
              <div className="space-y-2">
                <Label>名称</Label>
                <Input
                  value={editSource?.name ?? ""}
                  onChange={(e) => setEditSource((s) => s ? { ...s, name: e.target.value } : null)}
                />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Switch
                checked={editSource?.enable_highlight ?? false}
                onCheckedChange={(v) => setEditSource((s) => s ? { ...s, enable_highlight: v } : null)}
                id="edit-hl"
              />
              <Label htmlFor="edit-hl" className="text-sm cursor-pointer">启用 AI 内容加工</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditSource(null)}>取消</Button>
            <Button
              onClick={() => {
                if (!editSource) return;
                const data: Record<string, unknown> = {};
                if (editCookie) data.cookie = editCookie;
                if (editSource.name) data.name = editSource.name;
                data.crawl_interval_minutes = editSource.crawl_interval_minutes;
                data.enable_highlight = editSource.enable_highlight;
                updateMut.mutate({ id: editSource.id, data });
              }}
              disabled={updateMut.isPending}
            >
              {updateMut.isPending ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
