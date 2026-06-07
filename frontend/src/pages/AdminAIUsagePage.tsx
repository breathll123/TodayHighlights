import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
} from "recharts";
import { Activity, Cpu, Eye, TrendingUp, Zap } from "lucide-react";
import { fetchAITokenUsages, fetchAITokenUsageDetail, fetchAIUsageStats } from "@/api/client";
import type { AITokenUsage, AITokenUsageDetail } from "@/api/types";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AIUsageDetailDrawer } from "@/components/layout/AIUsageDetailDrawer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

export function AdminAIUsagePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["ai-token-usages"],
    queryFn: () => fetchAITokenUsages(1, 20),
  });
  const { data: stats } = useQuery({
    queryKey: ["ai-usage-stats"],
    queryFn: fetchAIUsageStats,
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
  } = useQuery({
    queryKey: ["ai-token-usage-detail", selectedId],
    queryFn: () => fetchAITokenUsageDetail(selectedId!),
    enabled: selectedId !== null,
  });

  const items = data?.items ?? [];
  const avgTokens = items.length > 0
    ? Math.round(items.reduce((sum, i) => sum + i.total_tokens, 0) / items.length)
    : 0;

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="AI Usage" title="AI 用量" description="追踪 AI 模型 token 消耗、调用次数和请求详情。" />

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500"><Zap className="h-4 w-4" /></span>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">今日 Token</p>
              <p className="text-xl font-bold tabular-nums">{stats?.today_tokens.toLocaleString() ?? "—"}</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500"><Activity className="h-4 w-4" /></span>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">今日调用</p>
              <p className="text-xl font-bold tabular-nums">{stats?.today_calls ?? "—"}</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500"><TrendingUp className="h-4 w-4" /></span>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">列表均次</p>
              <p className="text-xl font-bold tabular-nums">{avgTokens.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-violet-500"><Cpu className="h-4 w-4" /></span>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">活跃模型</p>
              <p className="text-xl font-bold tabular-nums">{stats?.active_models ?? "—"}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <Tabs defaultValue="trend">
        <TabsList className="h-8">
          <TabsTrigger value="trend" className="text-xs">趋势</TabsTrigger>
          <TabsTrigger value="model" className="text-xs">模型</TabsTrigger>
          <TabsTrigger value="topic" className="text-xs">主题</TabsTrigger>
        </TabsList>

        <TabsContent value="trend" className="rounded-xl border bg-card p-4 mt-3">
          {stats?.daily_trend?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={stats.daily_trend}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total_tokens" stroke="#3b82f6" name="Token" strokeWidth={2} dot={{ r: 2 }} />
                <Line type="monotone" dataKey="calls" stroke="#10b981" name="调用次数" strokeWidth={2} dot={{ r: 2 }} yAxisId={1} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无趋势数据</p>
          )}
        </TabsContent>

        <TabsContent value="model" className="rounded-xl border bg-card p-4 mt-3">
          {stats?.by_model?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.by_model}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                <XAxis dataKey="model_name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="total_tokens" fill="#3b82f6" name="Token" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无模型数据</p>
          )}
        </TabsContent>

        <TabsContent value="topic" className="rounded-xl border bg-card p-4 mt-3">
          {stats?.by_topic?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.by_topic}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
                <XAxis dataKey="topic_slug" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="total_tokens" fill={CHART_COLORS[0]} name="Token" radius={[4, 4, 0, 0]}>
                  {stats.by_topic.map((_, i) => (
                    <rect key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无主题数据</p>
          )}
        </TabsContent>
      </Tabs>

      {/* Detail Table */}
      <div className="overflow-hidden rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th className="px-4 py-3 text-left">时间</th>
              <th className="px-4 py-3 text-left">主题</th>
              <th className="px-4 py-3 text-left">方块/场景</th>
              <th className="px-4 py-3 text-left">模型</th>
              <th className="px-4 py-3 text-right">Prompt</th>
              <th className="px-4 py-3 text-right">Completion</th>
              <th className="px-4 py-3 text-right">Total</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td className="px-4 py-4 text-center text-muted-foreground" colSpan={8}>加载中...</td></tr>
            ) : items.length === 0 ? (
              <tr><td className="px-4 py-4 text-center text-muted-foreground" colSpan={8}>暂无使用记录</td></tr>
            ) : items.map((item: AITokenUsage) => (
              <tr key={item.id} className="border-t hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 text-xs tabular-nums whitespace-nowrap">{formatTime(item.created_at)}</td>
                <td className="px-4 py-3 text-xs">{item.topic}</td>
                <td className="px-4 py-3 text-xs max-w-[140px] truncate" title={item.block_title}>
                  {item.block_title || (item.usage_type === "item_enrichment" ? "单条加工" : item.usage_type === "topic_summary" ? "主题汇总" : item.usage_type)}
                </td>
                <td className="px-4 py-3 text-xs font-mono truncate max-w-[100px]" title={item.model_name}>{item.model_name}</td>
                <td className="px-4 py-3 text-xs text-right tabular-nums">{item.prompt_tokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-xs text-right tabular-nums">{item.completion_tokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-xs text-right tabular-nums font-semibold">
                  {item.total_tokens.toLocaleString()}
                  {item.estimated ? <span className="text-[10px] text-muted-foreground ml-0.5">~</span> : null}
                </td>
                <td className="px-4 py-3 text-center">
                  <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={() => setSelectedId(item.id)}>
                    <Eye className="h-3 w-3" />详情
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail Drawer */}
      <AIUsageDetailDrawer
        open={selectedId !== null}
        detail={detail ?? null}
        isLoading={detailLoading}
        error={detailError ? (detailError as Error).message : null}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}
