import { useEffect, useState } from "react";

interface MatchItem {
  id: string | number;
  title?: string;
  summary?: string;
  url?: string;
  league?: string;
  status: string | number;
  status_name?: string;
  team_a?: string;
  team_b?: string;
  score_a?: string | number;
  score_b?: string | number;
  minute?: string | number;
  start_time?: string;
}

interface Props {
  data: MatchItem[];
  dataUpdatedAt?: number;
}

const ROW_CLASS_NAME =
  "grid min-w-0 grid-cols-[3.75rem_minmax(0,1fr)_4.25rem_minmax(0,1fr)] items-center gap-2 overflow-hidden rounded-lg border border-border/50 bg-card/70 px-2 py-2.5 text-sm";

const LEGACY_STATUS_CODES: Record<string, number | undefined> = {
  Fixture: 1,
  Playing: 2,
  Played: 15,
  Postponed: 18,
  Cancelled: 19,
  Uncertain: undefined,
};

function groupByLeague(items: MatchItem[]): Record<string, MatchItem[]> {
  const groups: Record<string, MatchItem[]> = {};
  for (const item of items) {
    const league = item.league || "其他";
    if (!groups[league]) groups[league] = [];
    groups[league].push(item);
  }
  return groups;
}

function statusCode(status: MatchItem["status"]): number | undefined {
  if (typeof status === "number") return status;
  if (/^\d+$/.test(status)) return Number(status);
  return LEGACY_STATUS_CODES[status];
}

function formatClock(date: Date): string {
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function formatStartTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "待定";
}

function scoreFor(match: MatchItem): string {
  if (statusCode(match.status) === 1) return "vs";
  if (match.score_a === "" || match.score_a == null || match.score_b === "" || match.score_b == null) return "-";
  return `${match.score_a} - ${match.score_b}`;
}

function statusFor(match: MatchItem): { label: string; isLive: boolean } {
  const code = statusCode(match.status);
  if (code === 1) return { label: formatStartTime(match.start_time), isLive: false };
  if (code === 2 || code === 8) {
    const rawMinute = match.minute === "" || match.minute == null ? "" : String(match.minute);
    const minute = rawMinute && !rawMinute.endsWith("'") ? `${rawMinute}'` : rawMinute;
    return { label: minute || (code === 8 ? "下半场" : "上半场"), isLive: true };
  }
  if (code === 15) return { label: "完场", isLive: false };
  if (code === 18) return { label: "延期", isLive: false };
  if (code === 19) return { label: "取消", isLive: false };
  return { label: match.status_name || "待定", isLive: false };
}

function MatchRowContent({ match }: { match: MatchItem }) {
  const status = statusFor(match);
  return (
    <>
      <span
        className={`flex min-w-0 items-center gap-1 overflow-hidden text-[11px] font-medium tabular-nums ${
          status.isLive ? "text-red-500" : "text-muted-foreground"
        }`}
      >
        {status.isLive && (
          <span data-testid="live-dot" aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500" />
        )}
        <span className={`truncate ${status.isLive ? "text-red-500" : ""}`}>{status.label}</span>
      </span>
      <span className="min-w-0 truncate font-medium">{match.team_a || "待定"}</span>
      <span className="truncate text-center font-semibold tabular-nums text-foreground">{scoreFor(match)}</span>
      <span className="min-w-0 truncate text-right font-medium">{match.team_b || "待定"}</span>
    </>
  );
}

export function MatchList({ data, dataUpdatedAt }: Props) {
  const [fallbackUpdatedAt, setFallbackUpdatedAt] = useState(() => Date.now());

  useEffect(() => {
    if (dataUpdatedAt == null) setFallbackUpdatedAt(Date.now());
  }, [data, dataUpdatedAt]);

  const groups = groupByLeague(data);
  const updatedAt = formatClock(new Date(dataUpdatedAt ?? fallbackUpdatedAt));

  return (
    <div className="min-w-0 space-y-4 overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-1">
        <h3 className="min-w-0 truncate text-sm font-semibold text-foreground">今日赛程与比分</h3>
        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
          最近更新 {updatedAt}
        </span>
      </header>

      {Object.entries(groups).map(([league, matches]) => (
        <section key={league} className="min-w-0 space-y-1">
          <div className="flex items-center justify-between gap-2 px-1 text-xs font-semibold tracking-wide text-muted-foreground">
            <h4 className="min-w-0 truncate">{league}</h4>
            <span className="shrink-0 tabular-nums">{matches.length} 场</span>
          </div>

          {matches.map((match) => {
            return match.url ? (
              <a
                key={match.id}
                href={match.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`${ROW_CLASS_NAME} transition-colors hover:border-primary/40 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
              >
                <MatchRowContent match={match} />
              </a>
            ) : (
              <div key={match.id} data-testid="match-row" className={ROW_CLASS_NAME}>
                <MatchRowContent match={match} />
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
