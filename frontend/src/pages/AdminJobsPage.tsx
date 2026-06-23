import { useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { fetchJobs } from "../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, AlertCircle, CheckCircle2, Clock, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AnimatedNumber } from "@/components/layout/AnimatedNumber";
import { Skeleton } from "@/components/ui/skeleton";

const statusLabel: Record<string, string> = {
  success: "成功", failed: "失败", running: "运行中", pending: "等待中",
};
const statusIcon: Record<string, typeof AlertCircle> = {
  success: CheckCircle2, failed: AlertCircle, running: RotateCw, pending: Clock,
};
const triggerLabel: Record<string, string> = {
  manual: "手动", scheduled: "定时",
};

function fmtTime(ts: string | null) {
  if (!ts) return "-";
  const d = new Date(ts);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}

const PAGE_SIZE = 20;

export function AdminJobsPage() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", page],
    queryFn: () => fetchJobs(page, PAGE_SIZE),
    refetchInterval: 10000,
  });

  const jobs = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const summary: { label: string; value: number; glow: string; numberClass: string }[] = [
    { label: "总任务", value: total, glow: "#1DB8A8", numberClass: "text-foreground" },
    { label: "本页成功", value: jobs.filter((j) => j.status === "success").length, glow: "#10b981", numberClass: "text-green-500" },
    { label: "本页失败", value: jobs.filter((j) => j.status === "failed").length, glow: "#ef4444", numberClass: "text-red-500" },
    { label: "运行中", value: jobs.filter((j) => j.status === "running").length, glow: "#3b82f6", numberClass: "text-blue-500" },
  ];

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Jobs"
        title="任务日志"
        description="观察采集任务的运行状态、保存数量和错误摘要，快速判断来源健康度。"
      />

      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[88px] rounded-xl" style={{ animationDelay: `${i * 50}ms` }} />
            ))
          : summary.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.32, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
                className="stat-card rounded-xl border border-border/70 bg-card p-4 text-center"
                style={{ "--glow": s.glow } as CSSProperties}
              >
                <div className={cn("text-2xl font-bold tabular-nums", s.numberClass)}>
                  <AnimatedNumber value={s.value} animateOnMount durationMs={800} format={(n) => String(Math.round(n))} />
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">{s.label}</div>
              </motion.div>
            ))}
      </div>

      {/* Job list */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>爬取任务列表</CardTitle>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Button
                variant="outline" size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span>第 {page} / {totalPages} 页</span>
              <Button
                variant="outline" size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-[60px] rounded-lg" style={{ animationDelay: `${i * 60}ms` }} />
            ))
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">暂无任务记录</div>
          ) : (
            jobs.map((j) => {
            const Icon = statusIcon[j.status] ?? Clock;
            const isExpanded = expanded.has(j.id);
            const isFailed = j.status === "failed";

            return (
              <div
                key={j.id}
                className={cn(
                  "rounded-lg border p-4 transition-colors",
                  isFailed && "border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                )}
              >
                <div className="flex items-center gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">{j.source_name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {triggerLabel[j.trigger_type] ?? j.trigger_type} · {fmtTime(j.started_at)} → {fmtTime(j.finished_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-muted-foreground">
                      发现 <strong>{j.items_found}</strong> · 保存 <strong>{j.items_saved}</strong>
                    </span>
                  </div>
                  <Badge
                    variant={j.status === "failed" ? "destructive" : j.status === "success" ? "default" : "secondary"}
                    className="gap-1"
                  >
                    <Icon className="w-3 h-3" />
                    {statusLabel[j.status] ?? j.status}
                  </Badge>
                  {isFailed && j.error_message && (
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => toggle(j.id)}>
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </Button>
                  )}
                </div>
                {isExpanded && isFailed && (
                  <div className="mt-3 pt-3 border-t space-y-2">
                    <div className="rounded-md bg-red-100 dark:bg-red-950/50 p-3">
                      <div className="text-xs font-medium text-red-800 dark:text-red-200 mb-1">错误原因</div>
                      <div className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap break-all">
                        {j.error_message}
                      </div>
                    </div>
                    {j.log_excerpt && (
                      <div className="rounded-md bg-muted/50 p-3">
                        <div className="text-xs font-medium text-muted-foreground mb-1">日志摘要</div>
                        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all">{j.log_excerpt}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
