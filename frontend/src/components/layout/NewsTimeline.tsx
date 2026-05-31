import { motion, AnimatePresence } from "framer-motion";
import { Radio } from "lucide-react";

interface NewsItem {
  id: number;
  title: string;
  url?: string;
  published_at?: string;
  summary?: string;
}

function fmtTime(ts: string | null | undefined) {
  if (!ts) return "";
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
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
        Live Feed
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
                <div className="flex items-baseline gap-2">
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
                    {fmtTime(item.published_at)}
                  </span>
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="line-clamp-2 flex-1 text-[13px] font-medium leading-snug text-foreground/90 transition-colors hover:text-primary"
                    >
                      {item.title}
                    </a>
                  ) : (
                    <span className="line-clamp-2 flex-1 text-[13px] font-medium leading-snug text-foreground/90">
                      {item.title}
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
