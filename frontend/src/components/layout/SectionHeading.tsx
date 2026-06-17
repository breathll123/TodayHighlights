import type { LucideIcon } from "lucide-react";
import { Clock, ExternalLink } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

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
        className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/60 tabular-nums outline-none transition-colors hover:text-muted-foreground focus-visible:text-muted-foreground"
        aria-describedby={tooltipId}
        tabIndex={0}
      >
        <Clock className="h-3 w-3" aria-hidden="true" />
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
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
  dataUpdatedAt?: string | number | null;
  sourceName?: string;
  sourceUrl?: string;
  className?: string;
}) {
  const updatedAt = parseUpdatedAt(dataUpdatedAt);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex min-w-0 items-center justify-between gap-3">
        <h2 className="flex min-w-0 items-center gap-2.5 text-sm font-semibold text-foreground/90">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <Icon data-testid="section-heading-icon" className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
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
      {sourceName && (
        <div className="flex items-center gap-1 text-[10px] text-blue-400">
          数据来源：
          {sourceUrl ? (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-blue-400 hover:text-blue-300 no-underline">
              {sourceName}
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          ) : (
            <span>{sourceName}</span>
          )}
        </div>
      )}
    </div>
  );
}
