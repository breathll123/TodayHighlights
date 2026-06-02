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
        <h4 className="text-xs font-semibold text-foreground/80">AI 模型排行榜</h4>
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
        <a
          key={item.id}
          href={item.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className={`${colClass} border-b border-border/40 px-2.5 py-2 text-xs last:border-b-0 transition-colors hover:bg-primary/[0.04] ${
            i < 3 ? "bg-primary/[0.02]" : ""
          }`}
        >
          <span className={`text-center tabular-nums font-semibold ${
            item.rank && item.rank <= 3 ? "text-primary" : "text-muted-foreground"
          }`}>
            {item.rank || "—"}
          </span>
          <span className="flex items-center gap-1.5 truncate">
            <span className="truncate font-medium">{item.model || item.title}</span>
            {item.company ? (
              <span className="text-[10px] text-muted-foreground/60 shrink-0 hidden sm:inline">{item.company}</span>
            ) : null}
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
        </a>
      ))}
    </div>
  );
}
