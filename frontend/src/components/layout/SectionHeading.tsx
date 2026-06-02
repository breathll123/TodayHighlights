import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function SectionHeading({
  icon: Icon,
  title,
  meta,
  className,
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
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
      {meta ? <span className="shrink-0 text-[11px] text-muted-foreground">{meta}</span> : null}
    </div>
  );
}
