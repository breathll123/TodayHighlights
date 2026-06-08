import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";
import { fetchMarketIndices } from "@/api/client";
import type { MarketIndex } from "@/api/types";

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtTurnover(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}万亿`;
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}亿`;
  return `${(n / 1e4).toFixed(0)}万`;
}

const CHART_UP = "#ef4444";
const CHART_DN = "#10b981";

function TrendChart({ idx }: { idx: MarketIndex }) {
  if (!idx.trend?.points || idx.trend.points.length < 2) {
    return <div className="h-52 rounded-lg bg-muted/30 flex items-center justify-center text-xs text-muted-foreground">暂无分时数据</div>;
  }
  const isUp = idx.change_pct >= 0;
  const color = isUp ? CHART_UP : CHART_DN;
  const prevClose = idx.trend.prev_close;

  const raw = idx.trend.points;
  // Split into morning (9:30-11:30) and afternoon (13:00-15:00), add gap marker
  const morning = raw.filter((p) => p.time >= "09:30" && p.time <= "11:30");
  const afternoon = raw.filter((p) => p.time >= "13:00" && p.time <= "15:00");

  // Add a single gap point between sessions to break the line
  const chartData = [
    ...morning.map((p) => ({
      time: p.time,
      price: p.price,
      pct: prevClose > 0 ? ((p.price - prevClose) / prevClose) * 100 : 0,
    })),
    { time: "11:30", price: null as number | null, pct: null as number | null },
    ...afternoon.map((p) => ({
      time: p.time,
      price: p.price,
      pct: prevClose > 0 ? ((p.price - prevClose) / prevClose) * 100 : 0,
    })),
  ];

  // Compute pct domain
  const pcts = chartData.filter((d) => d.pct != null).map((d) => d.pct!);
  const pctAbsMax = Math.max(Math.abs(Math.max(...pcts, 0)), Math.abs(Math.min(...pcts, 0)), 0.1);
  const pctDomain: [number, number] = [-pctAbsMax * 1.3, pctAbsMax * 1.3];

  const tickLabels = new Set(["09:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00", "14:30", "15:00"]);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 52, bottom: 0, left: 48 }}>
        <defs>
          <linearGradient id="idx-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="time"
          tick={{ fontSize: 9, fill: "#A1AAB5" }}
          tickLine={false}
          axisLine={{ stroke: "#242E3A" }}
          interval={0}
          tickFormatter={(t: string) => tickLabels.has(t) ? t : ""}
        />
        <YAxis
          yAxisId="price"
          orientation="left"
          domain={["auto", "auto"]}
          tick={{ fontSize: 10, fill: "#A1AAB5" }}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(v: number) => v.toFixed(0)}
        />
        <YAxis
          yAxisId="pct"
          orientation="right"
          domain={pctDomain}
          tick={{ fontSize: 10, fill: color }}
          tickLine={false}
          axisLine={false}
          width={52}
          tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`}
        />
        <Tooltip
          contentStyle={{ background: "#131A21", border: "1px solid #242E3A", borderRadius: 8, fontSize: 12 }}
          labelFormatter={(t) => `时间: ${t}`}
          formatter={(v: unknown) => [typeof v === "number" ? v.toFixed(2) : "—", ""]}
        />
        {prevClose > 0 && (
          <ReferenceLine yAxisId="price" y={prevClose} stroke="#A1AAB5" strokeDasharray="4 3" strokeWidth={0.8} />
        )}
        <Area
          yAxisId="price"
          type="monotone"
          dataKey="price"
          stroke={color}
          strokeWidth={1.5}
          fill="url(#idx-grad)"
          dot={false}
          isAnimationActive={false}
          connectNulls={false}
        />
        {/* Invisible line to anchor the right YAxis */}
        <Area yAxisId="pct" type="monotone" dataKey="pct" stroke="none" fill="none" dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function MarketIndexBar() {
  const { data: indices, isLoading } = useQuery({
    queryKey: ["market-indices"],
    queryFn: fetchMarketIndices,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [active, setActive] = useState("000001");

  if (isLoading) {
    return (
      <div className="mb-6 rounded-xl border border-border/70 bg-card/80 animate-pulse p-5">
        <div className="flex gap-2 mb-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-7 w-20 bg-muted rounded-md" />
          ))}
        </div>
        <div className="h-52 bg-muted/30 rounded-lg" />
      </div>
    );
  }

  if (!indices || indices.length === 0) return null;

  const idx = indices.find((i) => i.code === active) ?? indices[0];
  const isUp = idx.change_pct >= 0;
  const accent = isUp ? CHART_UP : CHART_DN;

  return (
    <div className="mb-6 rounded-xl border border-border/70 bg-card/80">
      {/* Tab bar */}
      <div className="flex items-center border-b border-border/50 px-4 pt-3 pb-0 overflow-x-auto scrollbar-none">
        <div className="flex items-center gap-1 flex-1 min-w-0">
          {indices.map((i) => (
            <button
              key={i.code}
              onClick={() => setActive(i.code)}
              className={`shrink-0 px-3 py-1.5 text-xs font-medium rounded-t-md transition-colors border-b-2 -mb-[1px] ${
                active === i.code
                  ? "border-primary text-primary bg-primary/5"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30"
              }`}
            >
              {i.name}
            </button>
          ))}
        </div>
        {idx.trend?.date && (
          <span className="shrink-0 text-[11px] text-muted-foreground/60 tabular-nums ml-3 pb-1.5">{idx.trend.date}</span>
        )}
      </div>

      {/* Body */}
      <div className="p-5">
        {/* Price header */}
        <div className="flex items-baseline gap-3 mb-3">
          <span className="text-2xl font-bold tabular-nums text-foreground">{fmt(idx.current)}</span>
          <span className="text-sm font-semibold tabular-nums" style={{ color: accent }}>
            {isUp ? "+" : ""}{idx.change_pct.toFixed(2)}%
          </span>
          <span className="text-sm tabular-nums text-muted-foreground">
            {idx.change_amount >= 0 ? "+" : ""}{fmt(idx.change_amount)}
          </span>
        </div>

        {/* OHLC + Turnover row */}
        <div className="flex flex-wrap gap-x-5 gap-y-1 mb-4 text-xs text-muted-foreground">
          {idx.trend && (
            <>
              <span>今开 <span className="text-foreground tabular-nums font-medium">{fmt(idx.trend.points?.[0]?.price ?? 0)}</span></span>
              <span>最高 <span className="tabular-nums font-medium" style={{ color: CHART_UP }}>{fmt(idx.trend.high)}</span></span>
              <span>最低 <span className="tabular-nums font-medium" style={{ color: CHART_DN }}>{fmt(idx.trend.low)}</span></span>
              <span>昨收 <span className="text-foreground tabular-nums font-medium">{fmt(idx.trend.prev_close)}</span></span>
            </>
          )}
          <span>成交额 <span className="text-foreground tabular-nums font-medium">{fmtTurnover(idx.turnover)}</span></span>
          <div className="flex-1" />
          <a href={idx.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-primary transition-colors">
            详情 →
          </a>
        </div>

        <TrendChart idx={idx} />
      </div>
    </div>
  );
}
