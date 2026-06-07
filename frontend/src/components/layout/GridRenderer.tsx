import { useState } from "react";
import { motion } from "framer-motion";
import { BrainCircuit, CalendarClock, ChartNoAxesCombined, Newspaper, Trophy } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { BlockCard } from "./BlockCard";
import { BlockSkeleton } from "./BlockSkeleton";
import { CompactTable } from "./CompactTable";
import { MatchCards } from "./MatchCards";
import { MatchList } from "./MatchList";
import { NewsTimeline } from "./NewsTimeline";
import { StandingsTable } from "./StandingsTable";
import { LeaderboardTable } from "./LeaderboardTable";
import { SectionHeading } from "./SectionHeading";
import { BlockAIAnalysisDrawer } from "./BlockAIAnalysisDrawer";
import { CollapsibleSection } from "./CollapsibleSection";
import { FIELD_DEFS, DEFAULT_FIELDS } from "@/lib/field-defs";
import { generateBlockAIAnalysis } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import type { AIItemEnhancement } from "@/api/types";

function buildAIEnrichment(item: any): AIItemEnhancement | undefined {
  if (!item.generated_by_model) return undefined;
  return {
    status: item.review_status ?? "generated",
    summary: item.summary ?? "",
    tags: item.tags_json ?? [],
    importance_score: item.score ?? 0,
  };
}

const SOURCE_NAMES: Record<string, string> = {
  topic: "主题看点",
  raw: "来源内容",
  hot_stocks: "雪球热股",
  hot_events: "雪球话题",
  xueqiu_hot_cn: "雪球 A 股",
  xueqiu_hot_hk: "雪球港股",
  xueqiu_hot_us: "雪球美股",
  screener: "行情筛选",
  eastmoney_sectors: "东方财富",
  eastmoney_industry: "东方财富",
  eastmoney_longhu: "东方财富",
  eastmoney_capital_flow: "东方财富",
  eastmoney_announcements: "东方财富",
  eastmoney_indices: "指数行情",
  tonghuashun_news: "同花顺",
};

export function sourceNameFor(item: any, sourceType: string): string {
  return SOURCE_NAMES[item.source ?? sourceType] ?? "DataFlow";
}

function fmtTitle(item: any): string {
  const name = item.title ?? item.name ?? "";
  const code = item.symbols?.[0] ?? item.related_symbols_json?.[0];
  if (!code || String(code).startsWith("BK") || name.includes(String(code))) return name;
  return `${name}(${code})`;
}

function sectionIcon(sourceType: string) {
  if (sourceType === "qiumiwu_matches") return CalendarClock;
  if (sourceType === "qiumiwu_standings") return Trophy;
  if (sourceType.startsWith("datalearner_")) return BrainCircuit;
  if (sourceType === "tonghuashun_news") return Newspaper;
  return ChartNoAxesCombined;
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
  // AA index: company from summary
  else if (sourceType === "datalearner_aa_index" && item.company) {
    subtitle = item.company;
  }
  // Raw / news: use published_at as subtitle
  else if (item.published_at) {
    subtitle = new Date(item.published_at).toLocaleDateString();
  }
  return {
    id: item.id,
    rank: item.rank,
    title: fmtTitle(item),
    subtitle,
    percent: item.percent,
    score: item.score ?? item.value,
    url: item.url,
  };
}

