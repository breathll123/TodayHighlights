import type { LucideIcon } from "lucide-react";
import { Clock, ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

function timeAgo(ts: number): string {
  const seconds = Math.floor((Date.now() - ts) / 1000);
  if (seconds < 5) return "刚刚";
  if (seconds < 60) return `${seconds}秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分前`;
  const hours = Math.floor(minutes / 60);
  return `${hours}时前`;
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
  dataUpdatedAt?: number;
  sourceName?: string;
  sourceUrl?: string;
  className?: string;
}) {
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
          {dataUpdatedAt ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/60 tabular-nums">
              <Clock className="h-3 w-3" />
              {timeAgo(dataUpdatedAt)}
            </span>
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
