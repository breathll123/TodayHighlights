import { TrendingUp } from "lucide-react";

interface CompactTableProps {
  data: any[];
  columns: { key: string; label: string; className?: string }[];
}

export function CompactTable({ data, columns }: CompactTableProps) {
  return (
    <div className="overflow-hidden">
      <div className="grid grid-cols-[1fr_80px_100px] text-[11px] font-medium text-muted-foreground px-4 py-2 border-b bg-muted/30">
        {columns.map((c) => (
          <span key={c.key} className={c.className}>{c.label}</span>
        ))}
      </div>
      {data.map((item, i) => (
        <div
          key={item.id ?? i}
          className="grid grid-cols-[1fr_80px_100px] text-sm px-4 py-2.5 border-b last:border-0 hover:bg-muted/30 transition-colors items-center"
        >
          <span className="font-medium truncate pr-2">{item.title}</span>
          <span className={`text-xs font-semibold ${item.percent != null ? (item.percent > 0 ? "text-red-500" : "text-green-500") : "text-muted-foreground"}`}>
            {item.percent != null ? `${item.percent > 0 ? "+" : ""}${item.percent}%` : "-"}
          </span>
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            {item.score != null && item.score > 0 ? (item.score > 999 ? `${(item.score / 1000).toFixed(0)}k` : item.score) : "-"}
          </span>
        </div>
      ))}
    </div>
  );
}
