import { CalendarDays, Layers3, Radar, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

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
      <section className="rounded-2xl border border-border/80 bg-card/72 p-5 shadow-sm sm:p-6 lg:p-7">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <Radar className="h-3.5 w-3.5" aria-hidden="true" />
              {eyebrow}
            </div>
            <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">
              {title}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
              {description}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:min-w-[520px]">
            <StatusTile icon={Layers3} label="当前主题" value={activeTopic} />
            <StatusTile icon={CalendarDays} label="观测时间" value={formatter.format(new Date())} />
            <StatusTile icon={RefreshCw} label="内容模块" value={isLoading ? "同步中" : `${blockCount} 个`} />
            <StatusTile icon={Radar} label="平台状态" value={isLoading ? "连接中" : "运行中"} tone="primary" />
          </div>
        </div>
      </section>

      {children}
    </div>
  );
}

function StatusTile({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "default" | "primary";
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/45 p-3">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase text-muted-foreground">
        <Icon className={tone === "primary" ? "h-3.5 w-3.5 text-primary" : "h-3.5 w-3.5"} aria-hidden={true} />
        {label}
      </div>
      <div className="truncate text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}
