// -*- coding: utf-8 -*-
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { fetchJobLogs } from "@/api/client";
import type { JobLogEntry, JobLogResponse } from "@/api/types";
import { cn } from "@/lib/utils";

// 各日志级别对应的 CSS 样式类
const levelClass: Record<string, string> = {
  ERROR: "text-red-500",
  WARNING: "text-amber-500",
  INFO: "text-muted-foreground",
};

// 格式化时间戳的小工具函数，返回易读的 local 时间字符串
function fmtClock(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString();
}

function EntryRow({ entry }: { entry: JobLogEntry }) {
  // 单个日志行的展开/折叠状态管理
  const [open, setOpen] = useState(false);
  const f = entry.fields ?? {};
  // 判断是否为 HTTP 请求相关日志，以便特殊展示
  const isHttp = entry.event.startsWith("upstream.");
  const preview = (f.response_preview as string) ?? "";
  const traceback = (f.traceback as string) ?? "";
  const errText = (f.error as string) ?? "";
  // 仅在有详情（如 HTTP 详情、错误文本、堆栈 traceback）时允许行展开
  const expandable = Boolean(preview || traceback || errText || isHttp);

  return (
    <div className="border-b border-border/40 last:border-0">
      <button
        type="button"
        onClick={() => expandable && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-1 py-1.5 text-left text-xs",
          expandable && "hover:bg-muted/40",
        )}
      >
        {/* 时间列 */}
        <span className="shrink-0 tabular-nums text-muted-foreground">{fmtClock(entry.ts)}</span>
        {/* 阶段标签 */}
        {entry.stage && (
          <Badge variant="outline" className="shrink-0 px-1.5 py-0 text-[10px]">
            {entry.stage}
          </Badge>
        )}
        {/* 日志消息正文 */}
        <span className={cn("shrink-0 font-medium", levelClass[entry.level] ?? "")}>
          {entry.message || entry.event}
        </span>
        {/* HTTP 请求日志行特化展示：状态码，URL，耗时，字节数 */}
        {isHttp && (
          <span className="truncate text-muted-foreground tabular-nums">
            {String(f.status ?? "")} · {String(f.url ?? `${f.host ?? ""}${f.path ?? ""}`)} ·{" "}
            {String(f.duration_ms ?? "")}ms · {String(f.response_bytes ?? "")}B
          </span>
        )}
      </button>
      {/* 展开部分：显示错误文本、堆栈或 JSON 上下文数据 */}
      {open && (
        <pre className="mb-2 ml-12 max-w-full overflow-x-auto whitespace-pre-wrap break-all rounded bg-muted/50 p-2 text-[11px] text-muted-foreground">
          {errText && `error: ${errText}\n`}
          {preview && `response: ${preview}\n`}
          {traceback && traceback}
          {!errText && !preview && !traceback && JSON.stringify(f, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function JobLogModal({
  jobId,
  open,
  onOpenChange,
}: {
  jobId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  // 缓存与累加已拉取到的日志列表
  const [entries, setEntries] = useState<JobLogEntry[]>([]);
  // 缓存当前任务元数据状态
  const [job, setJob] = useState<JobLogResponse["job"] | null>(null);
  // 是否已结束
  const [done, setDone] = useState(false);
  // 利用 ref 保存已拉取日志的最大自增 ID，作为增量请求参数
  const afterIdRef = useRef(0);

  // 当弹窗重新打开或任务切换时，清空之前累加的历史数据并重置游标
  useEffect(() => {
    if (open) {
      afterIdRef.current = 0;
      setEntries([]);
      setDone(false);
      setJob(null);
    }
  }, [open, jobId]);

  // 利用 react-query 挂载增量轮询请求，默认 2s 轮询一次，任务 done 后停止轮询
  const { data } = useQuery({
    queryKey: ["job-logs", jobId],
    queryFn: () => fetchJobLogs(jobId as number, afterIdRef.current),
    enabled: open && jobId != null,
    refetchInterval: (query) => (query.state.data?.done ? false : 2000),
  });

  // 当接收到接口返回时，累加新日志并更新最大游标
  useEffect(() => {
    if (!data) return;
    setJob(data.job);
    if (data.entries.length) {
      afterIdRef.current = data.latest_id;
      setEntries((prev) => [...prev, ...data.entries]);
    }
    setDone(data.done);
  }, [data]);

  // 任务是否处于运行状态
  const running = job != null && !done;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl gap-3 overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            任务日志
            {job && (
              <Badge
                variant={job.status === "failed" ? "destructive" : job.status === "success" ? "default" : "secondary"}
              >
                {job.status}
              </Badge>
            )}
            {running && (
              <span className="flex items-center gap-1.5 text-xs text-blue-500">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                运行中
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* 顶部统计信息显示 */}
        {job && (
          <div className="text-xs text-muted-foreground tabular-nums">
            发现 {job.items_found} · 保存 {job.items_saved}
          </div>
        )}

        {/* 错误原因预览区域 */}
        {job?.error_message && (
          <div className="rounded-md bg-red-100 p-3 dark:bg-red-950/50">
            <div className="mb-1 text-xs font-medium text-red-800 dark:text-red-200">错误原因</div>
            <div className="whitespace-pre-wrap break-all text-sm text-red-700 dark:text-red-300">
              {job.error_message}
            </div>
          </div>
        )}

        {/* 日志时序列表容器 */}
        <div className="min-h-[120px] flex-1 overflow-y-auto rounded-md border border-border/50 bg-card/40 p-2">
          {entries.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">暂无日志</div>
          ) : (
            entries.map((e) => <EntryRow key={e.id} entry={e} />)
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
