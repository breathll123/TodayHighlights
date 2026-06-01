import { Activity, RefreshCw, Trophy } from "lucide-react";

interface FootballTopicOverviewProps {
  matchCount: number;
  dataUpdatedAt?: number;
  isLoading?: boolean;
}

function formatClock(timestamp?: number): string {
  if (!timestamp) return "--:--:--";

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

export function FootballTopicOverview({
  matchCount,
  dataUpdatedAt,
  isLoading = false,
}: FootballTopicOverviewProps) {
  return (
    <section data-testid="football-topic-overview" className="rounded-xl border border-border/75 bg-card/72 px-4 py-4 shadow-sm sm:px-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-primary">
            <Trophy className="h-3.5 w-3.5" aria-hidden="true" />
            Match Center
          </div>
          <h1 className="text-xl font-semibold text-foreground sm:text-2xl">足球主题看板</h1>
          <p className="mt-1.5 text-sm leading-5 text-muted-foreground">
            全球足球联赛实时比分与赛程，球迷屋数据源
          </p>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:flex lg:items-center lg:gap-5">
          <OverviewItem icon={Trophy} label="赛事数量" value={isLoading ? "同步中" : `${matchCount} 场`} />
          <OverviewItem icon={RefreshCw} label="最近更新" value={formatClock(dataUpdatedAt)} />
          <OverviewItem
            icon={Activity}
            label="平台状态"
            value={isLoading ? "连接中" : "运行中"}
            tone="primary"
          />
        </div>
      </div>
    </section>
  );
}

function OverviewItem({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: typeof Trophy;
  label: string;
  value: string;
  tone?: "default" | "primary";
}) {
  return (
    <div className="min-w-0 border-l border-border/70 pl-3.5">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        <Icon className={`h-3.5 w-3.5 ${tone === "primary" ? "text-primary" : ""}`} aria-hidden="true" />
        {label}
      </div>
      <div className={`mt-1 truncate text-sm font-semibold tabular-nums ${tone === "primary" ? "text-primary" : "text-foreground"}`}>
        {value}
      </div>
    </div>
  );
}
