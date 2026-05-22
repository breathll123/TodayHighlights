import { TrendingUp, Pin, ArrowRight } from "lucide-react";

interface BlockListItemProps {
  title: string;
  summary: string;
  tags?: string[];
  score?: number;
  isPinned?: boolean;
  symbols?: string[];
}

export function BlockListItem({ title, summary, tags, score, isPinned, symbols }: BlockListItemProps) {
  return (
    <div className={`flex items-center gap-4 px-4 py-3 border-b last:border-0 hover:bg-muted/50 transition-colors ${isPinned ? "border-l-2 border-l-orange-500 pl-3" : ""}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {isPinned && <Pin className="w-3 h-3 text-orange-500 shrink-0" />}
          {symbols?.map((s) => (
            <span key={s} className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded font-medium shrink-0">
              {s}
            </span>
          ))}
          <h3 className="font-medium text-sm truncate">{title}</h3>
        </div>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{summary}</p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {tags?.map((t) => (
          <span key={t} className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded hidden sm:inline">
            {t}
          </span>
        ))}
        {score != null && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            {score}
          </span>
        )}
        <ArrowRight className="w-4 h-4 text-muted-foreground/30" />
      </div>
    </div>
  );
}
