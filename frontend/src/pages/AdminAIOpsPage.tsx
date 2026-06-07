import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from "recharts";
import { Activity, Cpu, CheckCircle2, Eye, TrendingUp, XCircle, Zap, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { fetchAITokenUsages, fetchAITokenUsageDetail, fetchAIOpsStats } from "@/api/client";
import type { AITokenUsage, AITokenUsageDetail } from "@/api/types";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AIUsageDetailDrawer } from "@/components/layout/AIUsageDetailDrawer";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CHART_TEAL = "#1DB8A8";
const CHART_GOLD = "#F5A623";
const CHART_MUTED = "#A1AAB5";
const STATUS_COLORS: Record<string, string> = { succeeded: "#10b981", failed: "#ef4444", pending: "#f59e0b", processing: "#3b82f6" };

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
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

export function AdminAIOpsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: stats } = useQuery({ queryKey: ["ai-ops-stats"], queryFn: fetchAIOpsStats });
  const { data, isLoading } = useQuery({
    queryKey: ["ai-token-usages", page, statusFilter],
    queryFn: () => fetchAITokenUsages(page, 20),
  });

  const { data: detail, isLoading: detailLoading, error: detailError } = useQuery({
    queryKey: ["ai-token-usage-detail", selectedId],
    queryFn: () => fetchAITokenUsageDetail(selectedId!),
    enabled: selectedId !== null,
  });

  const items = (data?.items ?? []).filter((i: AITokenUsage) => {
    if (statusFilter === "all") return true;
    return i.job_status === statusFilter;
  });
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));
  const pieData = (stats?.job_status ?? []).filter((s) => s.count > 0).map((s) => ({ name: s.status === "succeeded" ? "成功" : s.status === "failed" ? "失败" : s.status, value: s.count, fill: STATUS_COLORS[s.status] || CHART_MUTED }));

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="AI Ops" title="AI 运营" description="Token 消耗追踪、任务执行状态与模型使用分布。" />

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-5">
        <StatCard icon={Zap} label="今日 Token" value={stats?.today_tokens.toLocaleString() ?? "—"} color="#F5A623" />
        <StatCard icon={Activity} label="今日调用" value={`${stats?.today_calls ?? "—"}`} color={CHART_TEAL} />
        <StatCard icon={CheckCircle2} label="今日成功" value={`${stats?.today_succeeded ?? "—"}`} color="#10b981" />
        <StatCard icon={XCircle} label="今日失败" value={`${stats?.today_failed ?? "—"}`} color="#ef4444" />
        <StatCard icon={Cpu} label="活跃模型" value={`${stats?.active_models ?? "—"}`} color="#8b5cf6" />
      </div>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border/70 bg-card p-4">
          <h4 className="text-xs font-medium text-muted-foreground mb-2">Token 趋势 (14 天)</h4>
          {stats?.daily_trend?.length ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={stats.daily_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.4)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_MUTED }} tickFormatter={(v: string) => v.slice(5)} />
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="total_tokens" stroke={CHART_TEAL} fill={`${CHART_TEAL}22`} strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-muted-foreground text-center py-10">暂无</p>}
        </div>

        <div className="rounded-xl border border-border/70 bg-card p-4">
          <h4 className="text-xs font-medium text-muted-foreground mb-2">任务状态（今日）</h4>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={65} innerRadius={38}>
                  {pieData.map((d) => (<Cell key={d.name} fill={d.fill} />))}
                </Pie>
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-muted-foreground text-center py-10">暂无</p>}
          <div className="flex justify-center gap-3 text-[10px] mt-1">
            {pieData.map((d) => (<span key={d.name} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: d.fill }} />{d.name} {d.value}</span>))}
          </div>
        </div>

        <div className="rounded-xl border border-border/70 bg-card p-4">
          <h4 className="text-xs font-medium text-muted-foreground mb-2">模型分布</h4>
          {stats?.by_model?.length ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={stats.by_model}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.4)" />
                <XAxis dataKey="model_name" tick={{ fontSize: 10, fill: CHART_MUTED }} />
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="total_tokens" fill={CHART_GOLD} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-muted-foreground text-center py-10">暂无</p>}
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground">状态</span>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <SelectTrigger className="h-8 w-[100px] text-xs"><SelectValue placeholder="全部" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">全部</SelectItem>
            <SelectItem value="succeeded" className="text-xs">成功</SelectItem>
            <SelectItem value="failed" className="text-xs">失败</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Merged list */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground text-sm">加载中...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 border border-dashed rounded-xl text-sm text-muted-foreground">暂无记录</div>
      ) : (
        <>
          <div className="space-y-2">
            {items.map((item: AITokenUsage) => (
              <div key={item.id} className="rounded-xl border border-border/70 bg-card/80 overflow-hidden">
                <div
                  className="p-4 flex items-start justify-between gap-4 cursor-pointer select-none"
                  onClick={() => item.job_error ? setExpanded((prev) => { const n = new Set(prev); n.has(item.id) ? n.delete(item.id) : n.add(item.id); return n; }) : undefined}
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      {item.job_status === "succeeded" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : item.job_status === "failed" ? <XCircle className="h-3.5 w-3.5 text-red-500" /> : <Activity className="h-3.5 w-3.5 text-muted-foreground" />}
                      <span className="text-sm font-medium">{item.topic}</span>
                      <span className="text-xs text-muted-foreground truncate max-w-[140px]" title={item.block_title}>{item.block_title || item.usage_type}</span>
                      <span className="text-xs font-mono text-muted-foreground/70">{item.model_name}</span>
                    </div>
                    <div className="text-[10px] text-muted-foreground/60">{formatTime(item.created_at)}</div>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <div className="text-right">
                      <span className="text-xs tabular-nums" style={{ color: CHART_TEAL }}>{item.prompt_tokens.toLocaleString()}</span>
                      <span className="text-xs text-muted-foreground mx-1">/</span>
                      <span className="text-xs tabular-nums" style={{ color: CHART_GOLD }}>{item.completion_tokens.toLocaleString()}</span>
                      <span className="text-xs text-muted-foreground mx-1">/</span>
                      <span className="text-xs tabular-nums font-semibold">{item.total_tokens.toLocaleString()}</span>
                    </div>
                    <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={(e) => { e.stopPropagation(); setSelectedId(item.id); }}>
                      <Eye className="h-3 w-3" />详情
                    </Button>
                    {item.job_error && <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${expanded.has(item.id) ? "rotate-180" : ""}`} />}
                  </div>
                </div>
                {expanded.has(item.id) && item.job_error && (
                  <div className="border-t border-border/40 bg-muted/20 px-4 py-3">
                    <p className="text-xs font-medium text-destructive/80 mb-1">错误信息</p>
                    <pre className="text-xs text-destructive/70 whitespace-pre-wrap break-all font-mono">{item.job_error}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-muted-foreground">共 {data?.total ?? 0} 条 · 第 {page}/{totalPages} 页</span>
            <div className="flex items-center gap-1">
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}><ChevronLeft className="h-3 w-3 mr-0.5" />上一页</Button>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}><ChevronRight className="h-3 w-3 ml-0.5" />下一页</Button>
            </div>
          </div>
        </>
      )}

      <AIUsageDetailDrawer open={selectedId !== null} detail={detail ?? null} isLoading={detailLoading} error={detailError ? (detailError as Error).message : null} onClose={() => setSelectedId(null)} />
    </div>
  );
}
