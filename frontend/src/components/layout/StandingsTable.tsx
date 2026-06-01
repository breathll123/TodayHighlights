interface StandingItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  rank?: number;
  team?: string;
  logo?: string;
  gp?: string;
  pts?: string;
  wdl?: string;
  gf?: string;
  ga?: string;
  gd?: string;
  league?: string;
  season?: string;
  updated?: string;
}

interface Props {
  data: StandingItem[];
}

function proxyImg(url?: string): string {
  if (!url) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}

function TeamLogo({ url, name }: { url?: string; name?: string }) {
  if (!url) {
    const initial = (name || "?").charAt(0);
    return (
      <span className="h-5 w-5 shrink-0 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold text-muted-foreground">
        {initial}
      </span>
    );
  }
  return (
    <img
      src={proxyImg(url)}
      alt=""
      className="h-5 w-5 shrink-0 rounded-full object-contain"
      loading="lazy"
    />
  );
}

export function StandingsTable({ data }: Props) {
  const first = data[0];
  const league = first?.league || "";
  const season = first?.season || "";
  const updated = first?.updated || "";

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/70 bg-card/75 shadow-sm">
      <section className="min-w-0">
        <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/30 px-3 py-1.5">
          <h4 className="flex min-w-0 items-center gap-1.5 text-xs font-semibold text-foreground/80">
            {league} 积分榜
            {season ? (
              <span className="font-normal text-muted-foreground">{season}</span>
            ) : null}
          </h4>
          {updated ? (
            <span className="shrink-0 text-[10px] text-muted-foreground/60">
              更新 {updated}
            </span>
          ) : null}
        </div>

            {/* Header row */}
            <div className="grid grid-cols-[2.5rem_minmax(0,1fr)_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem] gap-1 border-b border-border/40 bg-muted/20 px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
              <span className="text-center">#</span>
              <span>球队</span>
              <span className="text-center">场</span>
              <span className="text-center">胜/平/负</span>
              <span className="text-center">进</span>
              <span className="text-center">失</span>
              <span className="text-center">净</span>
              <span className="text-center font-semibold">分</span>
            </div>

            {data.map((item, i) => (
              <a
                key={item.id}
                href={item.url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className={`grid grid-cols-[2.5rem_minmax(0,1fr)_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem_2.5rem] gap-1 border-b border-border/40 px-2.5 py-2 text-xs last:border-b-0 transition-colors hover:bg-primary/[0.04] ${
                  i < 4 ? "bg-primary/[0.02]" : ""
                }`}
              >
                <span className={`text-center tabular-nums font-medium ${
                  item.rank && item.rank <= 4 ? "text-primary" : "text-muted-foreground"
                }`}>
                  {item.rank}
                </span>
                <span className="flex items-center gap-1.5 truncate">
                  <TeamLogo url={item.logo} name={item.team} />
                  <span className="truncate font-medium">{item.team}</span>
                </span>
                <span className="text-center tabular-nums text-muted-foreground">{item.gp || "-"}</span>
                <span className="text-center tabular-nums text-muted-foreground text-[10px]">{item.wdl || "-"}</span>
                <span className="text-center tabular-nums text-muted-foreground">{item.gf || "-"}</span>
                <span className="text-center tabular-nums text-muted-foreground">{item.ga || "-"}</span>
                <span className={`text-center tabular-nums ${(item.gd || "").startsWith("-") ? "text-green-500" : (item.gd && item.gd !== "0" ? "text-red-500" : "text-muted-foreground")}`}>
                  {item.gd || "-"}
                </span>
                <span className="text-center tabular-nums font-bold text-foreground">{item.pts || "-"}</span>
              </a>
            ))}
      </section>
    </div>
  );
}