function AAIndexBlock({ block, displayFields }: { block: any; displayFields: any[] }) {
  const [region, setRegion] = useState<"global" | "china">("global");
  const allData = block.data || [];
  const filtered = allData.filter((item: any) => item.region === region || (!item.region && region === "global"));
  const first = filtered[0];

  return (
    <div className="border rounded-lg bg-card overflow-hidden">
      {first?.description && (
        <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground leading-relaxed min-w-0">
              {first.description}
            </p>
            <span className="shrink-0 text-[10px] text-muted-foreground/60">
              {first?.version ? `v${first.version}` : ""}
              {first?.updated ? ` · ${first.updated}` : ""}
            </span>
          </div>
          <div className="flex items-center gap-1 mt-2">
            <button
              onClick={() => setRegion("global")}
              className={`rounded px-2.5 py-0.5 text-[10px] transition-[color,background-color,transform] active:scale-[0.97] ${
                region === "global" ? "bg-primary text-primary-foreground font-medium" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              全球排名
            </button>
            <button
              onClick={() => setRegion("china")}
              className={`rounded px-2.5 py-0.5 text-[10px] transition-[color,background-color,transform] active:scale-[0.97] ${
                region === "china" ? "bg-primary text-primary-foreground font-medium" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              国产排名
            </button>
          </div>
        </div>
      )}
      <motion.div
        key={region}
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        <CompactTable
          showRank
          data={filtered.map((item: any, index: number) => ({
            ...mapItem(item, block.source_type),
            rank: index + 1,
          }))}
          fields={displayFields}
        />
      </motion.div>
    </div>
  );
}

export function GridRenderer({ blocks, isLoading, dataUpdatedAt }: { blocks: any[]; isLoading: boolean; dataUpdatedAt?: number }) {
  const { isAuthenticated } = useAuth();
  const [selectedBlock, setSelectedBlock] = useState<any | null>(null);
  const [requiresLogin, setRequiresLogin] = useState(false);
  const analysisMutation = useMutation({
    mutationFn: generateBlockAIAnalysis,
  });

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
      <div className="text-center py-16 text-muted-foreground">
        <p className="text-lg mb-2">暂无内容</p>
        <p className="text-sm">管理员正在准备精彩内容</p>
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
          <CollapsibleSection
            key={block.id}
            blockId={block.id}
            className="space-y-0"
            style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
            heading={
              <SectionHeading
                icon={sectionIcon(st)}
                title={block.title}
                dataUpdatedAt={dataUpdatedAt}
                action={
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedBlock(block);
                      if (!isAuthenticated) {
                        setRequiresLogin(true);
                        return;
                      }
                      setRequiresLogin(false);
                      analysisMutation.mutate({ page_route: block.page_route, block_id: block.id });
                    }}
                  >
                    <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
                    AI 分析
                  </Button>
                }
              />
            }
          >
            {block.data?.length === 0 ? (
              <div className="bg-card border rounded-xl p-6 text-center text-sm text-muted-foreground">暂无数据</div>
            ) : block.source_type === "qiumiwu_matches" && block.display_style === "schedule" ? (
              <MatchCards data={block.data} />
            ) : block.source_type === "qiumiwu_matches" ? (
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} />
            ) : block.source_type === "qiumiwu_fixtures" ? (
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} defaultFilter="fixture" />
            ) : block.source_type === "qiumiwu_schedule" ? (
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} defaultFilter="fixture" />
            ) : block.source_type === "qiumiwu_standings" ? (
              <StandingsTable data={block.data} />
            ) : block.source_type === "datalearner_aa_index" ? (
              <AAIndexBlock block={block} displayFields={displayFields} />
            ) : block.source_type === "datalearner_leaderboard" ? (
              <LeaderboardTable data={block.data} />
            ) : block.source_type === "aihot_news" ? (
              <NewsTimeline data={block.data.map((item: any) => ({
                id: item.id,
                title: item.title ?? "",
                url: item.url,
                published_at: item.published_at,
                summary: item.summary,
                source: item.source,
                ai_enrichment: buildAIEnrichment(item),
              }))} />
            ) : block.source_type === "tonghuashun_news" || block.display_style === "timeline" ? (
              <NewsTimeline data={block.data.map((item: any) => ({
                id: item.id,
                title: item.title ?? "",
                url: item.url,
                published_at: item.published_at,
                summary: item.summary,
                ai_enrichment: buildAIEnrichment(item),
              }))} />
            ) : block.display_style === "list" ? (
              <div className="border rounded-lg bg-card">
                <CompactTable
                  data={block.data.map((item: any) => mapItem(item, st))}
                  fields={displayFields}
                />
              </div>
            ) : (
              <div className="space-y-2">
                {block.data.map((item: any, i: number) => (
                  <BlockCard
                    key={item.id ?? i}
                    title={fmtTitle(item)}
                    summary={item.summary ?? item.content ?? ""}
                    tags={item.tags_json ?? item.tags}
                    sourceName={sourceNameFor(item, st)}
                    isPinned={item.is_pinned}
                    url={item.url}
                    aiEnrichment={buildAIEnrichment(item)}
                  />
                ))}
              </div>
            )}
          </CollapsibleSection>
        );
      })}

      <BlockAIAnalysisDrawer
        open={Boolean(selectedBlock)}
        title={selectedBlock?.title ?? ""}
        analysis={analysisMutation.data ?? null}
        isLoading={analysisMutation.isPending}
        error={analysisMutation.error ? analysisMutation.error.message : null}
        requiresLogin={requiresLogin}
        onClose={() => {
          setSelectedBlock(null);
          setRequiresLogin(false);
          analysisMutation.reset();
        }}
      />
    </div>
  );
}
