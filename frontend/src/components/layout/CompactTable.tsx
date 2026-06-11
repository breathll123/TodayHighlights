import type { FieldDef } from "@/lib/field-defs";
import { cn } from "@/lib/utils";
import { RankBadge, rankRowTone } from "./RankBadge";

interface Row {
  id?: string | number;
  rank?: number;
  title: string;
  subtitle?: string;
  percent?: number;
  score?: string | number;
  url?: string;
  release?: string;
  [key: string]: unknown;
}

interface Props {
  data: Row[];
  fields: FieldDef[];
  showRank?: boolean;
}

function fmtNum(n: string | number | undefined): string {
  if (n == null) return "-";
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return typeof n === "string" ? n : "-";
  if (typeof n === "string" && /[^\d.]/.test(n)) return n;
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
  return String(Math.round(v));
}

function cell(key: string, item: Row) {
  switch (key) {
    case "title":
      return item.url ? (
        <a href={item.url} target="_blank" rel="noopener noreferrer" className="block truncate hover:text-primary transition-colors">
          {item.title}
        </a>
      ) : (
        <span className="truncate">{item.title}</span>
      );
    case "percent":
      return (
        <span className={`text-xs font-semibold tabular-nums ${item.percent != null ? (item.percent > 0 ? "text-red-500" : "text-green-500") : "text-muted-foreground"}`}>
          {item.percent != null ? `${item.percent > 0 ? "+" : ""}${item.percent.toFixed(2)}%` : "—"}
        </span>
      );
    case "score":
      return <span className="text-xs text-muted-foreground tabular-nums">{fmtNum(item.score)}</span>;
    case "subtitle":
      return <span className="text-xs text-muted-foreground truncate">{item.subtitle || "—"}</span>;
    case "release":
      return <span className="text-xs text-muted-foreground tabular-nums">{item.release || "—"}</span>;
    default: {
      const val = item[key];
      return <span className="text-xs text-muted-foreground truncate">{val != null ? String(val) : "—"}</span>;
    }
  }
}

function gridCols(fields: FieldDef[], showRank = false): string {
  // First field (title) gets 3fr, each subsequent gets 1fr
  const widths = fields.map((_, i) => (i === 0 ? "3fr" : "1fr"));
  return showRank ? ["2.75rem", ...widths].join(" ") : widths.join(" ");
}

function colAlign(f: FieldDef, i: number): string {
  if (i === 0) return "text-left";
  if (f.type === "number") return "text-right";
  return "text-left";
}

export function CompactTable({ data, fields, showRank = false }: Props) {
  const cols = gridCols(fields, showRank);
  return (
    <div className="overflow-hidden bg-card/70 backdrop-blur-md border border-white/20 rounded-lg">
      <div className="grid items-center gap-x-3 border-b bg-muted/30 px-3 py-2 text-[11px] font-medium text-muted-foreground" style={{ gridTemplateColumns: cols }}>
        {showRank ? <span className="text-center">排名</span> : null}
        {fields.map((f, i) => (
          <span key={f.key} className={colAlign(f, i)}>{f.label}</span>
        ))}
      </div>
      {data.map((item, idx) => (
        <div
          key={item.id ?? idx}
          data-rank-row={showRank ? item.rank : undefined}
          className={cn(
            "grid min-h-10 items-center gap-x-3 border-b px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30",
            showRank && rankRowTone(item.rank),
          )}
          style={{ gridTemplateColumns: cols }}
        >
          {showRank ? <RankBadge rank={item.rank} className="justify-center" /> : null}
          {fields.map((f, i) => (
            <div key={f.key} className={colAlign(f, i)}>
              {cell(f.key, item)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
