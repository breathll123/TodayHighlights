import { motion, AnimatePresence } from "framer-motion";
import { Radio } from "lucide-react";

interface NewsItem {
  id: string | number;
  title: string;
  url?: string;
  published_at?: string;
  summary?: string;
  source?: string;
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
        <Radio className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
        AI 资讯快讯
      </div>
      <div className="absolute bottom-4 left-[18px] top-11 w-px bg-border" />

      <div className="space-y-0">
        <AnimatePresence initial={false}>
          {data.map((item, i) => (
            <motion.div
              key={item.id ?? i}
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: "auto", marginBottom: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="group relative rounded-lg py-2 pl-7 pr-2 transition-colors hover:bg-muted/35"
            >
              <div className="absolute left-[8px] top-[15px] flex h-[15px] w-[15px] items-center justify-center rounded-full bg-card">
                <div className="h-2 w-2 rounded-full bg-primary/55 transition-all duration-200 group-hover:scale-125 group-hover:bg-primary" />
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

                {/* Title */}
                <div className="mt-0.5">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[13px] font-medium leading-snug text-foreground/90 transition-colors hover:text-primary"
                    >
                      {item.title}
                    </a>
                  ) : (
                    <span className="text-[13px] font-medium leading-snug text-foreground/90">
                      {item.title}
                    </span>
                  )}
                </div>

                {/* Summary */}
                {item.summary && (
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/80 line-clamp-3">
                    {item.summary}
                  </p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
