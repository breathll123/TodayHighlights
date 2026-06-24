import { motion } from "framer-motion";
import { Star } from "lucide-react";
import type { FieldDef } from "@/lib/field-defs";
import { cn } from "@/lib/utils";

const easeOutQuint: [number, number, number, number] = [0.22, 1, 0.36, 1];

interface SkillItem {
  id?: string | number;
  rank?: number;
  title: string;
  owner?: string;
  summary?: string;
  url?: string;
  score?: number;
}

function formatStars(value: number | undefined): string {
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

export function SkillRanking({ data, fields }: { data: SkillItem[]; fields: FieldDef[] }) {
  const keys = new Set(fields.map((f) => f.key));
  const showDesc = keys.has("summary");
  const showStars = keys.has("score");

  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无 skill 数据
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/70 bg-card/75">
      {data.map((item, index) => (
        <motion.a
          key={item.id ?? index}
          href={item.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: Math.min(index, 8) * 0.025, ease: easeOutQuint }}
          className="skill-row signal-row relative flex items-center gap-3 border-b px-3 py-2.5 transition-colors first:rounded-t-lg last:rounded-b-lg last:border-0 hover:bg-muted/30"
        >
          <span className="w-6 shrink-0 text-center text-xs font-semibold tabular-nums text-muted-foreground">
            {item.rank ?? index + 1}
          </span>
          <div className={cn("min-w-0", showDesc ? "max-w-[42%] shrink-0" : "flex-1")}>
            <div className="flex items-baseline gap-1.5">
              <span className="truncate text-sm font-medium text-foreground">{item.title}</span>
              {item.owner ? (
                <span className="shrink-0 text-[11px] text-muted-foreground/70">{item.owner}</span>
              ) : null}
            </div>
          </div>
          {showDesc ? (
            item.summary ? (
              <div className="skill-desc relative min-w-0 flex-1">
                <p className="truncate text-xs text-muted-foreground">{item.summary}</p>
                <span className="skill-desc-tip" role="tooltip">{item.summary}</span>
              </div>
            ) : (
              <div className="flex-1" />
            )
          ) : null}
          {showStars ? (
            <span className="inline-flex shrink-0 items-center gap-1 text-xs tabular-nums text-muted-foreground">
              <Star className="h-3 w-3 text-amber-400" aria-hidden="true" />
              {formatStars(item.score)}
            </span>
          ) : null}
        </motion.a>
      ))}
    </div>
  );
}
