import { useState, useMemo, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Trophy } from "lucide-react";
import { RankBadge, rankRowTone } from "./RankBadge";

interface StandingItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  rank?: number;
  team?: string;
  logo?: string;
  logo_local?: string;
  gp?: string;
  pts?: string;
  wdl?: string;
  gf?: string;
  ga?: string;
  gd?: string;
  league?: string;
  group?: string;
  season?: string;
  updated?: string;
}

interface Props {
  data: StandingItem[];
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
      src={resolveImgUrl(url)}
      alt=""
      className="h-5 w-5 shrink-0 rounded-full object-contain"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

function groupByLeague(items: StandingItem[]): Record<string, StandingItem[]> {
  const groups: Record<string, StandingItem[]> = {};
  for (const item of items) {
    const league = item.league || "其他";
    if (!groups[league]) groups[league] = [];
    groups[league].push(item);
  }
  return groups;
}

export function StandingsTable({ data }: Props) {
  const groups = useMemo(() => groupByLeague(data), [data]);
  const leagueNames = Object.keys(groups);
  const [activeLeague, setActiveLeague] = useState(leagueNames[0] || "");
  const tabScrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const items = groups[activeLeague] || [];
  const first = items[0];
  const season = first?.season || "";
  const updated = first?.updated || "";

  const updateScrollState = () => {
    const el = tabScrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  };

  useEffect(() => {
    updateScrollState();
  }, [leagueNames]);

  const scrollTabs = (dir: "left" | "right") => {
    const el = tabScrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -200 : 200, behavior: "smooth" });
    setTimeout(updateScrollState, 300);
  };

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      {/* League tabs — scrollable with arrows */}
      {leagueNames.length > 1 && (
        <div className="flex items-center border-b border-border/40 bg-gradient-to-b from-muted/40 to-muted/10">
          {/* Left arrow */}
          <button
            onClick={() => scrollTabs("left")}
            disabled={!canScrollLeft}
            className="shrink-0 h-10 w-8 flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-20 disabled:pointer-events-none transition-colors"
            aria-label="向左滚动"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          {/* Tabs */}
          <div
            ref={tabScrollRef}
            className="flex items-center gap-1 overflow-x-auto flex-1 py-2 px-1 scrollbar-none"
            onScroll={updateScrollState}
          >
            {leagueNames.map((name) => (
              <button
                key={name}
                onClick={() => setActiveLeague(name)}
                className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-200 active:scale-[0.98] ${
                  activeLeague === name
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                }`}
              >
                {name}
              </button>
            ))}
          </div>

          {/* Right arrow */}
          <button
            onClick={() => scrollTabs("right")}
            disabled={!canScrollRight}
            className="shrink-0 h-10 w-8 flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-20 disabled:pointer-events-none transition-colors"
            aria-label="向右滚动"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* League header */}
      <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/20 px-3 py-1.5">
        <h4 className="flex min-w-0 items-center gap-1.5 text-xs font-semibold text-foreground/80">
          <Trophy className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          {activeLeague} 积分榜
          {season ? (
            <span className="font-normal text-muted-foreground">{season}</span>
          ) : null}
        </h4>
        {updated ? (
          <span className="shrink-0 text-[10px] text-muted-foreground/60">
            更新 {updated}
          </span>
        ) : null}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[2.5rem_minmax(0,1fr)_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem] gap-1 border-b border-border/40 bg-muted/20 px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
        <span className="text-center">#</span>
        <span>球队</span>
        <span className="text-center">场</span>
        <span className="text-center">胜/平/负</span>
        <span className="text-center">进</span>
        <span className="text-center">失</span>
        <span className="text-center">净</span>
        <span className="text-center font-semibold">分</span>
      </div>

      {/* Rows */}
      {items.map((item, i) => {
        // Insert group separator when group changes (for group-stage tournaments like World Cup)
        const showGroupHeader = item.group && (i === 0 || items[i - 1]?.group !== item.group);
        return (
          <div key={item.id}>
            {showGroupHeader && (
              <div className="flex items-center gap-2 border-b border-border/40 bg-primary/[0.04] px-2.5 py-1.5">
                <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-sm bg-primary/10 px-1 text-[10px] font-bold text-primary">
                  {item.group}
                </span>
                <span className="text-[11px] font-medium text-muted-foreground">{item.group}组</span>
              </div>
            )}
            <motion.a
              href={item.url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              data-rank-row={item.rank}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: Math.min(i, 6) * 0.03, ease: "easeOut" }}
              className={`grid min-h-10 grid-cols-[2.5rem_minmax(0,1fr)_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem] items-center gap-1 border-b border-border/40 px-2.5 py-2 text-xs transition-[background-color,border-color,transform] last:border-b-0 hover:bg-primary/[0.06] active:scale-[0.99] ${rankRowTone(item.rank)}`}
            >
              <RankBadge rank={item.rank} className="justify-center" />
              <span className="flex items-center gap-1.5 truncate">
                <TeamLogo url={logoSrc(item.logo_local, item.logo)} name={item.team} />
                <span className="truncate font-medium">{item.team}</span>
              </span>
              <span className="text-center tabular-nums text-muted-foreground">{item.gp || "-"}</span>
              <span className="text-center tabular-nums text-muted-foreground text-[10px]">{item.wdl || "-"}</span>
              <span className="text-center tabular-nums text-muted-foreground">{item.gf || "-"}</span>
              <span className="text-center tabular-nums text-muted-foreground">{item.ga || "-"}</span>
              <span className={`text-center tabular-nums ${(item.gd || "").startsWith("-") ? "text-green-500" : (item.gd && item.gd !== "0" ? "text-red-500" : "text-muted-foreground")}`}>
                {item.gd || "-"}
              </span>
              <span className="text-center tabular-nums font-bold text-foreground">{item.pts || "-"}</span>
            </motion.a>
          </div>
        );
      })}
    </div>
  );
}
