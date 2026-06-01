import { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";

interface MatchItem {
  id: string | number;
  title?: string;
  summary?: string;
  url?: string;
  league?: string;
  logo_league?: string;
  status: string | number;
  status_name?: string;
  team_a?: string;
  team_b?: string;
  logo_a?: string;
  logo_b?: string;
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
  "relative grid min-w-0 grid-cols-[3.75rem_minmax(0,1fr)_4.25rem_minmax(0,1fr)] items-center gap-2 overflow-hidden border-b border-border/45 bg-transparent px-2.5 py-2.5 text-sm last:border-b-0";

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

function statusFor(match: MatchItem): { label: string; tone: "default" | "live" | "muted" | "warm" } {
  const code = statusCode(match.status);
  if (code === 1) return { label: formatStartTime(match.start_time), tone: "default" };
  if (code === 2 || code === 8) {
    const rawMinute = match.minute === "" || match.minute == null ? "" : String(match.minute);
    const minute = rawMinute && !rawMinute.endsWith("'") ? `${rawMinute}'` : rawMinute;
    return { label: minute || (code === 8 ? "下半场" : "上半场"), tone: "live" };
  }
  if (code === 15) return { label: "完场", tone: "muted" };
  if (code === 18) return { label: "延期", tone: "warm" };
  if (code === 19) return { label: "取消", tone: "warm" };
  return { label: match.status_name || "待定", tone: "default" };
}

const STATUS_TONE_CLASS = {
  default: "text-muted-foreground",
  live: "text-red-500",
  muted: "text-muted-foreground/75",
  warm: "text-amber-500",
};

function MatchRowContent({ match, showAffordance = false }: { match: MatchItem; showAffordance?: boolean }) {
  const status = statusFor(match);
  return (
    <>
      <span
        className={`flex min-w-0 items-center gap-1 overflow-hidden text-[11px] font-medium tabular-nums ${STATUS_TONE_CLASS[status.tone]}`}
      >
        {status.tone === "live" && (
          <span
            data-testid="live-dot"
            aria-hidden="true"
            className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500 motion-safe:animate-pulse"
          />
        )}
        <span className={`truncate ${STATUS_TONE_CLASS[status.tone]}`}>{status.label}</span>
      </span>
      <span className="flex min-w-0 items-center gap-1.5 font-medium">
        {match.logo_a ? (
          <img src={match.logo_a} alt="" className="h-5 w-5 shrink-0 rounded-full object-contain" loading="lazy" />
        ) : null}
        <span className="truncate">{match.team_a || "待定"}</span>
      </span>
      <span className="truncate text-center font-bold tabular-nums text-foreground">{scoreFor(match)}</span>
      <span className={`flex min-w-0 items-center justify-end gap-1.5 font-medium ${showAffordance ? "pr-3" : ""}`}>
        <span className="truncate">{match.team_b || "待定"}</span>
        {match.logo_b ? (
          <img src={match.logo_b} alt="" className="h-5 w-5 shrink-0 rounded-full object-contain" loading="lazy" />
        ) : null}
      </span>
      {showAffordance && (
        <ChevronRight
          data-testid="linked-row-affordance"
          aria-hidden="true"
          className="absolute right-1 h-3.5 w-3.5 text-muted-foreground/50 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
        />
      )}
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
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-background/20">
      <header className="flex items-center justify-between gap-3 border-b border-border/60 bg-card/55 px-3 py-2.5">
        <h3 className="min-w-0 truncate text-sm font-semibold text-foreground">今日赛程与比分</h3>
        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
          最近更新 {updatedAt}
        </span>
      </header>

      {Object.entries(groups).map(([league, matches]) => (
        <section key={league} className="min-w-0">
          <div className="flex items-center justify-between gap-2 border-b border-border/45 bg-muted/20 px-3 py-1.5 text-[11px] font-semibold text-muted-foreground">
            <h4 className="flex min-w-0 items-center gap-1.5 truncate">
              {matches[0]?.logo_league ? (
                <img src={matches[0].logo_league} alt="" className="h-4 w-4 shrink-0 object-contain" loading="lazy" />
              ) : null}
              {league}
            </h4>
            <span className="shrink-0 tabular-nums">{matches.length} 场</span>
          </div>

          {matches.map((match) => {
            return match.url ? (
              <a
                key={match.id}
                href={match.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`${ROW_CLASS_NAME} group transition-colors hover:bg-primary/[0.06] focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring`}
              >
                <MatchRowContent match={match} showAffordance />
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
