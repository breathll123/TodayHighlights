import { motion } from "framer-motion";
import { BrainCircuit, ExternalLink } from "lucide-react";
import { RankBadge, rankRowTone } from "./RankBadge";

interface LeaderboardItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  rank?: number;
  model?: string;
  company?: string;
  license?: string;
  HLE?: string;
  "ARC-AGI-2"?: string;
  FrontierMath?: string;
  "SWE-bench"?: string;
  "τ²-Bench"?: string;
  benchmarks?: string[];
}

interface Props {
  data: LeaderboardItem[];
}

const BENCHMARK_LABELS: Record<string, string> = {
  HLE: "HLE",
  "ARC-AGI-2": "ARC-AGI-2",
  FrontierMath: "FrontierMath",
  "SWE-bench": "SWE-bench",
  "τ²-Bench": "τ²-Bench",
};

function fmtScore(v: string | undefined): string {
  if (!v) return "—";
  return v;
}

export function LeaderboardTable({ data }: Props) {
  const benchmarks = data[0]?.benchmarks || Object.keys(BENCHMARK_LABELS);
  const activeBenchmarks = benchmarks.filter((b) => data.some((d) => (d as any)[b]));

  // Compute grid columns: rank + model + each benchmark
  const colClass = `grid grid-cols-[3rem_minmax(0,1.5fr)_repeat(${activeBenchmarks.length},1fr)_4rem] gap-1`;

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/30 px-3 py-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold text-foreground/85">
          <BrainCircuit className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          AI 模型排行榜
        </h4>
        <span className="shrink-0 text-[10px] text-muted-foreground/60">
          DataLearner · {data.length} 模型
        </span>
      </div>

      {/* Column headers */}
      <div className={`${colClass} border-b border-border/40 bg-muted/20 px-2.5 py-1.5 text-[10px] font-medium text-muted-foreground`}>
        <span className="text-center">#</span>
        <span>模型</span>
        {activeBenchmarks.map((b) => (
          <span key={b} className="text-center">{BENCHMARK_LABELS[b] || b}</span>
        ))}
        <span className="text-center">许可</span>
      </div>

      {/* Rows */}
      {data.map((item, i) => (
        <motion.a
          key={item.id}
          href={item.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          data-rank-row={item.rank}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: Math.min(i, 6) * 0.03, ease: "easeOut" }}
          className={`${colClass} ${rankRowTone(item.rank)} group min-h-10 items-center border-b border-border/40 px-2.5 py-2 text-xs transition-[background-color,border-color,transform] last:border-b-0 hover:bg-primary/[0.06] active:scale-[0.99]`}
        >
          <RankBadge rank={item.rank} className="justify-center" />
          <span className="flex items-center gap-1.5 truncate">
            <span className="truncate font-medium">{item.model || item.title}</span>
            {item.company ? (
              <span className="text-[10px] text-muted-foreground/60 shrink-0 hidden sm:inline">{item.company}</span>
            ) : null}
            <ExternalLink className="ml-auto hidden h-3 w-3 shrink-0 text-muted-foreground/45 opacity-0 transition-opacity group-hover:opacity-100 sm:block" aria-hidden="true" />
          </span>
          {activeBenchmarks.map((b) => {
            const val = (item as any)[b] || "";
            const isTop = val && item.rank && item.rank <= 3;
            return (
              <span
                key={b}
                className={`text-center tabular-nums ${
                  isTop ? "font-semibold text-foreground" : "text-muted-foreground"
                }`}
              >
                {fmtScore(val)}
              </span>
            );
          })}
          <span className="text-center text-[10px] text-muted-foreground/70">
            {item.license === "免费商用" ? (
              <span className="text-green-500">开源</span>
            ) : item.license === "开源" ? (
              <span className="text-green-500">开源</span>
            ) : (
              item.license || "—"
            )}
          </span>
        </motion.a>
      ))}
    </div>
  );
}
