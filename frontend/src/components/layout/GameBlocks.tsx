// -*- coding: utf-8 -*-
import { useEffect, useId } from "react";
import { motion } from "framer-motion";
import { Star, TrendingUp, Percent, Calendar, Info } from "lucide-react";
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

function MostPlayedMetricHint() {
  const tooltipId = useId();
  return (
    <div className="flex items-center justify-end">
      <div className="group relative inline-flex items-center gap-1.5 rounded-md border border-border/40 bg-card/45 px-2 py-1 text-[11px] text-muted-foreground">
        <TrendingUp className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
        <span className="font-medium text-foreground/85">峰值在线人数</span>
        <button
          type="button"
          aria-label="峰值在线人数说明"
          aria-describedby={tooltipId}
          className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus:ring-1 focus:ring-[color:var(--block-accent,hsl(var(--ring)))]"
          onClick={(event) => event.preventDefault()}
        >
          <Info className="h-3 w-3" />
        </button>
        <span
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute right-0 top-[calc(100%+6px)] z-20 w-56 rounded-md border border-border/70 bg-popover px-2.5 py-2 text-left text-[11px] leading-relaxed text-popover-foreground opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
        >
          此游戏过去 24 小时中同时在线玩家峰值
        </span>
      </div>
    </div>
  );
}

/**
 * 1. Steam 热门游戏排行榜 / 在线人数榜组件
 */
export function GameRankingList({
  data,
  mode = "top_sellers",
  onAnalysisDataChange,
}: {
  data: GameItem[];
  mode?: "top_sellers" | "most_played" | "wegame";
  onAnalysisDataChange?: (data: GameItem[], scopeLabel: string) => void;
}) {
  useEffect(() => {
    const scopeLabel = mode === "most_played" ? "在线热玩" : mode === "wegame" ? "WeGame榜单" : "全部热门";
    onAnalysisDataChange?.(data, scopeLabel);
  }, [data, mode, onAnalysisDataChange]);

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
      {mode === "most_played" ? <MostPlayedMetricHint /> : null}
      {data.map((item, index) => {
        const cover = resolveCoverUrl(item.cover_local, item.cover_url);
        const rank = item.rank ?? index + 1;
        const isTop3 = rank <= 3;
        const isMostPlayed = mode === "most_played";
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
                {isMostPlayed ? (
                  <>
                    <TrendingUp className="h-3 w-3" style={{ color: "var(--block-accent, currentColor)" }} />
                    {item.last_week_rank ? `上周 #${item.last_week_rank}` : "Steam 在线热玩"}
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
              {isMostPlayed ? (
                <>
                  <span className="arcade-score text-xs font-bold tabular-nums text-foreground" style={{ color: "var(--block-accent, #2BE07A)" }}>
                    {formatInteger(item.peak_in_game)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">峰值在线</span>
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
  useEffect(() => {
    onAnalysisDataChange?.(data, "全部优惠");
  }, [data, onAnalysisDataChange]);

  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无优惠促销 Steam 游戏数据
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
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
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.22, delay: Math.min(index, 6) * 0.03, ease: easeOutQuint }}
            className="group flex flex-col overflow-hidden rounded-lg border border-border/40 bg-card/45 transition-all hover:-translate-y-0.5 hover:border-[color:var(--block-accent,theme(colors.border))] hover:bg-card/75 hover:shadow-md"
            style={{
              boxShadow: "0 0 0 1px var(--block-accent-soft, transparent)"
            }}
          >
            {/* 上部：大图封面与折角标签 */}
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
              
              {/* 大比例折扣标签 - 街机色调适配 */}
              {discount ? (
                <div 
                  className="absolute right-1 top-1 flex items-center gap-0.5 rounded-md px-1.5 py-0.5 shadow-sm text-white"
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

            {/* 下部：文字标题与价格 */}
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
                {/* 现价固定保留高对比价格绿 */}
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
