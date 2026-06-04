interface ScheduleItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  competition?: string;
  group?: string;
  round?: string;
  time?: string;
  team_a?: string;
  team_b?: string;
}

interface Props {
  data: ScheduleItem[];
}

function groupByRound(items: ScheduleItem[]): Record<string, ScheduleItem[]> {
  const groups: Record<string, ScheduleItem[]> = {};
  for (const item of items) {
    const key = item.group ? `${item.group}组` : item.round || "其他";
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}

export function ScheduleList({ data }: Props) {
  const groups = groupByRound(data);
  const first = data[0];
  const comp = first?.competition || "";

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/30 px-3 py-2">
        <h4 className="text-xs font-semibold text-foreground/80">{comp} 赛程</h4>
        <span className="shrink-0 text-[10px] text-muted-foreground/60">{data.length} 场</span>
      </div>

      {Object.entries(groups).map(([groupLabel, matches]) => (
        <section key={groupLabel} className="min-w-0">
          <div className="border-b border-border/40 bg-muted/20 px-3 py-1 text-[10px] font-semibold text-muted-foreground">
            {groupLabel}
            <span className="ml-1.5 font-normal text-muted-foreground/60">{matches[0]?.round ? `第${matches[0].round}轮` : ""}</span>
          </div>

          {matches.map((m) => (
            <a
              key={m.id}
              href={m.url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 border-b border-border/40 px-3 py-2 text-xs last:border-b-0 transition-colors hover:bg-primary/[0.04]"
            >
              <span className="shrink-0 w-10 text-[11px] tabular-nums text-muted-foreground">{m.time}</span>
              <span className="flex-1 min-w-0 text-right truncate font-medium">{m.team_a}</span>
              <span className="shrink-0 text-[11px] font-semibold text-muted-foreground">vs</span>
              <span className="flex-1 min-w-0 truncate font-medium">{m.team_b}</span>
            </a>
          ))}
        </section>
      ))}
    </div>
  );
}
