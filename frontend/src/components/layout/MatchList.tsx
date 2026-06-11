import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CalendarClock, ChevronRight } from "lucide-react";

interface MatchItem {
  id: string | number;
  title?: string;
  summary?: string;
  url?: string;
  league?: string;
  logo_league?: string;
  logo_league_local?: string;
  status: string | number;
  status_name?: string;
  team_a?: string;
  team_b?: string;
  logo_a?: string;
  logo_a_local?: string;
  logo_b?: string;
  logo_b_local?: string;
  score_a?: string | number;
  score_b?: string | number;
  minute?: string | number;
  start_time?: string;
}

interface Props {
  data: MatchItem[];
  dataUpdatedAt?: number;
  defaultFilter?: StatusFilter;
}

type StatusFilter = "all" | "live" | "fixture" | "played";

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

// ── helpers ──

function statusCode(status: MatchItem["status"]): number | undefined {
  if (typeof status === "number") return status;
  if (/^\d+$/.test(status)) return Number(status);
  return LEGACY_STATUS_CODES[status];
}

function formatClock(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hms = [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return `${y}-${m}-${d} ${hms}`;
}

function logoSrc(localUrl?: string, remoteUrl?: string): string {
  if (localUrl) return localUrl;
  if (!remoteUrl) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(remoteUrl)}`;
}

function resolveImgUrl(url?: string): string {
  if (!url) return "";
  if (url.startsWith("/api/public/media/") || url.startsWith("/api/public/proxy/image")) return url;
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}

function formatStartTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "待定";
}

function extractDate(startTime?: string): string {
  if (!startTime) return "";
  return startTime.split("T")[0] ?? startTime.split(" ")[0] ?? "";
}

function dateLabel(dateStr: string): string {
  if (!dateStr || dateStr === "未知") return "待定";
  const d = new Date(dateStr + "T00:00:00");
  if (isNaN(d.getTime())) return dateStr;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = Math.round((target.getTime() - today.getTime()) / 86400000);

  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const wd = weekdays[d.getDay()];
  const m = d.getMonth() + 1;
  const day = d.getDate();

  if (diff === 0) return `今天 ${m}月${day}日 ${wd}`;
  if (diff === 1) return `明天 ${m}月${day}日 ${wd}`;
  if (diff === 2) return `后天 ${m}月${day}日 ${wd}`;
  return `${m}月${day}日 ${wd}`;
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

const FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "live", label: "进行中" },
  { value: "fixture", label: "未开赛" },
  { value: "played", label: "已结束" },
];

// ── components ──

function TeamLogo({ url, name, size = "sm" }: { url?: string; name?: string; size?: "sm" | "xs" }) {
  const [failed, setFailed] = useState(false);
  const dims = size === "sm" ? "h-5 w-5" : "h-4 w-4";

  if (!url || failed) {
    const initial = (name || "?").charAt(0);
    return (
      <span className={`${dims} shrink-0 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold text-muted-foreground`}>
        {initial}
      </span>
    );
  }

  return (
    <img
      src={resolveImgUrl(url)}
      alt=""
      className={`${dims} shrink-0 rounded-full object-contain`}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function MatchRowContent({ match, showAffordance = false }: { match: MatchItem; showAffordance?: boolean }) {
  const status = statusFor(match);
  const startTime = formatStartTime(match.start_time);
  const code = statusCode(match.status);
  const showSecondaryTime = code !== 1 && startTime;

  return (
    <>
      <span className="flex min-w-0 flex-col overflow-hidden text-[11px] font-medium tabular-nums leading-tight">
        <span className={`flex items-center gap-1 ${STATUS_TONE_CLASS[status.tone]}`}>
          {status.tone === "live" && (
            <span
              data-testid="live-dot"
              aria-hidden="true"
              className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500 motion-safe:animate-pulse"
            />
          )}
          <span className="truncate">{status.label}</span>
        </span>
        {showSecondaryTime && (
          <span className="text-[10px] text-muted-foreground/60">{startTime}</span>
        )}
      </span>
      <span className="flex min-w-0 items-center gap-1.5 font-medium">
        <TeamLogo url={logoSrc(match.logo_a_local, match.logo_a)} name={match.team_a} />
        <span className="truncate">{match.team_a || "待定"}</span>
      </span>
      <span className="truncate text-center font-bold tabular-nums text-foreground">{scoreFor(match)}</span>
      <span className={`flex min-w-0 items-center justify-end gap-1.5 font-medium ${showAffordance ? "pr-3" : ""}`}>
        <span className="truncate">{match.team_b || "待定"}</span>
        <TeamLogo url={logoSrc(match.logo_b_local, match.logo_b)} name={match.team_b} />
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

function filterMatches(items: MatchItem[], f: StatusFilter): MatchItem[] {
  if (f === "all") return items;
  return items.filter((m) => {
    const c = statusCode(m.status);
    if (f === "live") return c === 2 || c === 8;
    if (f === "fixture") return c === 1;
    if (f === "played") return c === 15;
    return true;
  });
}

interface DateGroup {
  date: string;
  label: string;
  leagues: Record<string, MatchItem[]>;
}

function groupMatches(items: MatchItem[]): DateGroup[] {
  const dates: Record<string, Record<string, MatchItem[]>> = {};
  for (const item of items) {
    const d = extractDate(item.start_time) || "未知";
    if (!dates[d]) dates[d] = {};
    const league = item.league || "其他";
    if (!dates[d][league]) dates[d][league] = [];
    dates[d][league].push(item);
  }
  return Object.entries(dates)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, leagues]) => ({
      date,
      label: dateLabel(date),
      leagues,
    }));
}

// ── main ──

export function MatchList({ data, dataUpdatedAt, defaultFilter = "all" }: Props) {
  const [fallbackUpdatedAt, setFallbackUpdatedAt] = useState(() => Date.now());
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(defaultFilter);

  useEffect(() => {
    if (dataUpdatedAt == null) setFallbackUpdatedAt(Date.now());
  }, [data, dataUpdatedAt]);

  const filtered = useMemo(() => filterMatches(data, statusFilter), [data, statusFilter]);
  const dateGroups = useMemo(() => groupMatches(filtered), [filtered]);
  const updatedAt = formatClock(new Date(dataUpdatedAt ?? fallbackUpdatedAt));

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      {/* Top bar: semantic title + update time */}
      <div className="flex items-center justify-between gap-3 border-b border-border/50 bg-muted/30 px-3 py-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground/85">
          <CalendarClock className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          比赛中心
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground/60">
          最近更新 {updatedAt}
        </span>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-end gap-0.5 border-b border-border/50 bg-muted/15 px-3 py-1.5">
        <div className="flex items-center gap-0.5">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={`rounded px-2 py-0.5 text-[10px] transition-[color,background-color,transform] active:scale-[0.97] ${
                statusFilter === opt.value
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Date → League → Matches */}
      <motion.div
        key={statusFilter}
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        {dateGroups.map((dg) => (
          <div key={dg.date}>
            <div className="border-b border-border/60 bg-accent/10 px-3 py-1.5 text-[11px] font-semibold text-foreground/80">
              {dg.label}
              <span className="ml-2 font-normal text-muted-foreground">
                {Object.values(dg.leagues).flat().length} 场
              </span>
            </div>

            {Object.entries(dg.leagues).map(([league, matches]) => (
              <section key={`${dg.date}-${league}`} className="min-w-0">
                <div className="flex items-center justify-between gap-2 border-b border-border/45 bg-muted/20 px-3 py-1 text-[10px] font-semibold text-muted-foreground">
                  <h4 className="flex min-w-0 items-center gap-1.5 truncate">
                    <TeamLogo url={logoSrc(matches[0]?.logo_league_local, matches[0]?.logo_league)} name={league} size="xs" />
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
                      className={`${ROW_CLASS_NAME} group transition-[background-color,transform] hover:bg-primary/[0.06] active:scale-[0.99] focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring`}
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
        ))}

        {dateGroups.length === 0 && (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">
            暂无符合条件的比赛
          </div>
        )}
      </motion.div>
    </div>
  );
}
