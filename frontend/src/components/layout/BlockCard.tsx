import { ArrowUpRight, Pin, Tags } from "lucide-react";
import { motion } from "framer-motion";

interface BlockCardProps {
  title: string;
  summary: string;
  tags?: string[];
  sourceName?: string;
  isPinned?: boolean;
  url?: string;
  className?: string;
}

export function BlockCard({ title, summary, tags, sourceName, isPinned, url, className }: BlockCardProps) {
  const isClickable = !!url;
  const Tag = isClickable ? "a" : "div";
  const card = (
    <Tag
      {...(isClickable ? { href: url, target: "_blank", rel: "noopener noreferrer" } : {})}
      className={`group block overflow-hidden rounded-lg border border-border/75 bg-card/80 shadow-sm transition-all duration-200 ${isClickable ? "cursor-pointer hover:border-primary/45 hover:bg-card hover:shadow-md" : ""} ${isPinned ? "ring-1 ring-accent/35" : ""} ${className ?? ""}`}
    >
      {isPinned && (
        <div className="absolute inset-0 rounded-lg bg-accent/10 pointer-events-none" />
      )}
      <div className="relative p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            {isPinned && (
              <span className="inline-flex h-5 items-center gap-1 rounded-full border border-accent/30 bg-accent/12 px-1.5 text-[10px] font-semibold text-accent">
                <Pin className="h-2.5 w-2.5" aria-hidden="true" />
                置顶
              </span>
            )}
            {sourceName && (
              <span className="truncate rounded-full border border-primary/20 bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                {sourceName}
              </span>
            )}
          </div>
          {isClickable && <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" aria-hidden="true" />}
        </div>

        <h3 className="mb-1.5 text-base font-semibold leading-snug text-foreground">{title}</h3>

        <p className="text-sm leading-5 text-muted-foreground line-clamp-2">
          {summary}
        </p>

        {tags && tags.length > 0 && (
          <div className="mt-2 flex items-center gap-1 overflow-hidden">
            <Tags className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden="true" />
            {tags.slice(0, 2).map((t) => (
              <span key={t} className="truncate rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                {t}
              </span>
            ))}
            {tags.length > 2 && <span className="text-[10px] text-muted-foreground">+{tags.length - 2}</span>}
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
      whileHover={{ y: -2 }}
      className="relative"
    >
      {card}
    </motion.div>
  );
}
