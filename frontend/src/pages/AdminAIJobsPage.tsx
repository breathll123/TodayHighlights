import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BrainCircuit, RefreshCw, AlertCircle, CheckCircle2, Clock, XCircle, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { fetchAIJobs, fetchAIJobsStats, retryAIJob } from "../api/client";
import type { AIGenerationJob } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

const STATUS_ICONS: Record<string, React.ReactNode> = {
  succeeded: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-500" />,
  pending: <Clock className="h-3.5 w-3.5 text-amber-500" />,
  processing: <RefreshCw className="h-3.5 w-3.5 text-blue-500 animate-spin" />,
  partial: <AlertCircle className="h-3.5 w-3.5 text-amber-500" />,
};

const STATUS_BADGE: Record<string, "default" | "destructive" | "secondary" | "outline"> = {
  succeeded: "default", failed: "destructive", pending: "secondary", processing: "secondary", partial: "secondary",
};

const PIE_COLORS = { succeeded: "#10b981", failed: "#ef4444", processing: "#3b82f6", pending: "#f59e0b" };

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-3.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground/70">{label}</p>
      <p className="text-lg font-bold tabular-nums mt-0.5" style={{ color }}>{value.toLocaleString()}</p>
    </div>
  );
}

export function AdminAIJobsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [triggerFilter, setTriggerFilter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const { data: stats } = useQuery({ queryKey: ["ai-jobs-stats"], queryFn: fetchAIJobsStats });
  const { data, isLoading } = useQuery({
    queryKey: ["ai-jobs", page, statusFilter, triggerFilter, dateFrom, dateTo],
    queryFn: () => fetchAIJobs({ page, page_size: 20, status: statusFilter || undefined, trigger_type: triggerFilter || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }),
  });

  const retryMut = useMutation({
    mutationFn: retryAIJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-jobs"] }),
  });

  const toggleExpand = (id: number) => {
    setExpanded((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };

  const jobs = data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));
  const pieData = [
    { name: "成功", value: stats?.total_succeeded ?? 0, fill: PIE_COLORS.succeeded },
    { name: "失败", value: stats?.total_failed ?? 0, fill: PIE_COLORS.failed },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="AI" title="AI 生成任务" description="监控内容加工和主题汇总任务的执行状态、成功率和错误详情。" />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard label="今日成功" value={stats?.today_succeeded ?? 0} color="#10b981" />
        <StatCard label="今日失败" value={stats?.today_failed ?? 0} color="#ef4444" />
        <StatCard label="总成功" value={stats?.total_succeeded ?? 0} color="#10b981" />
        <StatCard label="总失败" value={stats?.total_failed ?? 0} color="#ef4444" />
      </div>

      {/* Pie + Filters */}
      <div className="grid gap-4 lg:grid-cols-[200px_1fr]">
        {pieData.length > 0 && (
          <div className="rounded-xl border border-border/70 bg-card p-3">
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60} innerRadius={32}>
                  {pieData.map((d) => (<Cell key={d.name} fill={d.fill} />))}
                </Pie>
                <Tooltip contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 text-xs mt-1">
              {pieData.map((d) => (<span key={d.name} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: d.fill }} />{d.name} {d.value}</span>))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <span className="text-[10px] text-muted-foreground">状态</span>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="h-8 w-[100px] text-xs"><SelectValue placeholder="全部" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="" className="text-xs">全部</SelectItem>
                <SelectItem value="succeeded" className="text-xs">成功</SelectItem>
                <SelectItem value="failed" className="text-xs">失败</SelectItem>
                <SelectItem value="processing" className="text-xs">处理中</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] text-muted-foreground">触发</span>
            <Select value={triggerFilter} onValueChange={(v) => { setTriggerFilter(v); setPage(1); }}>
              <SelectTrigger className="h-8 w-[110px] text-xs"><SelectValue placeholder="全部" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="" className="text-xs">全部</SelectItem>
                <SelectItem value="crawl" className="text-xs">定时爬取</SelectItem>
                <SelectItem value="manual" className="text-xs">手动触发</SelectItem>
                <SelectItem value="retry" className="text-xs">重试</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] text-muted-foreground">从</span>
            <Input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} className="h-8 w-[130px] text-xs" />
          </div>
          <div className="space-y-1">
            <span className="text-[10px] text-muted-foreground">到</span>
            <Input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} className="h-8 w-[130px] text-xs" />
          </div>
        </div>
      </div>

      {/* Job list */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground text-sm">加载中...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 border border-dashed rounded-xl">
          <BrainCircuit className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">暂无匹配任务</p>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {jobs.map((job: AIGenerationJob) => (
              <div key={job.id} className={`rounded-xl border ${job.status === "failed" ? "border-destructive/30 bg-destructive/5" : "border-border/70 bg-card/80"} overflow-hidden`}>
                <div className="p-4 flex items-start justify-between gap-4 cursor-pointer select-none" onClick={() => toggleExpand(job.id)}>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      {STATUS_ICONS[job.status]}
                      <span className="text-sm font-medium">
                        {job.job_type === "item_enrichment" ? "单条加工" : job.job_type === "topic_summary" ? "主题汇总" : job.job_type}
                      </span>
                      <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                        {job.trigger_type === "crawl" ? "定时" : job.trigger_type === "manual" ? "手动" : job.trigger_type === "retry" ? "重试" : job.trigger_type}
                      </Badge>
                      <Badge variant={STATUS_BADGE[job.status]} className="text-[10px] h-4 px-1.5">
                        {job.status === "succeeded" ? "成功" : job.status === "failed" ? "失败" : job.status === "processing" ? "处理中" : job.status}
                      </Badge>
                    </div>
                    <div className="text-[10px] text-muted-foreground/60">
                      {formatTime(job.created_at)}
                      {job.started_at && <span> · {formatTime(job.started_at)}</span>}
                      {job.input_count > 0 && <span> · 输入 {job.input_count}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {job.status === "failed" && (
                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); retryMut.mutate(job.id); }} disabled={retryMut.isPending}>
                        <RefreshCw className={`h-3 w-3 mr-1 ${retryMut.isPending ? "animate-spin" : ""}`} />重试
                      </Button>
                    )}
                    <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${expanded.has(job.id) ? "rotate-180" : ""}`} />
                  </div>
                </div>

                {expanded.has(job.id) && (job.error_message || job.log_excerpt) && (
                  <div className="border-t border-border/40 bg-muted/20 px-4 py-3 space-y-2 text-xs">
                    {job.error_message && (
                      <div>
                        <p className="font-medium text-destructive/80 mb-1">错误信息</p>
                        <pre className="text-destructive/70 whitespace-pre-wrap break-all font-mono">{job.error_message}</pre>
                      </div>
                    )}
                    {job.log_excerpt && (
                      <div>
                        <p className="font-medium text-muted-foreground/80 mb-1">日志摘要</p>
                        <pre className="text-muted-foreground/70 whitespace-pre-wrap break-all font-mono">{job.log_excerpt}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-muted-foreground">共 {data?.total ?? 0} 条 · 第 {page}/{totalPages} 页</span>
            <div className="flex items-center gap-1">
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
                <ChevronLeft className="h-3 w-3 mr-0.5" />上一页
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
                下一页<ChevronRight className="h-3 w-3 ml-0.5" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
