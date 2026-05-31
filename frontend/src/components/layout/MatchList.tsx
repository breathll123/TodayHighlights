interface MatchItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  league: string;
  status: string;
  team_a: string;
  team_b: string;
  score_a: string;
  score_b: string;
  minute: string;
  start_time: string;
}

interface Props {
  data: MatchItem[];
}

const STATUS_LABELS: Record<string, string> = {
  Playing: "进行中",
  Played: "已结束",
  Fixture: "未开始",
  Postponed: "延期",
  Cancelled: "取消",
  Uncertain: "待定",
};

function groupByLeague(items: MatchItem[]): Record<string, MatchItem[]> {
  const groups: Record<string, MatchItem[]> = {};
  for (const item of items) {
    const league = item.league || "其他";
    if (!groups[league]) groups[league] = [];
    groups[league].push(item);
  }
  return groups;
}

export function MatchList({ data }: Props) {
  const groups = groupByLeague(data);
  const leagues = Object.keys(groups);

  return (
    <div className="space-y-4">
      {leagues.map((league) => (
        <div key={league}>
          <h3 className="text-xs font-semibold text-muted-foreground tracking-wide mb-2 px-1">
            {league}
          </h3>
          <div className="space-y-1">
            {groups[league].map((m) => (
              <a
                key={m.id}
                href={m.url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/70 px-3 py-2.5 transition-colors hover:border-primary/40 hover:bg-card"
              >
                {/* Status indicator */}
                <span className="shrink-0 text-[10px] font-medium text-muted-foreground w-12 text-right">
                  {m.status === "Playing" ? (
                    <span className="text-red-500 animate-pulse">{m.minute || "LIVE"}</span>
                  ) : m.status === "Fixture" ? (
                    m.start_time?.split(" ")?.[1]?.slice(0, 5) || ""
                  ) : (
                    STATUS_LABELS[m.status] || m.status
                  )}
                </span>

                {/* Teams + Score */}
                <span className="flex-1 min-w-0 text-sm font-medium truncate">
                  {m.team_a}
                </span>

                {/* Score */}
                <span className="shrink-0 text-sm font-semibold tabular-nums text-foreground">
                  {m.status === "Fixture" ? "vs" : `${m.score_a || "—"} - ${m.score_b || "—"}`}
                </span>

                <span className="flex-1 min-w-0 text-sm font-medium text-right truncate">
                  {m.team_b}
                </span>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
