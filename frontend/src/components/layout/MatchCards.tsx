import { useMemo, useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Dot } from "lucide-react";

interface MatchItem {
  id: string | number;
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
  url?: string;
}

interface Props {
  data: MatchItem[];
}

// ── helpers ──

function logoSrc(localUrl?: string, remoteUrl?: string): string {
  if (localUrl) return localUrl;
  if (!remoteUrl) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(remoteUrl)}`;
}

function statusCode(s: string | number): number | undefined {
  if (typeof s === "number") return s;
  return { Fixture: 1, Playing: 2, Played: 15 }[s];
}

function extractDate(startTime?: string): string {
  if (!startTime) return "";
  return startTime.split("T")[0] ?? startTime.split(" ")[0] ?? "";
}

function formatTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "";
}

function resolveImgUrl(url?: string): string {
  if (!url) return "";
  if (url.startsWith("/api/public/media/") || url.startsWith("/api/public/proxy/image")) return url;
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}

function TeamLogo({ url, name, size = "md" }: { url?: string; name?: string; size?: "sm" | "md" }) {
  const [failed, setFailed] = useState(false);
  const cls = size === "md" ? "h-8 w-8 text-[12px]" : "h-6 w-6 text-[10px]";
  if (!url || failed) {
    const initial = (name || "?").charAt(0);
    return (
      <span className={`${cls} shrink-0 rounded-full bg-muted flex items-center justify-center font-bold text-muted-foreground`}>
        {initial}
      </span>
    );
  }
  return (
    <img
      src={resolveImgUrl(url)}
      alt=""
      className={`${cls} shrink-0 rounded-full object-contain`}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}

// ── Card ──

function MatchCard({ m }: { m: MatchItem }) {
  const code = statusCode(m.status);
  const isLive = code === 2 || code === 8;
  const isFinished = code === 15;
  const isFixture = code === 1;
  const timeLabel = formatTime(m.start_time);

  return (
    <a
      href={m.url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className={`shrink-0 w-[200px] rounded-xl border bg-card/80 p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 ${
        isLive
          ? "border-red-500/40 shadow-[0_0_12px_rgba(239,68,68,0.08)]"
          : "border-border/50 hover:border-primary/30"
      }`}
    >
      {/* Top: league + status */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-1 min-w-0">
          {m.logo_league ? (
            <img
              src={logoSrc(m.logo_league_local, m.logo_league)}
              alt=""
              className="h-3.5 w-3.5 shrink-0 rounded object-contain"
              loading="lazy"
              decoding="async"
            />
          ) : (
            <Dot className="h-3 w-3 shrink-0 text-muted-foreground/40" />
          )}
          <span className="text-[10px] text-muted-foreground/70 truncate">{m.league || "—"}</span>
        </div>
        {isLive ? (
          <span className="inline-flex items-center gap-1 shrink-0 rounded-full bg-red-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-red-500">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 motion-safe:animate-pulse" />
            直播
          </span>
        ) : isFinished ? (
          <span className="shrink-0 text-[10px] text-muted-foreground/50">完场</span>
        ) : (
          <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground/60">{timeLabel}</span>
        )}
      </div>

      {/* Teams + Score */}
      <div className="flex items-center gap-2">
        {/* Home */}
        <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
          <TeamLogo url={logoSrc(m.logo_a_local, m.logo_a)} name={m.team_a} size="md" />
          <span className="text-[11px] font-medium text-center truncate w-full leading-tight">{m.team_a || "—"}</span>
        </div>

        {/* Score */}
        <div className="shrink-0 flex flex-col items-center gap-0.5">
          <span className={`text-lg font-bold tabular-nums leading-none ${isLive ? "text-red-500" : "text-foreground"}`}>
            {isFixture ? "vs" : `${m.score_a || "0"} - ${m.score_b || "0"}`}
          </span>
          {isLive && m.minute ? (
            <span className="text-[10px] tabular-nums text-red-500/70">{String(m.minute)}</span>
          ) : null}
        </div>

        {/* Away */}
        <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
          <TeamLogo url={logoSrc(m.logo_b_local, m.logo_b)} name={m.team_b} size="md" />
          <span className="text-[11px] font-medium text-center truncate w-full leading-tight">{m.team_b || "—"}</span>
        </div>
      </div>
    </a>
  );
}

// ── Main ──

export function MatchCards({ data }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  // Filter to today + tomorrow, count by day (local timezone)
  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;

  const { todayMatches, tomorrowMatches, todayCount, tomorrowCount } = useMemo(() => {
    let tm: MatchItem[] = [];
    let tom: MatchItem[] = [];
    for (const m of data) {
      const d = extractDate(m.start_time);
      if (d === todayStr) tm.push(m);
      else if (d === tomorrowStr) tom.push(m);
    }
    return { todayMatches: tm, tomorrowMatches: tom, todayCount: tm.length, tomorrowCount: tom.length };
  }, [data, todayStr, tomorrowStr]);

  const liveCount = todayMatches.filter((m) => {
    const c = statusCode(m.status);
    return c === 2 || c === 8;
  }).length;

  // Separate into Live → Fixture → Played order
  const sorted = useMemo(() => {
    const live = todayMatches.filter((m) => { const c = statusCode(m.status); return c === 2 || c === 8; });
    const fixture = todayMatches.filter((m) => statusCode(m.status) === 1);
    const played = todayMatches.filter((m) => statusCode(m.status) === 15);
    const rest = todayMatches.filter((m) => {
      const c = statusCode(m.status);
      return c !== 2 && c !== 8 && c !== 1 && c !== 15;
    });
    return [...live, ...fixture, ...played, ...rest];
  }, [todayMatches]);

  const updateScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => updateScroll(), [sorted]);

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({ left: dir === "left" ? -220 : 220, behavior: "smooth" });
    setTimeout(updateScroll, 350);
  };

  if (sorted.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        今日暂无比赛
      </div>
    );
  }

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-border/70 bg-card/75 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 border-b border-border/50 bg-muted/30 px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-foreground">今日赛程</h4>
            {liveCount > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-500">
                <span className="h-1.5 w-1.5 rounded-full bg-red-500 motion-safe:animate-pulse" />
                {liveCount} 场进行中
              </span>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">
            共 {todayCount} 场比赛{tomorrowCount > 0 ? ` · 明天 ${tomorrowCount} 场` : ""}
          </p>
        </div>
      </div>

      {/* Card stream */}
      <div className="relative">
        {canScrollLeft && (
          <button
            onClick={() => scroll("left")}
            className="absolute -left-1 top-1/2 z-10 -translate-y-1/2 h-8 w-8 rounded-full bg-card border border-border/60 shadow-sm flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            aria-label="向左滚动"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
        {canScrollRight && (
          <button
            onClick={() => scroll("right")}
            className="absolute -right-1 top-1/2 z-10 -translate-y-1/2 h-8 w-8 rounded-full bg-card border border-border/60 shadow-sm flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            aria-label="向右滚动"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        )}

        <div
          ref={scrollRef}
          className="flex gap-3 overflow-x-auto scrollbar-none px-4 py-4"
          onScroll={updateScroll}
        >
          {sorted.map((m) => (
            <MatchCard key={m.id} m={m} />
          ))}
        </div>
      </div>
    </div>
  );
}
