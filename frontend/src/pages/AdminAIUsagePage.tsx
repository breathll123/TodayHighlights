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

const CHART_TEAL = "#1DB8A8";
const CHART_GOLD = "#F5A623";
const CHART_MUTED = "#A1AAB5";

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function StatCard({ icon: Icon, label, value, color }: { icon: typeof Zap; label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-3.5">
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border" style={{ borderColor: `${color}33`, backgroundColor: `${color}11`, color }}>
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground/70">{label}</p>
          <p className="text-lg font-bold tabular-nums text-foreground leading-tight">{value}</p>
        </div>
      </div>
    </div>
  );
}

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
      <AdminPageHeader eyebrow="AI Usage" title="AI 用量" description="Token 消耗追踪、调用明细与模型分布。" />

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard icon={Zap} label="今日 Token" value={stats?.today_tokens.toLocaleString() ?? "—"} color="#F5A623" />
        <StatCard icon={Activity} label="今日调用" value={`${stats?.today_calls ?? "—"} 次`} color={CHART_TEAL} />
        <StatCard icon={TrendingUp} label="列表均次" value={avgTokens.toLocaleString()} color={CHART_TEAL} />
        <StatCard icon={Cpu} label="活跃模型" value={`${stats?.active_models ?? "—"}`} color="#8b5cf6" />
      </div>

      {/* Charts */}
      <Tabs defaultValue="trend">
        <TabsList className="h-8">
          <TabsTrigger value="trend" className="text-xs">趋势</TabsTrigger>
          <TabsTrigger value="model" className="text-xs">模型</TabsTrigger>
          <TabsTrigger value="topic" className="text-xs">主题</TabsTrigger>
        </TabsList>

        <TabsContent value="trend" className="rounded-xl border border-border/70 bg-card p-4 mt-3">
          {stats?.daily_trend?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={stats.daily_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.4)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: CHART_MUTED }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: CHART_MUTED }} />
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
                <Legend />
                <Line type="monotone" dataKey="total_tokens" stroke={CHART_TEAL} name="Token" strokeWidth={2} dot={{ r: 2, fill: CHART_TEAL }} />
                <Line type="monotone" dataKey="calls" stroke={CHART_GOLD} name="调用" strokeWidth={2} dot={{ r: 2, fill: CHART_GOLD }} yAxisId={1} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无趋势数据</p>
          )}
        </TabsContent>

        <TabsContent value="model" className="rounded-xl border border-border/70 bg-card p-4 mt-3">
          {stats?.by_model?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.by_model}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.4)" />
                <XAxis dataKey="model_name" tick={{ fontSize: 11, fill: CHART_MUTED }} />
                <YAxis tick={{ fontSize: 11, fill: CHART_MUTED }} />
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="total_tokens" fill={CHART_TEAL} name="Token" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无模型数据</p>
          )}
        </TabsContent>

        <TabsContent value="topic" className="rounded-xl border border-border/70 bg-card p-4 mt-3">
          {stats?.by_topic?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.by_topic}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.4)" />
                <XAxis dataKey="topic_slug" tick={{ fontSize: 11, fill: CHART_MUTED }} />
                <YAxis tick={{ fontSize: 11, fill: CHART_MUTED }} />
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="total_tokens" fill={CHART_GOLD} name="Token" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-10">暂无主题数据</p>
          )}
        </TabsContent>
      </Tabs>

      {/* Detail Table */}
      <div className="overflow-hidden rounded-xl border border-border/70 bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium">时间</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium">主题</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium">方块/场景</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium">模型</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium">P</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium">C</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium">Total</th>
              <th className="px-4 py-2.5 text-center text-xs font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td className="px-4 py-8 text-center text-muted-foreground text-xs" colSpan={8}>加载中...</td></tr>
            ) : items.length === 0 ? (
              <tr><td className="px-4 py-6 text-center text-muted-foreground text-xs font-mono" colSpan={8}>no records</td></tr>
            ) : items.map((item: AITokenUsage) => (
              <tr key={item.id} className="border-t border-border/40 hover:bg-muted/20 transition-colors">
                <td className="px-4 py-2.5 text-xs tabular-nums whitespace-nowrap text-muted-foreground">{formatTime(item.created_at)}</td>
                <td className="px-4 py-2.5 text-xs font-medium">{item.topic}</td>
                <td className="px-4 py-2.5 text-xs max-w-[140px] truncate" title={item.block_title}>
                  {item.block_title || (item.usage_type === "item_enrichment" ? "单条加工" : item.usage_type === "topic_summary" ? "主题汇总" : item.usage_type)}
                </td>
                <td className="px-4 py-2.5 text-xs font-mono truncate max-w-[110px] text-muted-foreground/80" title={item.model_name}>{item.model_name}</td>
                <td className="px-4 py-2.5 text-xs text-right tabular-nums" style={{ color: CHART_TEAL }}>{item.prompt_tokens.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-xs text-right tabular-nums" style={{ color: CHART_GOLD }}>{item.completion_tokens.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-xs text-right tabular-nums font-semibold text-foreground">
                  {item.total_tokens.toLocaleString()}
                  {item.estimated ? <span className="text-[10px] text-muted-foreground ml-0.5">~</span> : null}
                </td>
                <td className="px-4 py-2.5 text-center">
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
