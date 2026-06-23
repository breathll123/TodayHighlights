import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

/** A single shimmering placeholder block. */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={cn("skeleton-shimmer rounded-md bg-muted/60", className)} style={style} />;
}

/**
 * Loading rows for a data table — the in-content placeholder that replaces a
 * bare "加载中" string. Mirrors the real column count so the layout doesn't
 * jump when data lands.
 */
export function TableSkeleton({ columns, rows = 6 }: { columns: number; rows?: number }) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} className="border-t border-border/40">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <td key={colIndex} className="px-4 py-3">
              <Skeleton
                className="h-3.5"
                style={{ width: colIndex === 0 ? "70%" : "45%", animationDelay: `${rowIndex * 60}ms` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}
