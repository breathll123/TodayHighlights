import { BlockCard } from "./BlockCard";
import { BlockSkeleton } from "./BlockSkeleton";
import { CompactTable } from "./CompactTable";
import { NewsTimeline } from "./NewsTimeline";
import { FIELD_DEFS, DEFAULT_FIELDS } from "@/lib/field-defs";
import { cn } from "@/lib/utils";

const SOURCE_LABELS: Record<string, string> = {
  topic: "主题看点",
  raw: "来源内容",
  hot_stocks: "雪球热股",
  hot_events: "雪球话题",
  xueqiu_hot_cn: "雪球 A 股",
  xueqiu_hot_hk: "雪球港股",
  xueqiu_hot_us: "雪球美股",
  screener: "行情筛选",
  eastmoney_sectors: "概念板块",
  eastmoney_industry: "行业板块",
  eastmoney_indices: "指数行情",
  eastmoney_longhu: "龙虎榜",
  eastmoney_capital_flow: "资金流向",
  eastmoney_announcements: "公告",
  tonghuashun_news: "同花顺",
};

function sourceLabel(item: any, sourceType: string): string {
  return SOURCE_LABELS[item.source ?? sourceType] ?? "DataFlow";
}

function fmtTitle(item: any): string {
  const name = item.title ?? item.name ?? "";
  const code = item.symbols?.[0] ?? item.related_symbols_json?.[0];
  if (!code || String(code).startsWith("BK") || name.includes(String(code))) return name;
  return `${name}(${code})`;
}

function mapItem(item: any, sourceType: string) {
  let subtitle = "";
  const summary = item.summary ?? "";
  // Sectors/industry: "指数 4655.96 涨跌幅 +6.26%  |  华虹公司 +15.79%"
  if (summary.includes("|")) {
    subtitle = summary.split("|")[1]?.trim() ?? "";
  }
  // Longhu: "成交31.4亿 买入49.8亿 卖出18.5亿" → "买49.8/卖18.5"
  else if (sourceType === "eastmoney_longhu") {
    const b = summary.match(/买入([\d.]+亿)/);
    const s = summary.match(/卖出([\d.]+亿)/);
    if (b && s) subtitle = `买${b[1]}/卖${s[1]}`;
  }
  // Raw / news: use published_at as subtitle
  else if (item.published_at) {
    subtitle = new Date(item.published_at).toLocaleDateString();
  }
  return {
    id: item.id,
    title: fmtTitle(item),
    subtitle,
    percent: item.percent,
    score: item.score ?? item.value,
    url: item.url,
  };
}

export function GridRenderer({ blocks, isLoading }: { blocks: any[]; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="page-grid">
        {[1, 2, 3, 4].map((i) => (
          <BlockSkeleton key={i} colSpan={i % 2 === 0 ? 1 : 2} />
        ))}
      </div>
    );
  }

  if (blocks.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/80 bg-card/50 px-6 py-14 text-center text-muted-foreground">
        <p className="mb-2 text-base font-semibold text-foreground">当前页面还没有发布内容模块</p>
        <p className="text-sm">进入后台布局，将数据源、榜单或快讯模块发布到这个主题页。</p>
      </div>
    );
  }

  return (
    <div className="page-grid">
      {blocks.map((block) => {
        const st = block.source_type as string;
        const allFields = FIELD_DEFS[st] || [];
        const cfgFields: string[] | undefined = block.source_config?.display_fields;
        const selectedKeys: string[] = (cfgFields && cfgFields.length > 0 ? cfgFields : DEFAULT_FIELDS[st]) || allFields.map((f) => f.key);
        const displayFields = allFields.filter((f) => selectedKeys.includes(f.key));

        return (
          <section
            key={block.id}
            className="min-w-0 space-y-3"
            style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
          >
            <div className="flex min-h-8 items-center justify-between gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold text-foreground">{block.title}</h2>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-2 py-1 text-[11px] font-medium",
                  block.status === "published"
                    ? "border-primary/25 bg-primary/10 text-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                )}
              >
                {block.data?.length ?? 0} 条
              </span>
            </div>

            {block.data?.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/80 bg-card/55 p-6 text-center text-sm text-muted-foreground">暂无数据</div>
            ) : block.source_type === "tonghuashun_news" || block.display_style === "timeline" ? (
              <NewsTimeline data={block.data.map((item: any) => ({
                id: item.id,
                title: item.title ?? "",
                url: item.url,
                published_at: item.published_at,
                summary: item.summary,
              }))} />
            ) : block.display_style === "list" ? (
              <div className="overflow-hidden rounded-xl border border-border/70 bg-card/75 shadow-sm">
                <CompactTable
                  data={block.data.map((item: any) => mapItem(item, st))}
                  fields={displayFields}
                />
              </div>
            ) : (
              <div className="space-y-1.5">
                {block.data.map((item: any, i: number) => (
                  <BlockCard
                    key={item.id ?? i}
                    title={fmtTitle(item)}
                    summary={item.summary ?? item.content ?? ""}
                    tags={item.tags_json ?? item.tags}
                    sourceName={sourceLabel(item, st)}
                    isPinned={item.is_pinned}
                    symbols={item.related_symbols_json ?? item.symbols ?? (item.code ? [item.code] : undefined)}
                    url={item.url}
                  />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
