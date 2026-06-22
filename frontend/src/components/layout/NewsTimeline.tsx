import { motion, AnimatePresence } from "framer-motion";
import { Radio, Sparkles } from "lucide-react";
import type { AIItemEnhancement } from "@/api/types";
import { shouldShowAI } from "@/api/types";

interface NewsItem {
  id: string | number;
  title: string;
  url?: string;
  published_at?: string;
  summary?: string;
  source?: string;
  ai_enrichment?: AIItemEnhancement;
}

function fmtTime(ts: string | null | undefined) {
  if (!ts) return "";
  const d = new Date(ts);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

export function NewsTimeline({ data }: { data: NewsItem[] }) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无快讯
      </div>
    );
  }

  return (
    <div className="relative rounded-xl border border-border/70 bg-card/75 p-3 shadow-sm">
      <div className="mb-2 flex items-center gap-2 px-1 text-[11px] font-medium uppercase text-muted-foreground">
        <span className="relative flex h-3.5 w-3.5 items-center justify-center">
          <Radio className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          <span className="signal-blip absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
        </span>
        AI 资讯快讯
      </div>
      <div className="absolute bottom-4 left-[18px] top-11 w-px bg-border" />

      <div className="space-y-0">
        <AnimatePresence initial>
          {data.map((item, i) => (
            <motion.div
              key={item.id ?? i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, delay: Math.min(i, 9) * 0.03, ease: [0.22, 1, 0.36, 1] }}
              className="group relative rounded-lg py-2 pl-7 pr-2 transition-colors hover:bg-muted/35"
            >
              <div className="absolute left-[8px] top-[15px] flex h-[15px] w-[15px] items-center justify-center rounded-full bg-card">
                <div className="h-2 w-2 rounded-full bg-primary/55 transition-all duration-200 group-hover:scale-[1.35] group-hover:bg-primary group-hover:shadow-[0_0_8px_hsl(var(--primary)/0.7)]" />
              </div>

              <div className="min-w-0">
                {/* Time + Source + Title */}
                <div className="flex items-baseline gap-2">
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                    {fmtTime(item.published_at)}
                  </span>
                  {item.source && (
                    <span className="shrink-0 truncate text-[11px] text-muted-foreground/60">
                      {item.source}
                    </span>
                  )}
                </div>

                {/* Title — the subject */}
                <div className="mt-0.5 flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[13px] font-semibold leading-snug text-foreground underline-offset-2 decoration-primary/40 transition-colors hover:text-primary hover:underline"
                      >
                        {item.title}
                      </a>
                    ) : (
                      <span className="text-[13px] font-semibold leading-snug text-foreground">
                        {item.title}
                      </span>
                    )}
                  </div>
                  {shouldShowAI(item.ai_enrichment) && (
                    <span className="shrink-0 inline-flex items-center gap-0.5 rounded bg-primary/10 px-1 py-0.5 text-[9px] font-medium text-primary" title="AI 生成摘要">
                      <Sparkles className="h-2 w-2" />AI
                    </span>
                  )}
                </div>

                {/* Summary */}
                {item.summary && (
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/80 line-clamp-3">
                    {item.summary}
                  </p>
                )}
                {shouldShowAI(item.ai_enrichment) && item.ai_enrichment!.tags.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {item.ai_enrichment!.tags.map((t) => (
                      <span key={t} className="inline-flex rounded-full bg-primary/5 px-1.5 py-0.5 text-[9px] text-primary/70">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
