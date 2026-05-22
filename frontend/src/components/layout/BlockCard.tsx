import { TrendingUp, Pin } from "lucide-react";

interface BlockCardProps {
  title: string;
  summary: string;
  tags?: string[];
  score?: number;
  isPinned?: boolean;
  symbols?: string[];
  className?: string;
}

export function BlockCard({ title, summary, tags, score, isPinned, symbols, className }: BlockCardProps) {
  return (
    <div className={`p-4 border rounded-lg bg-card hover:shadow-sm transition-shadow ${isPinned ? "border-l-2 border-l-orange-500" : ""} ${className ?? ""}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm leading-snug">
          {isPinned && <Pin className="w-3 h-3 inline text-orange-500 mr-1" />}
          {title}
        </h3>
        {score != null && (
          <span className="text-xs text-muted-foreground flex items-center gap-1 shrink-0">
            <TrendingUp className="w-3 h-3" />
            {score}
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground line-clamp-3 mb-3">{summary}</p>
      <div className="flex items-center gap-2 flex-wrap">
        {symbols?.map((s) => (
          <span key={s} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium">
            {s}
          </span>
        ))}
        {tags?.map((t) => (
          <span key={t} className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
