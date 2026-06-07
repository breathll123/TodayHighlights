import type { LucideIcon } from "lucide-react";
import { Clock } from "lucide-react";
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
  className,
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
  dataUpdatedAt?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center justify-between gap-3", className)}>
      <h2 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-foreground/85">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
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
  );
}
