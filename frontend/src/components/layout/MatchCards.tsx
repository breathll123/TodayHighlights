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
  score_ht_a?: string;
  score_ht_b?: string;
  minute?: string | number;
  start_time?: string;
}

interface Props {
  data: MatchItem[];
  dataUpdatedAt?: number;
}

// ── helpers ──

function proxyImg(url?: string): string {
  if (!url) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}

function statusCode(s: string | number): number | undefined {
  if (typeof s === "number") return s;
  return { Fixture: 1, Playing: 2, Played: 15 }[s];
}

function formatTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "";
}

function extractDate(startTime?: string): string {
  if (!startTime) return "";
  return startTime.split("T")[0] ?? startTime.split(" ")[0] ?? "";
}

function TeamLogo({ url, name }: { url?: string; name?: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    const initial = (name || "?").charAt(0);
    return (
      <span className="h-5 w-5 shrink-0 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold text-muted-foreground">
        {initial}
      </span>
    );
  }
  return (
    <img
      src={proxyImg(url)}
      alt=""
      className="h-5 w-5 shrink-0 rounded-full object-contain"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function dateLabel(offset: number, baseDate?: Date): string {
  const d = new Date(baseDate || new Date());
  d.setDate(d.getDate() + offset);
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const wd = weekdays[d.getDay()];
  const m = d.getMonth() + 1;
  const day = d.getDate();
  if (offset === 0) return `今天 ${m}/${day}`;
  if (offset === 1) return `明天 ${m}/${day}`;
  return `${wd} ${m}/${day}`;
}

// ── component ──

export function MatchCards({ data }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  // Gather all unique dates within ±7 days from today
  const { availableDates, dateMap } = useMemo(() => {
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

    // Collect all unique dates from data
    const allDates = new Set<string>();
    for (const m of data) {
      const d = extractDate(m.start_time);
      if (d) allDates.add(d);
    }

    // Build a map: date → matches, filtered to near-future
    const map: Record<string, MatchItem[]> = {};
    for (const m of data) {
      const d = extractDate(m.start_time);
      if (d && d >= todayStr) {
        if (!map[d]) map[d] = [];
        map[d].push(m);
      }
    }

    // Sort dates
    const sorted = Object.keys(map).sort();
    return { availableDates: sorted, dateMap: map };
  }, [data]);

  // Default to today
  useEffect(() => {
    if (!selectedDate && availableDates.length > 0) {
      setSelectedDate(availableDates[0]);
    }
  }, [availableDates, selectedDate]);

  const matches = dateMap[selectedDate] || [];
  const todayStr = extractDate(new Date().toISOString());

  // Group matches by league
  const leagueGroups = useMemo(() => {
    const groups: Record<string, MatchItem[]> = {};
    for (const m of matches) {
      const league = m.league || "其他";
      if (!groups[league]) groups[league] = [];
      groups[league].push(m);
    }
    return Object.entries(groups);
  }, [matches]);

  const updateScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    updateScroll();
  }, [availableDates]);

  const scrollDates = (dir: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -200 : 200, behavior: "smooth" });
    setTimeout(updateScroll, 350);
  };

  if (availableDates.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无赛程
      </div>
    );
  }

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      {/* Date tabs — horizontal scroll */}
      <div className="flex items-center border-b border-border/50 bg-muted/30">
        {canScrollLeft && (
          <button
            onClick={() => scrollDates("left")}
            className="shrink-0 h-9 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground"
            aria-label="更早日期"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
        )}

        <div
          ref={scrollRef}
          className="flex items-center gap-0.5 overflow-x-auto flex-1 py-1.5 px-1 scrollbar-none"
          onScroll={updateScroll}
        >
          {availableDates.map((d) => {
            const count = dateMap[d]?.length || 0;
            const isToday = d === todayStr;
            const isSelected = d === selectedDate;
            const dObj = new Date(d + "T00:00:00");
            const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
            const label = `${weekdays[dObj.getDay()]} ${dObj.getMonth() + 1}/${dObj.getDate()}`;

            return (
              <button
                key={d}
                onClick={() => setSelectedDate(d)}
                className={`shrink-0 rounded-md px-2.5 py-1.5 text-xs transition-all ${
                  isSelected
                    ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                }`}
              >
                <span className="block">{label}</span>
                <span className="block text-[10px] opacity-70">{count}场</span>
              </button>
            );
          })}
        </div>

        {canScrollRight && (
          <button
            onClick={() => scrollDates("right")}
            className="shrink-0 h-9 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground"
            aria-label="更晚日期"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Match table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/40 bg-muted/20 text-[10px] text-muted-foreground">
              <th className="text-left font-medium px-3 py-2 w-[52px]">时间</th>
              <th className="text-left font-medium px-2 py-2">主队</th>
              <th className="text-center font-medium px-2 py-2 w-[56px]">比分</th>
              <th className="text-left font-medium px-2 py-2">客队</th>
              <th className="text-center font-medium px-1 py-2 w-[44px]">半场</th>
              <th className="text-center font-medium px-1 py-2 w-[44px]">角球</th>
            </tr>
          </thead>
          <tbody>
            {leagueGroups.map(([league, leagueMatches]) => (
              <>
                {/* League sub-header */}
                <tr key={`h-${league}`}>
                  <td colSpan={6} className="border-b border-border/40 bg-muted/15 px-3 py-1 text-[10px] font-semibold text-muted-foreground">
                    {league}
                    <span className="ml-1.5 font-normal text-muted-foreground/60">{leagueMatches.length}场</span>
                  </td>
                </tr>

                {leagueMatches.map((m) => {
                  const code = statusCode(m.status);
                  const isLive = code === 2 || code === 8;
                  const isFinished = code === 15;
                  const timeLabel = formatTime(m.start_time);

                  return (
                    <tr
                      key={m.id}
                      className="border-b border-border/35 transition-colors hover:bg-primary/[0.03]"
                    >
                      {/* Time + Status */}
                      <td className="px-3 py-2.5">
                        {isLive ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-500">
                            <span className="h-1.5 w-1.5 rounded-full bg-red-500 motion-safe:animate-pulse" />
                            {typeof m.minute === "string" && m.minute ? m.minute : "LIVE"}
                          </span>
                        ) : isFinished ? (
                          <span className="text-[10px] text-muted-foreground/60">完场</span>
                        ) : (
                          <span className="text-[10px] tabular-nums text-muted-foreground">{timeLabel}</span>
                        )}
                      </td>

                      {/* Home team */}
                      <td className="px-2 py-2.5">
                        <div className="flex items-center gap-1.5 justify-end">
                          <span className="text-xs font-medium truncate">{m.team_a}</span>
                          <TeamLogo url={m.logo_a} name={m.team_a} />
                        </div>
                      </td>

                      {/* Score */}
                      <td className="px-2 py-2.5 text-center">
                        <span className="text-xs font-bold tabular-nums text-foreground">
                          {isLive || isFinished
                            ? `${m.score_a || "0"} - ${m.score_b || "0"}`
                            : "vs"}
                        </span>
                      </td>

                      {/* Away team */}
                      <td className="px-2 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <TeamLogo url={m.logo_b} name={m.team_b} />
                          <span className="text-xs font-medium truncate">{m.team_b}</span>
                        </div>
                      </td>

                      {/* Half-time score */}
                      <td className="px-1 py-2.5 text-center">
                        {m.score_ht_a != null && m.score_ht_a !== "" ? (
                          <span className="text-[10px] tabular-nums text-muted-foreground/60">
                            {m.score_ht_a}-{m.score_ht_b}
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/30">—</span>
                        )}
                      </td>

                      {/* Corners */}
                      <td className="px-1 py-2.5 text-center">
                        <span className="text-[10px] text-muted-foreground/30">—</span>
                      </td>
                    </tr>
                  );
                })}
              </>
            ))}
          </tbody>
        </table>

        {matches.length === 0 && selectedDate && (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">
            {selectedDate} 暂无比赛
          </div>
        )}
      </div>
    </div>
  );
}
