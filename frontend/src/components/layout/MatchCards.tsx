import { useMemo, useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

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

function proxyImg(url?: string): string {
  if (!url) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}

function TeamLogo({ url, name }: { url?: string; name?: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    const initial = (name || "?").charAt(0);
    return (
      <span className="h-7 w-7 shrink-0 rounded-full bg-muted flex items-center justify-center text-[11px] font-bold text-muted-foreground">
        {initial}
      </span>
    );
  }
  return (
    <img
      src={proxyImg(url)}
      alt=""
      className="h-7 w-7 shrink-0 rounded-full object-contain"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function statusCode(s: string | number): number | undefined {
  if (typeof s === "number") return s;
  if (/^\d+$/.test(s)) return Number(s);
  return { Fixture: 1, Playing: 2, Played: 15 }[s];
}

function formatTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "";
}

function extractDate(startTime?: string): string {
  if (!startTime) return "";
  return startTime.split("T")[0] ?? startTime.split(" ")[0] ?? "";
}

function dayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
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
  return `${m}月${day}日 ${wd}`;
}

export function MatchCards({ data }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  // Filter to today + tomorrow only, group by date
  const dayGroups = useMemo(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;

    const groups: Record<string, MatchItem[]> = {};
    for (const m of data) {
      const d = extractDate(m.start_time);
      if (d === todayStr || d === tomorrowStr) {
        if (!groups[d]) groups[d] = [];
        groups[d].push(m);
      }
    }
    return Object.entries(groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, matches]) => ({
        date,
        label: dayLabel(date),
        matches,
      }));
  }, [data]);

  const updateScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    updateScroll();
  }, [dayGroups]);

  const scroll = (dir: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -320 : 320, behavior: "smooth" });
    setTimeout(updateScroll, 350);
  };

  if (dayGroups.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        近两日暂无赛程
      </div>
    );
  }

  return (
    <div className="relative min-w-0">
      {/* Scroll arrows */}
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

      {/* Horizontal scroll container */}
      <div
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto scrollbar-none pb-2 px-1"
        onScroll={updateScroll}
      >
        {dayGroups.map((dg) => (
          <div key={dg.date} className="shrink-0 w-[300px]">
            {/* Day header */}
            <div className="flex items-center justify-between gap-2 mb-3 px-2">
              <h4 className="text-sm font-semibold text-foreground/80">{dg.label}</h4>
              <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                {dg.matches.length} 场
              </span>
            </div>

            {/* Match cards */}
            <div className="space-y-2">
              {dg.matches.map((m) => {
                const code = statusCode(m.status);
                const isLive = code === 2 || code === 8;
                const isFinished = code === 15;
                const timeLabel = formatTime(m.start_time);

                return (
                  <a
                    key={m.id}
                    href={m.url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/80 px-3 py-2.5 transition-all hover:border-primary/40 hover:bg-card hover:shadow-sm"
                  >
                    {/* Status + Time */}
                    <div className="shrink-0 w-11 text-center">
                      {isLive ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-red-500 motion-safe:animate-pulse" />
                          {typeof m.minute === "string" && m.minute ? m.minute : "LIVE"}
                        </span>
                      ) : isFinished ? (
                        <span className="text-[10px] text-muted-foreground/60">完场</span>
                      ) : (
                        <span className="text-xs tabular-nums text-muted-foreground">{timeLabel}</span>
                      )}
                    </div>

                    {/* Teams */}
                    <div className="flex-1 min-w-0 flex items-center gap-2">
                      <div className="flex-1 min-w-0 flex items-center gap-1.5 justify-end">
                        <span className="text-xs font-medium truncate">{m.team_a}</span>
                        <TeamLogo url={m.logo_a} name={m.team_a} />
                      </div>

                      {/* Score */}
                      <span className="shrink-0 text-xs font-bold tabular-nums text-foreground w-9 text-center">
                        {isLive || isFinished
                          ? `${m.score_a || "0"} - ${m.score_b || "0"}`
                          : "vs"}
                      </span>

                      <div className="flex-1 min-w-0 flex items-center gap-1.5">
                        <TeamLogo url={m.logo_b} name={m.team_b} />
                        <span className="text-xs font-medium truncate">{m.team_b}</span>
                      </div>
                    </div>
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
