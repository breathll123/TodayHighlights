import { useState } from "react";
import { TrendingUp, Pin, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

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
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`group bg-card rounded-xl border shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer ${isPinned ? "border-l-2 border-l-orange-500 shadow-orange-100" : ""} ${className ?? ""}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="p-5">
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
            {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground/50" /> : <ChevronDown className="w-4 h-4 text-muted-foreground/50" />}
          </div>
        </div>

        {/* Summary */}
        <p className={`text-[13px] text-muted-foreground/80 leading-relaxed ${expanded ? "" : "line-clamp-2"}`}>
          {summary}
        </p>

        {/* Expanded content */}
        {expanded && (
          <div className="mt-4 pt-4 border-t animate-in fade-in slide-in-from-top-2 duration-200">
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline mb-3"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="w-3 h-3" />查看原文
              </a>
            )}
            <div className="flex items-center gap-2 flex-wrap mt-2">
              {tags?.map((t) => (
                <span key={t} className="text-[11px] bg-muted/80 text-muted-foreground px-2 py-0.5 rounded-full">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
