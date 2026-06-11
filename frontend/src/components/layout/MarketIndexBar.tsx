import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";
import { fetchMarketIndices } from "@/api/client";
import type { MarketIndex, MarketIndexTrend } from "@/api/types";

const easeOutQuint = [0.22, 1, 0.36, 1] as const;

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
const CHART_LINE = "#38bdf8";

export type MarketIndexChartDatum = {
  x: number;
  time: string;
  price: number;
  pct: number;
};

export const MARKET_TIME_TICKS = [0, 30, 60, 90, 120, 150, 180, 210, 240];
const MOBILE_MARKET_TIME_TICKS = [0, 60, 120, 180, 240];

export function getMarketIndexChartLayout(isMobile: boolean) {
  return isMobile
    ? {
        ticks: MOBILE_MARKET_TIME_TICKS,
        axisWidth: 38,
        horizontalMargin: 4,
      }
    : {
        ticks: MARKET_TIME_TICKS,
        axisWidth: 44,
        horizontalMargin: 8,
      };
}

const MARKET_TIME_LABELS: Record<number, string> = {
  0: "09:30",
  30: "10:00",
  60: "10:30",
  90: "11:00",
  120: "13:00",
  150: "13:30",
  180: "14:00",
  210: "14:30",
  240: "15:00",
};

function toMarketMinute(time: string): number | null {
  const [hourText, minuteText] = time.split(":");
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;

  const total = hour * 60 + minute;
  const morningStart = 9 * 60 + 30;
  const afternoonStart = 13 * 60;
  if (total >= morningStart && total <= 11 * 60 + 30) return total - morningStart;
  if (total >= afternoonStart && total <= 15 * 60) return 120 + (total - afternoonStart);
  return null;
}

export function buildMarketIndexChartData(points: MarketIndexTrend["points"], referencePrice: number): MarketIndexChartDatum[] {
  return points
    .flatMap((p) => {
      const x = toMarketMinute(p.time);
      if (x == null) return [];
      return [{
        x,
        time: p.time,
        price: p.price,
        pct: referencePrice > 0 ? ((p.price - referencePrice) / referencePrice) * 100 : 0,
      }];
    })
    .sort((a, b) => a.x - b.x);
}

export function priceToReferencePct(price: number, referencePrice: number): number {
  return referencePrice > 0 ? ((price - referencePrice) / referencePrice) * 100 : 0;
}

export function buildPriceDomain(chartData: MarketIndexChartDatum[], openPrice: number, high: number, low: number): [number, number] {
  const prices = chartData.map((d) => d.price).filter((price) => Number.isFinite(price));
  const baseMin = Math.min(...prices, openPrice, high || openPrice, low || openPrice);
  const baseMax = Math.max(...prices, openPrice, high || openPrice, low || openPrice);
  const padding = Math.max((baseMax - baseMin) * 0.08, openPrice * 0.0005, 1);
  return [baseMin - padding, baseMax + padding];
}

function PercentAxisTick({ x, y, payload, referencePrice }: { x?: number; y?: number; payload?: { value?: number }; referencePrice: number }) {
  const price = payload?.value ?? referencePrice;
  const value = priceToReferencePct(price, referencePrice);
  const color = price > referencePrice ? CHART_UP : price < referencePrice ? CHART_DN : "#A1AAB5";
  return (
    <text x={x} y={y} dy={4} textAnchor="start" fill={color} fontSize={10} className="tabular-nums">
      {`${value > 0 ? "+" : ""}${value.toFixed(2)}%`}
    </text>
  );
}

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string | number; value?: unknown; payload?: MarketIndexChartDatum }>;
}) {
  if (!active || !payload?.length) return null;
  const datum = payload.find((item) => item.payload)?.payload;
  if (!datum) return null;

  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg">
      <div className="mb-1 font-medium tabular-nums">{datum.time}</div>
      <div className="flex min-w-28 items-center justify-between gap-4 text-muted-foreground">
        <span>指数</span>
        <span className="text-popover-foreground tabular-nums">{datum.price.toFixed(2)}</span>
      </div>
      <div className="mt-1 flex min-w-28 items-center justify-between gap-4 text-muted-foreground">
        <span>涨幅</span>
        <span className="tabular-nums" style={{ color: datum.pct >= 0 ? CHART_UP : CHART_DN }}>
          {datum.pct >= 0 ? "+" : ""}
          {datum.pct.toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

function useMobileChartLayout(): boolean {
  const query = "(max-width: 640px)";
  const [isMobile, setIsMobile] = useState(() => (
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false
  ));

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const mediaQuery = window.matchMedia(query);
    const update = () => setIsMobile(mediaQuery.matches);
    update();
    mediaQuery.addEventListener("change", update);
    return () => mediaQuery.removeEventListener("change", update);
  }, []);

  return isMobile;
}

