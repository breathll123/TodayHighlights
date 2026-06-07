import { useQuery } from "@tanstack/react-query";
import { useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { fetchMarketIndices } from "@/api/client";
import type { MarketIndex } from "@/api/types";

function formatTurnover(n: number): string {
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)}万`;
  return n.toLocaleString();
}

function Sparkline({ points, color }: { points: { time: string; price: number }[]; color: string }) {
  if (!points || points.length < 2) return null;
  return (
    <ResponsiveContainer width="100%" height={40}>
      <AreaChart data={points} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="price" stroke={color} strokeWidth={1.5} fill={`url(#grad-${color})`} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function IndexCard({ idx }: { idx: MarketIndex }) {
  const isUp = idx.change_pct >= 0;
  const accent = isUp ? "#ef4444" : "#10b981";
  const trendColor = isUp ? "#ef4444" : "#10b981";

  return (
    <a
      href={idx.url}
      target="_blank"
      rel="noopener noreferrer"
      className="shrink-0 w-[192px] rounded-xl border border-border/70 bg-card/80 p-3.5 transition-all hover:border-border hover:bg-card hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="text-xs font-medium text-muted-foreground truncate">{idx.name}</span>
        <span className="text-[10px] tabular-nums font-semibold shrink-0" style={{ color: accent }}>
          {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct.toFixed(2)}%
        </span>
      </div>

      <p className="text-lg font-bold tabular-nums text-foreground leading-tight mb-1">
        {idx.current.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>

      <p className="text-[10px] text-muted-foreground/60 mb-2 tabular-nums">
        成交 {formatTurnover(idx.turnover)}
      </p>

      {idx.trend?.points ? (
        <Sparkline points={idx.trend.points} color={trendColor} />
      ) : (
        <div className="h-10 rounded bg-muted/30" />
      )}
    </a>
  );
}

export function MarketIndexBar() {
  const { data: indices, isLoading } = useQuery({
    queryKey: ["market-indices"],
    queryFn: fetchMarketIndices,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const updateScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => updateScroll(), [indices]);

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({ left: dir === "left" ? -210 : 210, behavior: "smooth" });
    setTimeout(updateScroll, 350);
  };

  if (isLoading) {
    return (
      <div className="mb-6 flex gap-3 overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="shrink-0 w-[192px] rounded-xl border border-border/50 bg-card/60 animate-pulse p-3.5">
            <div className="h-3 w-16 bg-muted rounded mb-2" />
            <div className="h-5 w-24 bg-muted rounded mb-1" />
            <div className="h-3 w-14 bg-muted rounded mb-2" />
            <div className="h-10 bg-muted/50 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (!indices || indices.length === 0) return null;

  return (
    <div className="mb-6 relative group">
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
        className="flex gap-3 overflow-x-auto scrollbar-none"
        onScroll={updateScroll}
      >
        {indices.map((idx) => (
          <IndexCard key={idx.code} idx={idx} />
        ))}
      </div>
    </div>
  );
}
