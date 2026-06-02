import { Medal } from "lucide-react";
import { cn } from "@/lib/utils";

const TOP_RANKS = {
  1: { icon: "text-amber-400", number: "text-amber-300" },
  2: { icon: "text-slate-300", number: "text-slate-200" },
  3: { icon: "text-orange-400", number: "text-orange-300" },
} as const;

export function rankRowTone(rank?: number): string {
  if (rank === 1) return "rank-row-gold";
  if (rank === 2) return "rank-row-silver";
  if (rank === 3) return "rank-row-bronze";
  return "";
}

export function RankBadge({ rank, className }: { rank?: number; className?: string }) {
  const palette = rank && rank <= 3 ? TOP_RANKS[rank as keyof typeof TOP_RANKS] : undefined;

  if (!rank) {
    return <span className={cn("text-muted-foreground", className)}>—</span>;
  }

  return (
    <span
      aria-label={`第 ${rank} 名`}
      className={cn("inline-flex items-center justify-center gap-1 tabular-nums", className)}
    >
      {palette ? (
        <Medal
          data-testid={`rank-medal-${rank}`}
          className={cn("h-3.5 w-3.5", palette.icon)}
          aria-hidden="true"
        />
      ) : null}
      <span className={cn("font-semibold", palette?.number ?? "text-muted-foreground")}>{rank}</span>
    </span>
  );
}
