import { motion } from "framer-motion";
import type { FieldDef } from "@/lib/field-defs";
import { cn } from "@/lib/utils";
import { FlashValue } from "./AnimatedNumber";
import { RankBadge, rankRowTone } from "./RankBadge";

const easeOutQuint: [number, number, number, number] = [0.22, 1, 0.36, 1];

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
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block truncate font-medium text-foreground underline-offset-2 decoration-primary/40 transition-colors hover:text-primary hover:underline"
        >
          {item.title}
        </a>
      ) : (
        <span className="block truncate font-medium text-foreground">{item.title}</span>
      );
    case "percent":
      return (
        <FlashValue
          value={item.percent}
          className={`text-xs font-semibold tabular-nums ${item.percent != null ? (item.percent > 0 ? "text-red-500" : "text-green-500") : "text-muted-foreground"}`}
        >
          {item.percent != null ? `${item.percent > 0 ? "+" : ""}${item.percent.toFixed(2)}%` : "—"}
        </FlashValue>
      );
    case "score":
      return <span className="text-xs text-muted-foreground tabular-nums">{fmtNum(item.score)}</span>;
    case "net_amount": {
      const value = Number(item.net_amount ?? 0);
      const tone = value > 0 ? "text-red-500" : value < 0 ? "text-green-500" : "text-muted-foreground";
      const sign = value > 0 ? "+" : value < 0 ? "-" : "";
      return (
        <FlashValue value={value} className={`text-xs font-semibold tabular-nums ${tone}`}>
          {sign}{fmtNum(Math.abs(value))}
        </FlashValue>
      );
    }
    case "reason": {
      const reason = typeof item.reason === "string" ? item.reason : "";
      return (
        <span className="block truncate text-xs text-muted-foreground" title={reason}>
          {reason || "—"}
        </span>
      );
    }
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
    /* 外层滚动容器：在移动端如果宽度不足，支持横向滚动，避免表格被压挤变形 */
    <div className="w-full overflow-x-auto scrollbar-thin">
      {/* 表格主体：在小屏幕 (max-width: 640px) 时限制最小宽度为 500px，防止内容堆叠看不清；在大屏幕下自适应 */}
      <div className="min-w-[500px] sm:min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75">
        <div className="grid items-center gap-x-3 border-b bg-muted/30 px-3 py-2 text-[11px] font-medium text-muted-foreground" style={{ gridTemplateColumns: cols }}>
          {showRank ? <span className="text-center">排名</span> : null}
          {fields.map((f, i) => (
            /* 单元格表头：加入 min-w-0 以防文本超出时溢出 */
            <span key={f.key} className={cn(colAlign(f, i), "min-w-0")}>{f.label}</span>
          ))}
        </div>
        {data.map((item, idx) => {
          const tone = showRank ? rankRowTone(item.rank) : "";
          return (
            <motion.div
              key={item.id ?? idx}
              data-rank-row={showRank ? item.rank : undefined}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: Math.min(idx, 8) * 0.025, ease: easeOutQuint }}
              className={cn(
                "relative grid min-h-10 items-center gap-x-3 border-b px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30",
                tone || "signal-row",
              )}
              style={{ gridTemplateColumns: cols }}
            >
              {showRank ? <RankBadge rank={item.rank} className="justify-center" /> : null}
              {fields.map((f, i) => (
                /* 单元格内容：加入 min-w-0 配合 truncate 实现超出自动截断，避免撑大 Grid 列 */
                <div key={f.key} className={cn(colAlign(f, i), "min-w-0")}>
                  {cell(f.key, item)}
                </div>
              ))}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
