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
      className={`group block overflow-hidden rounded-lg border border-border/50 bg-card/80 shadow-sm transition-all duration-200 ${isClickable ? "cursor-pointer hover:border-primary/40 hover:bg-card hover:shadow-md" : ""} ${isPinned ? "ring-1 ring-amber-500/30" : ""} ${className ?? ""}`}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-base font-semibold leading-snug text-foreground min-w-0">
            {isPinned && (
              <Pin className="inline h-3.5 w-3.5 -mt-0.5 mr-1 text-amber-500" aria-hidden="true" />
            )}
            {title}
          </h3>
          {isClickable && (
            <ArrowUpRight className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground/60 transition-colors group-hover:text-primary" aria-hidden="true" />
          )}
        </div>

        <p className="mt-2 text-sm leading-5 text-muted-foreground line-clamp-2">
          {summary}
        </p>

        {tags && tags.length > 0 && (
          <div className="mt-3 flex items-center gap-1.5 overflow-hidden">
            <Tags className="h-3 w-3 shrink-0 text-muted-foreground/60" aria-hidden="true" />
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
