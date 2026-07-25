// -*- coding: utf-8 -*-
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Calendar, ChevronLeft, ChevronRight, Gamepad2, Percent, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { PixelIcon } from "./PixelIcon";

const easeOutQuint: [number, number, number, number] = [0.22, 1, 0.36, 1];

export interface GameItem {
  id: string | number;
  title: string;
  subtitle?: string;
  rank?: number;
  provider: string;
  source: string;
  external_id: string;
  url: string;
  cover_url?: string;
  cover_local?: string;
  current_price?: number | null;
  original_price?: number | null;
  discount_percent?: number;
  discount_label?: string;
  release_date?: string | null;
  peak_in_game?: number | null;
  concurrent_in_game?: number | null;
  last_week_rank?: number | null;
  summary?: string;
  e_game_name?: string;
  last_purchase_rank?: number | null;
  captured_at?: string;
}

// 辅助方法：解析封面图片，优先使用本地缓存，若无则使用公网代理
function resolveCoverUrl(coverLocal?: string, coverUrl?: string): string {
  if (coverLocal) return coverLocal;
  if (!coverUrl) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(coverUrl)}`;
}

// 辅助方法：格式化价格展示
function formatPrice(price: number | null | undefined): string {
  if (price === undefined || price === null) return "未定价";
  if (price === 0) return "免费";
  return `¥${price.toFixed(2)}`;
}

function formatDiscount(item: GameItem): string {
  if (item.discount_label) return item.discount_label;
  if (item.discount_percent && item.discount_percent > 0) return `-${item.discount_percent}%`;
  return "";
}

function formatInteger(value: number | null | undefined): string {
  if (value === undefined || value === null) return "-";
  return new Intl.NumberFormat("zh-CN").format(value);
}

function formatDiscountMetric(item: GameItem): string {
  const discount = formatDiscount(item);
  if (discount) return discount;
  if (item.current_price === 0) return "免费";
  return "折扣";
}

function isWeGameDeal(item: GameItem): boolean {
  return item.provider === "wegame" || item.source === "WeGame";
}

/**
 * 1. Steam 热门游戏排行榜 / 在线人数榜组件
 */
type RealtimeSortKey = "concurrent" | "peak";

export function GameRankingList({
  data,
  mode = "top_sellers",
  onAnalysisDataChange,
}: {
  data: GameItem[];
  mode?: "top_sellers" | "wegame" | "realtime";
  onAnalysisDataChange?: (data: GameItem[], scopeLabel: string) => void;
}) {
  // 实时热玩榜：接口默认按当前在线排序；切到今日峰值时前端重排
  const [realtimeSort, setRealtimeSort] = useState<RealtimeSortKey>("concurrent");
  const sortedData = useMemo(() => {
    if (mode !== "realtime" || realtimeSort === "concurrent") return data;
    return [...data].sort((a, b) => (b.peak_in_game ?? 0) - (a.peak_in_game ?? 0));
  }, [data, mode, realtimeSort]);

  useEffect(() => {
    const scopeLabel =
      mode === "wegame" ? "WeGame榜单"
      : mode === "realtime" ? (realtimeSort === "peak" ? "实时热玩·今日峰值" : "实时热玩·当前在线")
      : "全部热门";
    onAnalysisDataChange?.(sortedData, scopeLabel);
  }, [sortedData, mode, realtimeSort, onAnalysisDataChange]);

  if (data.length === 0) {
    const emptyLabel = mode === "wegame" ? "WeGame 榜单" : "热门 Steam 游戏";
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无{emptyLabel}数据
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {mode === "realtime" ? (
        <div className="flex items-center justify-end gap-1">
          {([
            ["concurrent", "当前在线"],
            ["peak", "今日峰值"],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setRealtimeSort(key)}
              className={cn(
                "rounded-md px-2.5 py-1 text-[11px] font-medium transition-[color,background-color,transform] active:scale-[0.97]",
                realtimeSort === key ? "" : "text-muted-foreground hover:text-foreground",
              )}
              style={
                realtimeSort === key
                  ? {
                      backgroundColor: "var(--block-accent-soft, rgba(43,224,122,0.12))",
                      color: "var(--block-accent, hsl(var(--primary)))",
                    }
                  : undefined
              }
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}
      {sortedData.map((item, index) => {
        const cover = resolveCoverUrl(item.cover_local, item.cover_url);
        const isRealtime = mode === "realtime";
        // 峰值排序是前端重排，名次按排序后的位置重新编号
        const rank = isRealtime && realtimeSort === "peak" ? index + 1 : item.rank ?? index + 1;
        const isTop3 = rank <= 3;
        const isWeGame = mode === "wegame";
        
        // 金、银、铜像素硬币的主体色
        const coinColor = rank === 1 ? "#FFC53D" : rank === 2 ? "#A0AEC0" : "#CD7F32";
        
        return (
          <motion.a
            key={item.id ?? index}
            href={item.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            title={item.summary ? `${item.title}\n${item.summary}` : item.title}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: Math.min(index, 6) * 0.03, ease: easeOutQuint }}
            className="group relative flex items-center gap-3 overflow-hidden rounded-lg border border-border/40 bg-card/45 p-2 transition-all hover:-translate-y-0.5 hover:border-[color:var(--block-accent,theme(colors.border))] hover:bg-card/75 hover:shadow-md"
            style={{
              // 霓虹背光微弱外发光投影
              boxShadow: "0 0 0 1px var(--block-accent-soft, transparent)"
            }}
          >
            {/* 排名角标 - 前三名采用原创像素硬币 */}
            {isTop3 ? (
              <div className="relative flex h-7 w-7 shrink-0 items-center justify-center">
                <PixelIcon name="coin" color={coinColor} size={24} />
                <span className="absolute text-[10px] font-black text-black tabular-nums" style={{ top: "4px" }}>
                  {rank}
                </span>
              </div>
            ) : (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-bold tabular-nums bg-muted/40 text-muted-foreground">
                {rank}
              </div>
            )}

            {/* 封面缩略图 */}
            <div className="relative h-12 w-20 shrink-0 overflow-hidden rounded-md bg-muted">
              {cover ? (
                <img
                  src={cover}
                  alt={item.title}
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                  No Cover
                </div>
              )}
            </div>

            {/* 游戏名与榜单信息 */}
            <div className="min-w-0 flex-1">
              <h4 className="truncate text-sm font-semibold tracking-tight text-foreground transition-colors group-hover:text-[color:var(--block-accent,hsl(var(--primary)))]">
                {item.title}
              </h4>
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                {isRealtime ? (
                  <>
                    <TrendingUp className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
                    Steam 实时在线
                  </>
                ) : isWeGame ? (
                  <>
                    <TrendingUp className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
                    <span className="truncate">{item.e_game_name || "WeGame 榜单"}</span>
                  </>
                ) : (
                  <>
                    <Calendar className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
                    {item.release_date ? `${item.release_date} 发售` : "发布日期未知"}
                  </>
                )}
                {item.summary ? <span className="rounded bg-muted/50 px-1 text-[10px] text-muted-foreground/80">简介</span> : null}
              </p>
            </div>

            {/* 右侧指标区 */}
            <div className="flex shrink-0 flex-col items-end gap-0.5">
              {isRealtime ? (
                <>
                  <span className="arcade-score text-xs font-bold tabular-nums" style={{ color: "var(--block-accent, #2BE07A)" }}>
                    {formatInteger(realtimeSort === "peak" ? item.peak_in_game : item.concurrent_in_game)}
                  </span>
                  <span className="text-[10px] text-muted-foreground tabular-nums">
                    {realtimeSort === "peak"
                      ? `当前 ${formatInteger(item.concurrent_in_game)}`
                      : `峰值 ${formatInteger(item.peak_in_game)}`}
                  </span>
                </>
              ) : isWeGame ? (
                <>
                  <span className="rounded-md border border-border/50 bg-card/60 px-2 py-0.5 text-[11px] font-semibold text-[color:var(--block-accent,hsl(var(--primary)))]">
                    WeGame
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {item.last_purchase_rank ? `上周 #${item.last_purchase_rank}` : "平台榜单"}
                  </span>
                </>
              ) : (
                <>
                  {item.discount_percent && item.discount_percent > 0 ? (
                    <div className="flex items-center gap-1.5">
                      <span 
                        className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                        style={{
                          backgroundColor: "var(--block-accent-soft, rgba(52, 229, 160, 0.15))",
                          color: "var(--block-accent, #34E5A0)"
                        }}
                      >
                        {formatDiscount(item)}
                      </span>
                      <span className="text-[10px] text-muted-foreground line-through decoration-muted-foreground/60">
                        {formatPrice(item.original_price)}
                      </span>
                    </div>
                  ) : null}
                  <span className="text-xs font-bold text-foreground">
                    {formatPrice(item.current_price)}
                  </span>
                </>
              )}
            </div>
          </motion.a>
        );
      })}
    </div>
  );
}

