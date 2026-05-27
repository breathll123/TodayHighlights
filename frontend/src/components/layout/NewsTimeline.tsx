import { ExternalLink } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

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
      <div className="bg-card/70 backdrop-blur-md border border-white/20 rounded-xl p-6 text-center text-sm text-muted-foreground">
        暂无快讯
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />

      <div className="space-y-0">
        <AnimatePresence initial={false}>
          {data.map((item, i) => (
            <motion.div
              key={item.id ?? i}
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: "auto", marginBottom: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="relative pl-6 py-2 group"
            >
              {/* Dot */}
              <div className="absolute left-0 top-[14px] w-[15px] h-[15px] flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-primary/30 group-hover:bg-primary/60 group-hover:scale-125 transition-all duration-200" />
              </div>

              {/* Content */}
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-[11px] text-muted-foreground/60 shrink-0 tabular-nums">
                    {fmtTime(item.published_at)}
                  </span>
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[13px] leading-snug text-foreground/85 hover:text-primary transition-colors line-clamp-2 flex-1"
                    >
                      {item.title}
                      <ExternalLink className="inline-block w-3 h-3 ml-1 text-muted-foreground/30 group-hover:text-primary/50 transition-colors" />
                    </a>
                  ) : (
                    <span className="text-[13px] leading-snug text-foreground/85 line-clamp-2 flex-1">
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
