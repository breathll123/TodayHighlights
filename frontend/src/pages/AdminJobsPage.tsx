// -*- coding: utf-8 -*-
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight, AlertCircle, CheckCircle2, Clock, RotateCw, Activity, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AnimatedNumber } from "@/components/layout/AnimatedNumber";
import { Skeleton } from "@/components/ui/skeleton";
import { JobLogModal } from "@/components/admin/JobLogModal";

const statusLabel: Record<string, string> = {
  success: "成功", failed: "失败", running: "运行中", pending: "等待中",
};
const statusIcon: Record<string, typeof AlertCircle> = {
  success: CheckCircle2, failed: AlertCircle, running: RotateCw, pending: Clock,
};
const triggerLabel: Record<string, string> = {
  manual: "手动", scheduled: "定时",
};

// 格式化展示日期的辅助函数
function fmtTime(ts: string | null) {
  if (!ts) return "-";
  const d = new Date(ts);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}

const PAGE_SIZE = 20;

export function AdminJobsPage() {
  const [page, setPage] = useState(1);
  const [inputValue, setInputValue] = useState(""); // 存放输入框中的即时查询内容
  const [search, setSearch] = useState(""); // 触发真正后端检索的搜索词
  // 选中的用于在弹窗中展示日志的任务 ID，为 null 时弹窗关闭
  const [logJobId, setLogJobId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", page, search], // 当搜索词或页码变化时，重新获取数据
    queryFn: () => fetchJobs(page, PAGE_SIZE, search),
    refetchInterval: 10000,
  });

  // 处理输入内容变化，清空搜索时即时刷新
  const handleInputChange = (val: string) => {
    setInputValue(val);
    if (val === "") {
      setSearch("");
      setPage(1);
    }
  };

  // 执行搜索动作并将页码置为 1
  const handleSearch = () => {
    setSearch(inputValue);
    setPage(1);
  };

  // 在搜索框中按下回车触发搜索
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const jobs = data?.items ?? [];
  const total = data?.total ?? 0;
  const stats = data?.stats ?? {
    total,
    success: jobs.filter((j) => j.status === "success").length,
    failed: jobs.filter((j) => j.status === "failed").length,
    running: jobs.filter((j) => j.status === "running").length,
    pending: jobs.filter((j) => j.status === "pending").length,
  };
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const statItems = [
    { label: "成功", value: stats.success, className: "text-emerald-500", dotClassName: "bg-emerald-500" },
    { label: "失败", value: stats.failed, className: "text-red-500", dotClassName: "bg-red-500" },
    { label: "运行中", value: stats.running, className: "text-blue-500", dotClassName: "bg-blue-500" },
  ];

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Jobs"
        title="任务日志"
        description="观察采集任务的运行状态、保存数量和错误摘要，快速判断来源健康度。"
      />

      {/* Summary */}
      {isLoading ? (
        <Skeleton className="h-[92px] rounded-xl" />
      ) : (
        <Card className="overflow-hidden border-border/70 bg-card/80">
          <CardContent className="p-0">
            <div className="flex flex-col gap-0 md:flex-row md:items-stretch">
              <div className="flex items-center gap-4 border-b border-border/70 px-5 py-4 md:w-[260px] md:border-b-0 md:border-r">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">总任务</div>
                  <div className="mt-0.5 text-2xl font-semibold tabular-nums text-foreground">
                    <AnimatedNumber value={stats.total} animateOnMount durationMs={700} format={(n) => String(Math.round(n))} />
                  </div>
                </div>
              </div>

              <div className="grid flex-1 grid-cols-3 divide-x divide-border/60">
                {statItems.map((item) => (
                  <div key={item.label} className="px-4 py-4 md:px-6">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className={cn("h-1.5 w-1.5 rounded-full", item.dotClassName)} />
                      {item.label}
                    </div>
                    <div className={cn("mt-1.5 text-xl font-semibold tabular-nums md:text-2xl", item.className)}>
                      <AnimatedNumber value={item.value} animateOnMount durationMs={700} format={(n) => String(Math.round(n))} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Job list */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>爬取任务列表</CardTitle>
            
            {/* 搜索与翻页控制区 */}
            <div className="flex flex-wrap items-center gap-3 flex-1 justify-end">
              <div className="flex max-w-xs w-full items-center gap-1.5">
                <Input
                  placeholder="搜索数据源、状态、类型、日志原因..."
                  value={inputValue}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="h-8 text-xs bg-background/50 border-border/70"
                />
                <Button size="sm" className="h-8 text-xs shrink-0" onClick={handleSearch}>
                  搜索
                </Button>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-muted-foreground border border-border/50 rounded-md p-1 bg-muted/20">
                <Button
                  variant="ghost" size="icon" className="h-6 w-6"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </Button>
                <span className="px-1.5 tabular-nums">第 {page} / {totalPages} 页</span>
                <Button
                  variant="ghost" size="icon" className="h-6 w-6"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
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
                    {/* 查看任务日志详情的模态弹窗入口按钮 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1 px-2 text-xs"
                      onClick={() => setLogJobId(j.id)}
                    >
                      <FileText className="h-3.5 w-3.5" />
                      日志
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* 挂载结构化日志模态弹窗 */}
      <JobLogModal
        jobId={logJobId}
        open={logJobId != null}
        onOpenChange={(o) => { if (!o) setLogJobId(null); }}
      />
    </div>
  );
}
