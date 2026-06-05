import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, RefreshCw, AlertCircle, CheckCircle2, Clock, XCircle } from "lucide-react";
import { fetchAIJobs, retryAIJob } from "../api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const STATUS_ICONS: Record<string, React.ReactNode> = {
  succeeded: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-500" />,
  pending: <Clock className="h-3.5 w-3.5 text-amber-500" />,
  processing: <RefreshCw className="h-3.5 w-3.5 text-blue-500 animate-spin" />,
  partial: <AlertCircle className="h-3.5 w-3.5 text-amber-500" />,
};

const STATUS_BADGE: Record<string, string> = {
  succeeded: "default",
  failed: "destructive",
  pending: "secondary",
  processing: "secondary",
  partial: "secondary",
} as const;

function formatTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function AdminAIJobsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ai-jobs"],
    queryFn: () => fetchAIJobs(1, 20),
    refetchInterval: 15_000,
  });

  const retryMut = useMutation({
    mutationFn: retryAIJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-jobs"] }),
  });

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  const jobs = data?.items ?? [];

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="AI"
        title="AI 生成任务"
        description="查看 AI 内容加工和主题汇总任务的执行状态，失败任务可手动重试。"
      />

      {isError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          加载失败，请检查后端服务。
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="text-center py-16 border border-dashed rounded-xl">
          <BrainCircuit className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">暂无 AI 生成任务</p>
          <p className="text-xs text-muted-foreground/60 mt-1">当数据源开始执行内容加工时，任务记录会出现在这里</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.id}
              className={`rounded-xl border p-4 ${
                job.status === "failed" ? "border-destructive/30 bg-destructive/5" :
                job.status === "succeeded" ? "border-border/70 bg-card/80" :
                "border-border/70 bg-card/80"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-2">
                  {/* Top row: type + trigger + status */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {STATUS_ICONS[job.status]}
                    <span className="text-sm font-medium">
                      {job.job_type === "item_enrichment" ? "单条加工" :
                       job.job_type === "topic_summary" ? "主题汇总" : job.job_type}
                    </span>
                    <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                      {job.trigger_type === "crawl" ? "定时爬取" :
                       job.trigger_type === "manual" ? "手动触发" :
                       job.trigger_type === "retry" ? "重试" : job.trigger_type}
                    </Badge>
                    <Badge variant={STATUS_BADGE[job.status] as "default" | "destructive" | "secondary" | "outline"} className="text-[10px] h-4 px-1.5">
                      {job.status === "succeeded" ? "成功" :
                       job.status === "failed" ? "失败" :
                       job.status === "processing" ? "处理中" :
                       job.status === "partial" ? "部分成功" : job.status}
                    </Badge>
                  </div>

                  {/* Metrics row */}
                  {job.input_count > 0 && (
                    <div className="text-xs text-muted-foreground">
                      输入 {job.input_count} · 成功 {job.success_count} · 失败 {job.failed_count}
                    </div>
                  )}

                  {/* Error message */}
                  {job.error_message && (
                    <div className="text-xs text-destructive bg-destructive/5 rounded px-2 py-1.5 break-all">
                      {job.error_message}
                    </div>
                  )}

                  {/* Timestamps */}
                  <div className="text-[10px] text-muted-foreground/60">
                    {job.started_at && <span>开始 {formatTime(job.started_at)}</span>}
                    {job.finished_at && <span> · 结束 {formatTime(job.finished_at)}</span>}
                    <span> · 创建 {formatTime(job.created_at)}</span>
                  </div>
                </div>

                {/* Retry button */}
                {job.status === "failed" && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                    onClick={() => retryMut.mutate(job.id)}
                    disabled={retryMut.isPending}
                  >
                    <RefreshCw className={`h-3.5 w-3.5 mr-1 ${retryMut.isPending ? "animate-spin" : ""}`} />
                    重试
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
