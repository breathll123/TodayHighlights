import { Activity, Clock3, Layers3, Radar, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import type { ReactNode } from "react";

const easeOutQuint = [0.22, 1, 0.36, 1] as const;

interface DashboardShellProps {
  eyebrow: string;
  title: string;
  description: string;
  activeTopic: string;
  blockCount?: number;
  isLoading?: boolean;
  children: ReactNode;
}

const formatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function DashboardShell({
  eyebrow,
  title,
  description,
  activeTopic,
  blockCount = 0,
  isLoading = false,
  children,
}: DashboardShellProps) {
  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: easeOutQuint }}
        className="w-full max-w-full rounded-lg border border-border/80 bg-card/72 px-4 py-3 shadow-sm sm:px-5"
        aria-label={`${activeTopic}看板概览`}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-medium text-primary">
              <Radar className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>{activeTopic} · {eyebrow}</span>
            </div>
            <div className="mt-1 flex min-w-0 flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-3">
              <h1 className="shrink-0 text-xl font-semibold text-foreground sm:text-2xl">
                {title}
              </h1>
              {description && (
                <p className="line-clamp-2 text-sm leading-5 text-muted-foreground sm:line-clamp-1">
                  {description}
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              {isLoading ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" aria-hidden="true" />
              ) : (
                <Activity className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
              )}
              {isLoading ? "同步中" : "运行中"}
            </span>
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <Layers3 className="h-3.5 w-3.5" aria-hidden="true" />
              {blockCount} 个模块
            </span>
            <time className="inline-flex items-center gap-1.5 whitespace-nowrap tabular-nums">
              <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
              {formatter.format(new Date())} 更新
            </time>
          </div>
        </div>
      </motion.section>

      {children}
    </div>
  );
}
