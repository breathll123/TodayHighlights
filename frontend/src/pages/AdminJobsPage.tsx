import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, AlertCircle, CheckCircle2, Clock, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";

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

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  const jobs = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">任务日志</h1>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">{total}</div>
            <div className="text-xs text-muted-foreground">总任务</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {jobs.filter((j) => j.status === "success").length}
            </div>
            <div className="text-xs text-muted-foreground">本页成功</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">
              {jobs.filter((j) => j.status === "failed").length}
            </div>
            <div className="text-xs text-muted-foreground">本页失败</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {jobs.filter((j) => j.status === "running").length}
            </div>
            <div className="text-xs text-muted-foreground">运行中</div>
          </CardContent>
        </Card>
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
          {jobs.map((j) => {
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
          })}
          {jobs.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm">暂无任务记录</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
