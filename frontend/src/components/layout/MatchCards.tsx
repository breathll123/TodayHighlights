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

function extractDate(startTime?: string): string {
  if (!startTime) return "";
  return startTime.split("T")[0] ?? startTime.split(" ")[0] ?? "";
}

function formatTime(startTime?: string): string {
  return startTime?.match(/[T ](\d{2}:\d{2})/)?.[1] ?? "";
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

// ── Date tab bar ──

function DateTabs({
  dates,
  selected,
  onSelect,
  dateCounts,
}: {
  dates: string[];
  selected: string;
  onSelect: (d: string) => void;
  dateCounts: Record<string, number>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const updateScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => updateScroll(), [dates]);

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({ left: dir === "left" ? -240 : 240, behavior: "smooth" });
    setTimeout(updateScroll, 350);
  };

  const todayStr = extractDate(new Date().toISOString());

  return (
    <div className="flex items-center gap-0.5">
      <button
        onClick={() => scroll("left")}
        disabled={!canScrollLeft}
        className="shrink-0 h-8 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-20"
        aria-label="更早"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>
      <div ref={scrollRef} className="flex items-center gap-1 overflow-x-auto flex-1 scrollbar-none" onScroll={updateScroll}>
        {dates.map((d) => {
          const count = dateCounts[d] || 0;
          const isToday = d === todayStr;
          const isSelected = d === selected;
          const dObj = new Date(d + "T00:00:00");
          const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
          const wd = weekdays[dObj.getDay()];
          const m = dObj.getMonth() + 1;
          const day = dObj.getDate();

          return (
            <button
              key={d}
              onClick={() => onSelect(d)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-center transition-all ${
                isSelected
                  ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <span className="block text-[11px] leading-tight">
                {isToday ? "今天" : wd}
              </span>
              <span className="block text-[13px] font-semibold leading-tight">{`${m}/${day}`}</span>
              <span className="block text-[10px] opacity-70">{count}场</span>
            </button>
          );
        })}
      </div>
      <button
        onClick={() => scroll("right")}
        disabled={!canScrollRight}
        className="shrink-0 h-8 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-20"
        aria-label="更晚"
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ── Match table ──

export function MatchCards({ data }: Props) {
  // Build date index
  const { dates, dateMap, dateCounts } = useMemo(() => {
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

    const map: Record<string, MatchItem[]> = {};
    const counts: Record<string, number> = {};
    for (const m of data) {
      const d = extractDate(m.start_time);
      if (d && d >= todayStr) {
        if (!map[d]) map[d] = [];
        map[d].push(m);
        counts[d] = (counts[d] || 0) + 1;
      }
    }
    return { dates: Object.keys(map).sort(), dateMap: map, dateCounts: counts };
  }, [data]);

  const [selectedDate, setSelectedDate] = useState(dates[0] || "");

  const matches = dateMap[selectedDate] || [];

  // Group by league
  const leagueGroups = useMemo(() => {
    const groups: Record<string, MatchItem[]> = {};
    for (const m of matches) {
      const league = m.league || "其他";
      if (!groups[league]) groups[league] = [];
      groups[league].push(m);
    }
    return Object.entries(groups);
  }, [matches]);

  if (dates.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无赛程
      </div>
    );
  }

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      {/* Date navbar */}
      <div className="border-b border-border/50 bg-muted/30 px-2 py-1.5">
        <DateTabs dates={dates} selected={selectedDate} onSelect={setSelectedDate} dateCounts={dateCounts} />
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/40 bg-muted/20 text-[10px] text-muted-foreground">
              <th className="text-left font-medium pl-3 pr-2 py-2 w-[52px]">时间</th>
              <th className="text-right font-medium px-2 py-2">主队</th>
              <th className="text-center font-medium px-2 py-2 w-[52px]">比分</th>
              <th className="text-left font-medium px-2 py-2">客队</th>
              <th className="text-center font-medium px-1 py-2 w-[42px]">半场</th>
            </tr>
          </thead>
          <tbody>
            {leagueGroups.map(([league, leagueMatches]) => (
              <tr key={`h-${league}`} className="border-b border-border/25 bg-muted/10">
                <td colSpan={5} className="pl-3 pr-2 py-1 text-[10px] font-semibold text-muted-foreground">
                  {league}
                </td>
              </tr>
            ))}
            {/* Interleave league headers with rows */}
            {leagueGroups.flatMap(([league, leagueMatches]) =>
              leagueMatches.map((m) => {
                const code = statusCode(m.status);
                const isLive = code === 2 || code === 8;
                const isFinished = code === 15;
                const timeLabel = formatTime(m.start_time);

                return (
                  <tr key={m.id} className="border-b border-border/30 transition-colors hover:bg-primary/[0.03]">
                    <td className="pl-3 pr-2 py-2.5">
                      {isLive ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-red-500 motion-safe:animate-pulse" />
                          {typeof m.minute === "string" && m.minute ? m.minute : "LIVE"}
                        </span>
                      ) : isFinished ? (
                        <span className="text-[10px] text-muted-foreground/60">完场</span>
                      ) : (
                        <span className="text-[11px] tabular-nums text-muted-foreground">{timeLabel}</span>
                      )}
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-1.5 justify-end">
                        <span className="text-xs font-medium truncate max-w-[120px]">{m.team_a}</span>
                        <TeamLogo url={m.logo_a} name={m.team_a} />
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <span className={`text-xs font-bold tabular-nums ${isLive ? "text-red-500" : "text-foreground"}`}>
                        {isLive || isFinished ? `${m.score_a || "0"} - ${m.score_b || "0"}` : "vs"}
                      </span>
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <TeamLogo url={m.logo_b} name={m.team_b} />
                        <span className="text-xs font-medium truncate max-w-[120px]">{m.team_b}</span>
                      </div>
                    </td>
                    <td className="px-1 py-2.5 text-center">
                      {m.score_ht_a != null && m.score_ht_a !== "" ? (
                        <span className="text-[10px] tabular-nums text-muted-foreground/60">
                          {m.score_ht_a}-{m.score_ht_b}
                        </span>
                      ) : (
                        <span className="text-[10px] text-muted-foreground/25">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
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
