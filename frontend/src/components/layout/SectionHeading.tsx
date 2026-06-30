import type { LucideIcon } from "lucide-react";
import { ExternalLink } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { PixelIcon } from "./PixelIcon";
import type { BoardSkin } from "@/lib/block-themes";

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function parseUpdatedAt(value: string | number | null | undefined): Date | null {
  if (value == null) return null;
  const date = typeof value === "number" ? new Date(value) : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatClockTime(date: Date): string {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function formatFullTime(date: Date): string {
  return [
    `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`,
    `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`,
  ].join(" ");
}

function UpdatedAtBadge({ date }: { date: Date }) {
  const tooltipId = useId();
  const fullTime = formatFullTime(date);

  return (
    <span className="section-updated-trigger" onClick={(event) => event.stopPropagation()}>
      <span
        className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground/60 tabular-nums outline-none transition-colors hover:text-muted-foreground focus-visible:text-muted-foreground"
        aria-describedby={tooltipId}
        tabIndex={0}
      >
        {/* A single green "active" light — a steady status indicator, not a
            claim of real-time refresh (many sources update on their own cadence). */}
        <span className="signal-blip h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" aria-hidden="true" />
        更新 {formatClockTime(date)}
      </span>
      <span id={tooltipId} role="tooltip" className="section-updated-tooltip">
        <span className="section-updated-tooltip-label">数据更新时间</span>
        <span>{fullTime}</span>
      </span>
    </span>
  );
}

export function SectionHeading({
  icon: Icon,
  title,
  meta,
  action,
  dataUpdatedAt,
  sourceName,
  sourceUrl,
  className,
  skin,
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
  dataUpdatedAt?: string | number | null;
  sourceName?: string;
  sourceUrl?: string;
  className?: string;
  skin?: BoardSkin;
}) {
  const updatedAt = parseUpdatedAt(dataUpdatedAt);

  return (
    <div className={cn("space-y-1.5", className)}>
      {skin ? <div className="arcade-eyebrow mb-1" style={{ color: skin.accent }}>{skin.eyebrow}</div> : null}
      <div className="flex min-w-0 items-center justify-between gap-3">
        <h2 className="flex min-w-0 items-center gap-2.5 text-sm font-semibold text-foreground">
          {skin ? (
            <span
              className="arcade-scanline flex h-7 w-7 shrink-0 items-center justify-center rounded-md border"
              style={{ borderColor: skin.accent, background: skin.accentSoft, boxShadow: `0 0 10px ${skin.accentSoft}` }}
            >
              <PixelIcon name={skin.icon} color={skin.accent} size={16} />
            </span>
          ) : (
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary transition-colors duration-200 group-hover:border-primary/50 group-hover:bg-primary/15">
              <Icon data-testid="section-heading-icon" className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          )}
          <span className="truncate">{title}</span>
        </h2>
        <div className="flex shrink-0 items-center gap-2">
          {meta ? <span className="text-[11px] text-muted-foreground tabular-nums">{meta}</span> : null}
          {updatedAt ? (
            <UpdatedAtBadge date={updatedAt} />
          ) : null}
          {action}
        </div>
      </div>

      <div
        className={cn("header-rule h-px w-full", !skin && "bg-gradient-to-r from-primary/45 via-primary/10 to-transparent")}
        style={skin ? { background: `linear-gradient(to right, ${skin.accent}, transparent)` } : undefined}
      />

      {sourceName && (
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground/70">
          <span>来源</span>
          <span className="text-muted-foreground/35" aria-hidden="true">·</span>
          {sourceUrl ? (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-primary/80 transition-colors hover:text-primary no-underline">
              {sourceName}
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          ) : (
            <span className="text-muted-foreground">{sourceName}</span>
          )}
        </div>
      )}
    </div>
  );
}
