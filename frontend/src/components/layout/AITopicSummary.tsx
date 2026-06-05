import { BrainCircuit, AlertTriangle, Lightbulb } from "lucide-react";
import type { AITopicSummaryResponse } from "@/api/types";

interface Props {
  summary: AITopicSummaryResponse;
}

function formatTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function AITopicSummary({ summary }: Props) {
  if (!summary || !summary.items || summary.items.length === 0) return null;

  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 shadow-sm mb-6">
      <div className="px-5 py-3.5 border-b border-primary/15 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <BrainCircuit className="h-5 w-5 text-primary shrink-0" />
          <h3 className="text-sm font-semibold text-foreground truncate">{summary.title || "AI 今日看点"}</h3>
          {summary.version > 1 && (
            <span className="text-[10px] text-muted-foreground/60 shrink-0">v{summary.version}</span>
          )}
        </div>
        {summary.generated_at && (
          <span className="text-[10px] text-muted-foreground/50 shrink-0">{formatTime(summary.generated_at)}</span>
        )}
      </div>

      <div className="px-5 py-3.5 space-y-3">
        {summary.items.map((item, i) => (
          <div key={i} className="flex items-start gap-3 group">
            <span className="shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground leading-snug">{item.title}</p>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{item.reason}</p>

              <div className="flex flex-wrap items-center gap-2 mt-1.5">
                {item.related.length > 0 && item.related.map((r) => (
                  <span key={r} className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                    <Lightbulb className="h-2.5 w-2.5" />
                    {r}
                  </span>
                ))}
                {item.risk && (
                  <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                    <AlertTriangle className="h-2.5 w-2.5" />
                    {item.risk}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="px-5 py-2 border-t border-primary/10 text-[10px] text-muted-foreground/50 text-right">
        AI 摘要，仅供信息参考
      </div>
    </div>
  );
}