function TrendChart({ idx }: { idx: MarketIndex }) {
  const isMobile = useMobileChartLayout();
  const chartLayout = getMarketIndexChartLayout(isMobile);

  if (!idx.trend?.points || idx.trend.points.length < 2) {
    return <div className="h-52 rounded-lg bg-muted/30 flex items-center justify-center text-xs text-muted-foreground">暂无分时数据</div>;
  }
  const openPrice = idx.trend.points[0]?.price ?? idx.current;

  const chartData = buildMarketIndexChartData(idx.trend.points, openPrice);
  const priceDomain = buildPriceDomain(chartData, openPrice, idx.trend.high, idx.trend.low);

  return (
    <div className="relative">
      <div
        className="pointer-events-none absolute top-1 z-10 rounded bg-card/85 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground shadow-sm"
        style={{ left: chartLayout.axisWidth + chartLayout.horizontalMargin }}
      >
        开盘 {fmt(openPrice)}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart
          data={chartData}
          margin={{
            top: 18,
            right: chartLayout.horizontalMargin,
            bottom: 0,
            left: chartLayout.horizontalMargin,
          }}
        >
          <defs>
            <linearGradient id="idx-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_LINE} stopOpacity={0.2} />
              <stop offset="100%" stopColor={CHART_LINE} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 240]}
            ticks={chartLayout.ticks}
            tick={{ fontSize: 9, fill: "#A1AAB5" }}
            tickLine={false}
            axisLine={{ stroke: "#242E3A" }}
            interval={0}
            tickFormatter={(t: number) => MARKET_TIME_LABELS[t] ?? ""}
          />
          <YAxis
            yAxisId="price"
            orientation="left"
            domain={priceDomain}
            tick={{ fontSize: 10, fill: "#A1AAB5" }}
            tickLine={false}
            axisLine={false}
            width={chartLayout.axisWidth}
            tickFormatter={(v: number) => v.toFixed(0)}
          />
          <YAxis
            yAxisId="pct"
            orientation="right"
            domain={priceDomain}
            tick={<PercentAxisTick referencePrice={openPrice} />}
            tickLine={false}
            axisLine={false}
            width={chartLayout.axisWidth}
          />
          <Tooltip content={<TrendTooltip />} cursor={{ stroke: "#4B5563", strokeWidth: 1, strokeDasharray: "3 3" }} />
          {openPrice > 0 && (
            <ReferenceLine yAxisId="price" y={openPrice} stroke="#A1AAB5" strokeDasharray="4 3" strokeWidth={0.8} />
          )}
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke={CHART_LINE}
            strokeWidth={1.5}
            fill="url(#idx-grad)"
            dot={false}
            isAnimationActive={false}
          />
          {/* Invisible line keeps the right axis on the same price scale as the visible chart. */}
          <Area yAxisId="pct" type="monotone" dataKey="price" stroke="none" fill="none" dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MarketIndexBar({ data: externalData }: { data?: MarketIndex[] }) {
  const { data: fetchedData, isLoading } = useQuery({
    queryKey: ["market-indices"],
    queryFn: fetchMarketIndices,
    staleTime: 30_000,
    refetchInterval: 30_000,
    enabled: !externalData,
  });

  const indices = externalData ?? fetchedData;
  const [active, setActive] = useState("000001");

  if (!externalData && isLoading) {
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
          <span className="hidden shrink-0 text-[11px] text-muted-foreground/60 tabular-nums ml-3 pb-1.5 sm:inline">{idx.trend.date}</span>
        )}
      </div>

      {/* Body */}
      <motion.div
        key={active}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15, ease: easeOutQuint }}
        className="p-4 sm:p-5"
      >
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
      </motion.div>
    </div>
  );
}