/**
 * 2. Steam 促销折扣专区组件
 */
export function GameDealGrid({
  data,
  onAnalysisDataChange,
}: {
  data: GameItem[];
  onAnalysisDataChange?: (data: GameItem[], scopeLabel: string) => void;
}) {
  const orbitRef = useRef<HTMLDivElement | null>(null);
  const [orbitWidth, setOrbitWidth] = useState(640);
  const [cursor, setCursor] = useState(0);
  const [paused, setPaused] = useState(false);
  const [prefersReducedMotion] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );
  const { steamDeals, wegameDeals } = useMemo(() => {
    const steam = data.filter((item) => !isWeGameDeal(item));
    const wegame = data.filter(isWeGameDeal);
    const pick = (items: GameItem[], limit: number) => {
      if (items.length === 0) return [];
      const slots = Math.min(limit, items.length);
      // cursor 是无界整数（后退可为负），取模需归正
      return Array.from({ length: slots }, (_, index) => items[(((cursor + index) % items.length) + items.length) % items.length]);
    };
    return {
      steamDeals: pick(steam, 5),
      wegameDeals: pick(wegame, 5),
    };
  }, [cursor, data]);

  useEffect(() => {
    const node = orbitRef.current;
    if (!node) return undefined;

    const updateWidth = () => {
      setOrbitWidth(node.getBoundingClientRect().width || 640);
    };
    updateWidth();

    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      setOrbitWidth(entries[0]?.contentRect.width || 640);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    onAnalysisDataChange?.(data, "全部优惠");
  }, [data, onAnalysisDataChange]);

  useEffect(() => {
    // 悬停/聚焦时暂停自动切换，别跟正在看的人抢；用户降低动效偏好时完全交给手动按钮。
    if (data.length <= 1 || paused || prefersReducedMotion) return undefined;
    const timer = window.setTimeout(() => {
      setCursor((value) => value + 1);
    }, 10000);
    return () => window.clearTimeout(timer);
  }, [cursor, data.length, paused, prefersReducedMotion]);

  const positions = useMemo(() => {
    const verticalOffset = Math.max(88, Math.min(104, orbitWidth * 0.15));
    // 槽位按"旅程"排序（index 递减 = 向前走一站）：
    //   左四/右四（最外侧进场）→ 左三 → 左二 → 左一/右一（hero）→ 下/上（谢幕位）→ 收束进中心金币消失。
    // hero=true 的槽位（左一/右一 + 谢幕位）承载完整信息；其余为"预告"，只留封面 + 折扣角标。
    const steam = [
      { label: "Steam 下", x: 0, y: verticalOffset, scale: 0.8, zIndex: 4, opacity: 0.92, hero: true, flip: false, wide: true },
      { label: "Steam 左一", x: orbitWidth * -0.18, y: 0, scale: 0.92, zIndex: 5, opacity: 1, hero: true, flip: false },
      { label: "Steam 左二", x: orbitWidth * -0.28, y: 0, scale: 0.8, zIndex: 3, opacity: 0.76, hero: false, flip: false },
      { label: "Steam 左三", x: orbitWidth * -0.38, y: 0, scale: 0.72, zIndex: 2, opacity: 0.62, hero: false, flip: false },
      { label: "Steam 左四", x: orbitWidth * -0.48, y: 0, scale: 0.66, zIndex: 1, opacity: 0.48, hero: false, flip: false },
    ];
    const wegame = [
      // flip：信息条翻到卡片顶部（朝外缘），避免被中间的 hero 卡遮住
      { label: "上", x: 0, y: -verticalOffset, scale: 0.8, zIndex: 4, opacity: 0.92, hero: true, flip: true, wide: true },
      { label: "右一", x: orbitWidth * 0.18, y: 0, scale: 0.92, zIndex: 5, opacity: 1, hero: true, flip: false },
      { label: "右二", x: orbitWidth * 0.28, y: 0, scale: 0.8, zIndex: 3, opacity: 0.76, hero: false, flip: false },
      { label: "右三", x: orbitWidth * 0.38, y: 0, scale: 0.72, zIndex: 2, opacity: 0.62, hero: false, flip: false },
      { label: "右四", x: orbitWidth * 0.48, y: 0, scale: 0.66, zIndex: 1, opacity: 0.48, hero: false, flip: false },
    ];
    return { steam, wegame };
  }, [orbitWidth]);

  // seq（= 进场时的游标序号）作为 key：卡片实例在各槽位间迁移时 key 恒定，
  // 走完谢幕位掉出窗口时 key 消失 → AnimatePresence 触发"归一到中心"退场。
  const positionedDeals = useMemo(() => [
    ...steamDeals.map((item, index) => ({ item, position: positions.steam[index] ?? positions.steam[0], lane: "steam", seq: cursor + index })),
    ...wegameDeals.map((item, index) => ({ item, position: positions.wegame[index] ?? positions.wegame[0], lane: "wegame", seq: cursor + index })),
  ], [cursor, positions, steamDeals, wegameDeals]);

  const rotateDeals = () => {
    setCursor((value) => value + 1);
  };

  const rotateDealsBack = () => {
    setCursor((value) => value - 1);
  };

  const { mobileDeal, mobilePreviewDeals } = useMemo(() => {
    if (data.length === 0) return { mobileDeal: undefined, mobilePreviewDeals: [] as GameItem[] };
    const normalized = ((cursor % data.length) + data.length) % data.length;
    return {
      mobileDeal: data[normalized],
      mobilePreviewDeals: Array.from({ length: Math.min(4, data.length) }, (_, index) => (
        data[(normalized + index) % data.length]
      )),
    };
  }, [cursor, data]);
  const mobileDealCover = resolveCoverUrl(mobileDeal?.cover_local, mobileDeal?.cover_url);

  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无优惠促销游戏数据
      </div>
    );
  }

  return (
    <>
      {mobileDeal ? (
        <div
          data-testid="deal-mobile-carousel"
          className="relative overflow-hidden rounded-xl border border-border/55 bg-card/45 p-2.5 shadow-[0_0_0_1px_var(--block-accent-soft,transparent)] md:hidden"
        >
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,var(--block-accent-soft,rgba(255,197,61,0.12)),transparent_44%),radial-gradient(circle_at_82%_12%,rgba(255,197,61,0.18),transparent_28%)]" />
          <div className="relative flex items-center justify-between gap-2 pb-2">
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[color:var(--block-accent,#FFC53D)]">
                Deal Deck
              </p>
              <h3 className="truncate text-sm font-semibold text-foreground">打折促销</h3>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                onClick={rotateDealsBack}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 bg-background/80 text-muted-foreground shadow-sm backdrop-blur transition active:scale-95"
                aria-label="后退切换折扣游戏"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={rotateDeals}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--block-accent,hsl(var(--primary)))] bg-background/90 text-[color:var(--block-accent,hsl(var(--primary)))] shadow-sm backdrop-blur transition active:scale-95"
                aria-label="前进切换折扣游戏"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <motion.a
            key={`mobile-${cursor}-${mobileDeal.id}`}
            href={mobileDeal.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            title={mobileDeal.summary ? `${mobileDeal.title}\n${mobileDeal.summary}` : mobileDeal.title}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.28, ease: easeOutQuint }}
            onTouchStart={() => setPaused(true)}
            onTouchEnd={() => setPaused(false)}
            onFocus={() => setPaused(true)}
            onBlur={() => setPaused(false)}
            className="relative block overflow-hidden rounded-lg border border-border/50 bg-background/80 shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--block-accent,hsl(var(--ring)))]"
          >
            <div className="relative aspect-[16/9] w-full overflow-hidden bg-muted">
              {mobileDealCover ? (
                <img
                  src={mobileDealCover}
                  alt={mobileDeal.title}
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                  No Image
                </div>
              )}
              <span className="absolute left-2 top-2 rounded bg-background/85 px-2 py-1 text-[10px] font-bold text-foreground shadow-sm backdrop-blur">
                {isWeGameDeal(mobileDeal) ? "WeGame" : "Steam"}
              </span>
              {formatDiscountMetric(mobileDeal) ? (
                <span className="absolute right-2 top-2 rounded-md bg-[color:var(--block-accent,#FF4D8D)] px-2 py-1 text-xs font-black text-white shadow-sm">
                  {formatDiscountMetric(mobileDeal)}
                </span>
              ) : null}
            </div>
            <div className="p-3">
              <h4 className="line-clamp-2 text-base font-bold leading-snug text-foreground">
                {mobileDeal.title}
              </h4>
              <div className="mt-2 flex items-end justify-between gap-2">
                <div className="min-w-0">
                  {formatDiscount(mobileDeal) ? (
                    <div className="flex items-center gap-1.5">
                      <span className="rounded bg-[color:var(--block-accent-soft,rgba(255,77,141,0.14))] px-1.5 py-0.5 text-xs font-bold text-[color:var(--block-accent,#FF4D8D)]">
                        {formatDiscount(mobileDeal)}
                      </span>
                      <span className="truncate text-xs text-muted-foreground line-through">
                        {formatPrice(mobileDeal.original_price)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">限时优惠</span>
                  )}
                </div>
                <span className="shrink-0 text-lg font-black text-emerald-400">
                  {formatPrice(mobileDeal.current_price)}
                </span>
              </div>
            </div>
          </motion.a>

          <div className="relative mt-2.5 grid grid-cols-4 gap-1.5">
            {mobilePreviewDeals.map((item, index) => {
              const cover = resolveCoverUrl(item.cover_local, item.cover_url);
              return (
                <button
                  key={`${item.id}-${index}`}
                  type="button"
                  onClick={() => setCursor((value) => value + index)}
                  className={cn(
                    "relative aspect-[16/10] overflow-hidden rounded-md border bg-muted text-left transition active:scale-95",
                    index === 0 ? "border-[color:var(--block-accent,hsl(var(--primary)))]" : "border-border/50 opacity-70",
                  )}
                  aria-label={`切换到折扣游戏：${item.title}`}
                >
                  {cover ? <img src={cover} alt="" loading="lazy" className="h-full w-full object-cover" /> : null}
                  <span className="absolute bottom-1 right-1 rounded bg-background/85 px-1 text-[9px] font-bold text-foreground">
                    {formatDiscountMetric(item)}
                  </span>
                </button>
              );
            })}
          </div>

          <div
            key={`mobile-progress-${cursor}`}
            className="relative mx-auto mt-2.5 h-1 w-28 overflow-hidden rounded-none border border-amber-300/35 bg-amber-950/45"
            data-testid="deal-mobile-progress-line"
            aria-label="10秒后自动切换"
          >
            <div className="deal-orbit-progress-line h-full origin-left" aria-hidden="true" />
          </div>
        </div>
      ) : null}

    <div
      data-testid="deal-orbit"
      className="relative hidden overflow-hidden rounded-xl border border-border/50 bg-card/35 px-3 py-3 pb-4 md:block"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,var(--block-accent-soft,rgba(52,229,160,0.14)),transparent_48%)] opacity-70" />
      <button
        type="button"
        onClick={rotateDealsBack}
        className="absolute left-2 top-1/2 z-30 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-border/60 bg-background/80 text-muted-foreground shadow-lg backdrop-blur transition hover:border-[color:var(--block-accent,hsl(var(--primary)))] hover:text-[color:var(--block-accent,hsl(var(--primary)))] focus:outline-none focus:ring-2 focus:ring-[color:var(--block-accent,hsl(var(--ring)))]"
        aria-label="后退切换折扣游戏"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={rotateDeals}
        className="absolute right-2 top-1/2 z-30 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-[color:var(--block-accent,hsl(var(--primary)))] bg-background/90 text-[color:var(--block-accent,hsl(var(--primary)))] shadow-lg backdrop-blur transition hover:bg-card focus:outline-none focus:ring-2 focus:ring-[color:var(--block-accent,hsl(var(--ring)))]"
        aria-label="前进切换折扣游戏"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
      <div ref={orbitRef} className="relative h-[350px] w-full sm:h-[382px]">
        <div className="pointer-events-none absolute left-4 right-4 top-1/2 h-px -translate-y-1/2 bg-gradient-to-r from-transparent via-[color:var(--block-accent,hsl(var(--primary)))] to-transparent opacity-35" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[124px] w-[124px] -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-xl border border-border/45 bg-background/10 shadow-[0_0_30px_var(--block-accent-soft,rgba(52,229,160,0.16))] sm:h-[148px] sm:w-[148px]" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-2xl border border-amber-300/35 bg-[linear-gradient(135deg,rgba(255,214,102,0.22),rgba(39,210,255,0.16),rgba(255,77,141,0.18))] shadow-[0_0_28px_rgba(255,197,61,0.24)] backdrop-blur sm:h-[72px] sm:w-[72px]">
          <Gamepad2 className="h-8 w-8 text-amber-200 drop-shadow-[0_0_10px_rgba(255,197,61,0.75)] sm:h-9 sm:w-9" />
        </div>

        <AnimatePresence>
        {positionedDeals.map(({ item, position, lane, seq }) => {
          const cover = resolveCoverUrl(item.cover_local, item.cover_url);
          const platform = isWeGameDeal(item) ? "WeGame" : "Steam";

          return (
            <motion.a
              key={`${lane}-${seq}`}
              href={item.url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              title={item.summary ? `${item.title}\n${item.summary}` : item.title}
              initial={{ opacity: 0, x: position.x, y: position.y, scale: 0.9 }}
              animate={{ opacity: position.opacity, x: position.x, y: position.y, scale: position.scale }}
              exit={{ opacity: 0, x: 0, y: 0, scale: 0.08 }}
              transition={{ duration: 0.68, ease: [0.16, 1, 0.3, 1] }}
              transformTemplate={({ x, y, scale }) => `translate(-50%, -50%) translate3d(${x}, ${y}, 0) scale(${scale})`}
              onMouseEnter={() => setPaused(true)}
              onMouseLeave={() => setPaused(false)}
              onFocus={() => setPaused(true)}
              onBlur={() => setPaused(false)}
              className={cn(
                "group absolute left-1/2 top-1/2 flex flex-col overflow-hidden rounded-lg border border-border/40 bg-card/85 shadow-lg backdrop-blur will-change-transform hover:border-[color:var(--block-accent,theme(colors.border))] hover:bg-card hover:shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--block-accent,hsl(var(--ring)))]",
                position.wide ? "w-[206px] sm:w-[244px]" : "w-[190px] sm:w-[228px]",
                position.flip && "flex-col-reverse",
              )}
              style={{ zIndex: position.zIndex, boxShadow: "0 0 0 1px var(--block-accent-soft, transparent)" }}
              aria-label={`${position.label}侧折扣：${item.title}`}
            >
              <div className="relative aspect-[16/9] w-full overflow-hidden bg-muted">
                {cover ? (
                  <img
                    src={cover}
                    alt={item.title}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                    No Image
                  </div>
                )}
                {formatDiscountMetric(item) ? (
                  <div
                    className="absolute right-1 top-1 flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-white shadow-sm"
                    style={{ backgroundColor: "var(--block-accent, #FF4D8D)" }}
                  >
                    <Percent className="h-2.5 w-2.5" />
                    <span className="text-[10px] font-extrabold">
                      {formatDiscountMetric(item)}
                    </span>
                  </div>
                ) : null}
                <span className="absolute left-1 top-1 rounded bg-background/85 px-1.5 py-0.5 text-[9px] font-bold text-foreground shadow-sm backdrop-blur">
                  {platform}
                </span>
              </div>

              {/* 只有 hero（左一/右一）承载完整标题+价格；预告卡片只留封面 + 折扣角标，
                  读作有意的"预览"而非被截断的卡片。 */}
              {position.hero ? (
                <div className="flex flex-1 flex-col justify-between p-2.5">
                  <h4 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground group-hover:text-[color:var(--block-accent,hsl(var(--primary)))]">
                    {item.title}
                  </h4>

                  <div className="mt-1.5 flex items-baseline justify-between gap-2">
                    {formatDiscount(item) ? (
                      <div className="flex min-w-0 items-center gap-1.5">
                        <span
                          className="rounded px-1.5 py-0.5 text-[11px] font-bold"
                          style={{
                            backgroundColor: "var(--block-accent-soft, rgba(255, 77, 141, 0.15))",
                            color: "var(--block-accent, #FF4D8D)"
                          }}
                        >
                          {formatDiscount(item)}
                        </span>
                        <span className="text-[11px] text-muted-foreground line-through">
                          {formatPrice(item.original_price)}
                        </span>
                      </div>
                    ) : (
                      <div />
                    )}
                    <span className="text-sm font-bold text-emerald-400">
                      {formatPrice(item.current_price)}
                    </span>
                  </div>
                </div>
              ) : null}
            </motion.a>
          );
        })}
        </AnimatePresence>
      </div>

      <div
        key={cursor}
        className="absolute bottom-2 left-1/2 z-20 h-1.5 w-1/2 -translate-x-1/2 overflow-hidden rounded-none border border-amber-300/35 bg-amber-950/45 shadow-[0_0_12px_rgba(255,197,61,0.16)]"
        data-testid="deal-orbit-progress-line"
        aria-label="10秒后自动切换"
      >
        <div className="deal-orbit-progress-line h-full origin-left" aria-hidden="true" />
      </div>
    </div>
    </>
  );
}

