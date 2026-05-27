import { TrendingUp, Pin, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

interface BlockCardProps {
  title: string;
  summary: string;
  tags?: string[];
  score?: number;
  isPinned?: boolean;
  symbols?: string[];
  url?: string;
  className?: string;
}

export function BlockCard({ title, summary, tags, score, isPinned, symbols, url, className }: BlockCardProps) {
  const isClickable = !!url;
  const Tag = isClickable ? "a" : "div";

  const card = (
    <Tag
      {...(isClickable ? { href: url, target: "_blank", rel: "noopener noreferrer" } : {})}
      className={`group block bg-card/70 backdrop-blur-md rounded-xl border border-white/20 shadow-sm transition-shadow duration-300 ${isClickable ? "cursor-pointer hover:border-primary/30 hover:shadow-lg" : ""} ${isPinned ? "ring-1 ring-orange-500/20" : ""} ${className ?? ""}`}
    >
      {isPinned && (
        <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-orange-500/10 via-amber-500/5 to-transparent pointer-events-none" />
      )}
      <div className="relative p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            {isPinned && <Pin className="w-3.5 h-3.5 text-orange-500 shrink-0" />}
            {symbols?.slice(0, 3).map((s) => (
              <span key={s} className="text-[11px] bg-primary/10 text-primary px-2 py-0.5 rounded-md font-semibold shrink-0 tracking-tight">
                {s}
              </span>
            ))}
            <h3 className="font-semibold text-[15px] leading-snug text-foreground/90 truncate">{title}</h3>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {score != null && score > 0 && (
              <span className="text-[11px] text-muted-foreground flex items-center gap-1 bg-muted/50 px-2 py-0.5 rounded-full">
                <TrendingUp className="w-3 h-3" />
                {score > 999 ? `${(score / 1000).toFixed(0)}k` : score}
              </span>
            )}
            {isClickable && (
              <ExternalLink className="w-3.5 h-3.5 text-muted-foreground/40 group-hover:text-primary transition-colors shrink-0" />
            )}
          </div>
        </div>

        {/* Summary */}
        <p className="text-[13px] text-muted-foreground/80 leading-relaxed line-clamp-2">
          {summary}
        </p>

        {/* Footer */}
        {tags && tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap mt-3">
            {tags.map((t) => (
              <span key={t} className="text-[11px] bg-muted/80 text-muted-foreground px-2 py-0.5 rounded-full">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </Tag>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      whileHover={{ y: -3, scale: 1.01 }}
      className="relative"
    >
      {card}
    </motion.div>
  );
}