/**
 * 2b. 传统 Steam 促销折扣横向货架，保留给后续回退或对比使用
 */
export function GameDealShelf({
  data,
}: {
  data: GameItem[];
}) {
  return (
    <div data-testid="deal-shelf" className="deal-shelf flex snap-x gap-2 overflow-x-auto pb-2">
      {data.map((item, index) => {
        const cover = resolveCoverUrl(item.cover_local, item.cover_url);
        const discount = formatDiscount(item);

        return (
          <motion.a
            key={item.id ?? index}
            href={item.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            title={item.summary ? `${item.title}\n${item.summary}` : item.title}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.22, delay: Math.min(index, 6) * 0.03, ease: easeOutQuint }}
            className="group flex w-[188px] shrink-0 snap-start flex-col overflow-hidden rounded-lg border border-border/40 bg-card/45 transition-all hover:-translate-y-0.5 hover:border-[color:var(--block-accent,theme(colors.border))] hover:bg-card/75 hover:shadow-md"
            style={{
              boxShadow: "0 0 0 1px var(--block-accent-soft, transparent)"
            }}
          >
            <div className="relative aspect-[16/9] w-full overflow-hidden bg-muted">
              {cover ? (
                <img
                  src={cover}
                  alt={item.title}
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                  No Image
                </div>
              )}
              {discount ? (
                <div
                  className="absolute right-1 top-1 flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-white shadow-sm"
                  style={{
                    backgroundColor: "var(--block-accent, #FF4D8D)"
                  }}
                >
                  <Percent className="h-2.5 w-2.5" />
                  <span className="text-[10px] font-extrabold">
                    {item.discount_percent}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="flex flex-1 flex-col justify-between p-2">
              <h4 className="line-clamp-2 text-xs font-semibold text-foreground group-hover:text-[color:var(--block-accent,hsl(var(--primary)))]">
                {item.title}
              </h4>
              
              <div className="mt-1.5 flex items-baseline justify-between gap-1">
                {discount ? (
                  <div className="flex min-w-0 items-center gap-1">
                    <span 
                      className="rounded px-1 py-0.5 text-[9px] font-bold"
                      style={{
                        backgroundColor: "var(--block-accent-soft, rgba(255, 77, 141, 0.15))",
                        color: "var(--block-accent, #FF4D8D)"
                      }}
                    >
                      {discount}
                    </span>
                    <span className="text-[9px] text-muted-foreground line-through">
                      {formatPrice(item.original_price)}
                    </span>
                  </div>
                ) : (
                  <div />
                )}
                <span className="text-xs font-bold text-emerald-400">
                  {formatPrice(item.current_price)}
                </span>
              </div>
            </div>
          </motion.a>
        );
      })}
    </div>
  );
}

/**
 * 3. Steam 新发售动态组件
 */
export function GameReleaseList({
  data,
  onAnalysisDataChange,
}: {
  data: GameItem[];
  onAnalysisDataChange?: (data: GameItem[], scopeLabel: string) => void;
}) {
  useEffect(() => {
    onAnalysisDataChange?.(data, "最新发布");
  }, [data, onAnalysisDataChange]);

  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无最新发售 Steam 游戏数据
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {data.map((item, index) => {
        const cover = resolveCoverUrl(item.cover_local, item.cover_url);
        
        return (
          <motion.a
            key={item.id ?? index}
            href={item.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            title={item.summary ? `${item.title}\n${item.summary}` : item.title}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: Math.min(index, 6) * 0.03, ease: easeOutQuint }}
            className="group flex items-center gap-3 overflow-hidden rounded-lg border border-border/40 bg-card/45 p-2 transition-all hover:border-[color:var(--block-accent,theme(colors.border))] hover:bg-card/75 hover:shadow-md"
            style={{
              boxShadow: "0 0 0 1px var(--block-accent-soft, transparent)"
            }}
          >
            {/* 封面缩略图 */}
            <div className="relative h-12 w-20 shrink-0 overflow-hidden rounded-md bg-muted">
              {cover ? (
                <img
                  src={cover}
                  alt={item.title}
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-103"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                  No Cover
                </div>
              )}
            </div>

            {/* 名称与状态 */}
            <div className="min-w-0 flex-1">
              <h4 className="truncate text-sm font-semibold tracking-tight text-foreground transition-colors group-hover:text-[color:var(--block-accent,hsl(var(--primary)))]">
                {item.title}
              </h4>
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                <Calendar className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
                {item.release_date ? `${item.release_date} 发售` : "暂未确定发布日期"}
                {item.summary ? <span className="rounded bg-muted/50 px-1 text-[10px] text-muted-foreground/80">简介</span> : null}
              </p>
            </div>

            {/* 发售价格状态 */}
            <div className="shrink-0 text-right">
              {item.current_price !== undefined && item.current_price !== null ? (
                <span className="text-xs font-bold text-foreground">
                  {formatPrice(item.current_price)}
                </span>
              ) : (
                <span 
                  className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  style={{
                    backgroundColor: "var(--block-accent-soft, rgba(77, 208, 255, 0.15))",
                    color: "var(--block-accent, #4DD0FF)"
                  }}
                >
                  预约中
                </span>
              )}
            </div>
          </motion.a>
        );
      })}
    </div>
  );
}
