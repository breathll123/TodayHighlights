import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BrainCircuit, CalendarClock, ChartNoAxesCombined, Newspaper, Trophy } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { BlockCard } from "./BlockCard";
import { BlockSkeleton } from "./BlockSkeleton";
import { CompactTable } from "./CompactTable";
import { MatchCards } from "./MatchCards";
import { MatchList } from "./MatchList";
import { NewsTimeline } from "./NewsTimeline";
import { StandingsTable } from "./StandingsTable";
import { LeaderboardTable } from "./LeaderboardTable";
import { LonghuList } from "./LonghuList";
import { ArtificialAnalysisRanking } from "./ArtificialAnalysisRanking";
import { MarketIndexBar } from "./MarketIndexBar";
import { SectionHeading } from "./SectionHeading";
import { BlockAIAnalysisDrawer } from "./BlockAIAnalysisDrawer";
import { CollapsibleSection } from "./CollapsibleSection";
import { FIELD_DEFS, resolveDisplayFieldKeys } from "@/lib/field-defs";
import { generateBlockAIAnalysis } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import type { AIItemEnhancement } from "@/api/types";

const easeOutQuint: [number, number, number, number] = [0.22, 1, 0.36, 1];
const MAX_VISIBLE_ANALYSIS_ITEMS = 200;

interface AnalysisScope {
  data: any[];
  label?: string;
}

const VISIBLE_ANALYSIS_FIELDS = [
  "id", "title", "name", "summary", "content", "source", "source_type", "published_at", "created_at",
  "url", "rank", "score", "percent", "value", "tags", "tags_json", "related_symbols_json", "symbols",
  "team", "league", "group", "season", "updated", "gp", "pts", "wdl", "gf", "ga", "gd",
  "status", "minute", "start_time", "team_a", "team_b", "score_a", "score_b",
  "model", "creator", "subtitle", "region", "net_amount", "reason",
] as const;

function compactVisibleAnalysisData(data: any[]): any[] {
  if (!Array.isArray(data)) return [];
  return data.slice(0, MAX_VISIBLE_ANALYSIS_ITEMS).map((item) => {
    if (!item || typeof item !== "object") return {};
    const compact: Record<string, unknown> = {};
    for (const key of VISIBLE_ANALYSIS_FIELDS) {
      const value = item[key];
      if (value === undefined || value === null || value === "") continue;
      compact[key] = value;
    }
    return compact;
  }).filter((item) => Object.keys(item).length > 0);
}

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
  eastmoney_indices: "新浪财经",
  tonghuashun_news: "同花顺",
  qiumiwu_matches: "球迷屋",
  qiumiwu_fixtures: "球迷屋",
  qiumiwu_standings: "球迷屋",
  qiumiwu_schedule: "球迷屋",
  datalearner_leaderboard: "DataLearner",
  datalearner_aa_index: "DataLearner",
  aihot_news: "AI HOT",
  artificial_analysis_ranking: "Artificial Analysis",
  market_index_trends: "东方财富",
};

const SOURCE_URLS: Record<string, string> = {
  xueqiu: "https://xueqiu.com/",
  eastmoney: "https://www.eastmoney.com/",
  sina: "https://finance.sina.com.cn/",
  tonghuashun: "https://www.10jqka.com.cn/",
  qiumiwu: "https://www.qiumiwu.com/",
  datalearner: "https://www.datalearner.com/",
  aihot: "https://aihot.virxact.com/",
  artificial_analysis: "https://artificialanalysis.ai/",
};

function sourceUrlFor(sourceType: string): string | undefined {
  if (sourceType.startsWith("xueqiu")) return SOURCE_URLS.xueqiu;
  if (sourceType === "eastmoney_indices") return SOURCE_URLS.sina;
  if (sourceType.startsWith("eastmoney")) return SOURCE_URLS.eastmoney;
  if (sourceType.startsWith("tonghuashun")) return SOURCE_URLS.tonghuashun;
  if (sourceType.startsWith("qiumiwu")) return SOURCE_URLS.qiumiwu;
  if (sourceType.startsWith("datalearner")) return SOURCE_URLS.datalearner;
  if (sourceType.startsWith("aihot")) return SOURCE_URLS.aihot;
  if (sourceType.startsWith("artificial_analysis")) return SOURCE_URLS.artificial_analysis;
  if (sourceType.startsWith("market_index")) return SOURCE_URLS.eastmoney;
  return undefined;
}

export function sourceNameFor(item: any, sourceType: string): string {
  return SOURCE_NAMES[item.source ?? sourceType] ?? "今日看点";
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
    net_amount: item.net_amount,
    reason: item.reason,
    url: item.url,
  };
}

function AAIndexBlock({
  block,
  displayFields,
  onAnalysisDataChange,
}: {
  block: any;
  displayFields: any[];
  onAnalysisDataChange?: (data: any[], scopeLabel: string) => void;
}) {
  const [region, setRegion] = useState<"global" | "china">("global");
  const allData = block.data || [];
  const filtered = useMemo(
    () => allData.filter((item: any) => item.region === region || (!item.region && region === "global")),
    [allData, region],
  );
  const first = filtered[0];
  const regionLabel = region === "china" ? "国产排名" : "全球排名";

  useEffect(() => {
    onAnalysisDataChange?.(filtered, regionLabel);
  }, [filtered, onAnalysisDataChange, regionLabel]);

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
  const location = useLocation();
  const [selectedBlock, setSelectedBlock] = useState<any | null>(null);
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [analysisScopes, setAnalysisScopes] = useState<Record<number, AnalysisScope>>({});
  const analysisMutation = useMutation({
    mutationFn: generateBlockAIAnalysis,
  });

  const closeAnalysisDrawer = () => {
    setSelectedBlock(null);
    setRequiresLogin(false);
    analysisMutation.reset();
  };

  useEffect(() => {
    closeAnalysisDrawer();
  }, [location.pathname]);

  const setBlockAnalysisScope = useCallback((blockId: number, data: any[], label?: string) => {
    setAnalysisScopes((current) => {
      const previous = current[blockId];
      if (previous?.data === data && previous?.label === label) return current;
      return { ...current, [blockId]: { data, label } };
    });
  }, []);

  const buildAnalysisPayload = (block: any) => {
    const scope = analysisScopes[block.id];
    const visibleData = compactVisibleAnalysisData(scope?.data ?? block.data ?? []);
    return {
      page_route: block.page_route,
      block_id: block.id,
      visible_data: visibleData,
      scope_label: scope?.label,
    };
  };

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
      {blocks.map((block, blockIdx) => {
        const st = block.source_type as string;
        const allFields = FIELD_DEFS[st] || [];
        const cfgFields: string[] | undefined = block.source_config?.display_fields;
        const selectedKeys = resolveDisplayFieldKeys(st, cfgFields);
        const displayFields = allFields.filter((f) => selectedKeys.includes(f.key));

        return (
          <motion.div
            key={block.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.25,
              ease: easeOutQuint,
              delay: Math.min(blockIdx, 8) * 0.025,
            }}
            style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
          >
          <CollapsibleSection
            key={block.id}
            blockId={block.id}
            className="space-y-0"
            style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
            heading={
              <SectionHeading
                icon={sectionIcon(st)}
                title={block.title}
                dataUpdatedAt={block.data_updated_at}
                sourceName={st === "topic" || st === "raw" ? undefined : SOURCE_NAMES[st] ?? undefined}
                sourceUrl={st === "artificial_analysis_ranking" ? undefined : sourceUrlFor(st)}
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
                      analysisMutation.mutate(buildAnalysisPayload(block));
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
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} onAnalysisDataChange={(visible, label) => setBlockAnalysisScope(block.id, visible, label)} />
            ) : block.source_type === "qiumiwu_fixtures" ? (
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} defaultFilter="fixture" onAnalysisDataChange={(visible, label) => setBlockAnalysisScope(block.id, visible, label)} />
            ) : block.source_type === "qiumiwu_schedule" ? (
              <MatchList data={block.data} dataUpdatedAt={dataUpdatedAt} defaultFilter="fixture" onAnalysisDataChange={(visible, label) => setBlockAnalysisScope(block.id, visible, label)} />
            ) : block.source_type === "qiumiwu_standings" ? (
              <StandingsTable data={block.data} onAnalysisDataChange={(visible, label) => setBlockAnalysisScope(block.id, visible, label)} />
            ) : block.source_type === "datalearner_aa_index" ? (
              <AAIndexBlock block={block} displayFields={displayFields} onAnalysisDataChange={(visible, label) => setBlockAnalysisScope(block.id, visible, label)} />
            ) : block.source_type === "datalearner_leaderboard" ? (
              <LeaderboardTable data={block.data} />
            ) : block.source_type === "market_index_trends" ? (
              <MarketIndexBar data={block.data} />
            ) : block.source_type === "artificial_analysis_ranking" ? (
              <ArtificialAnalysisRanking data={block.data} meta={block.meta} />
            ) : block.source_type === "eastmoney_longhu" ? (
              <LonghuList data={block.data} fields={displayFields} />
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
          </motion.div>
        );
      })}

      <BlockAIAnalysisDrawer
        open={Boolean(selectedBlock)}
        title={selectedBlock?.title ?? ""}
        analysis={analysisMutation.data ?? null}
        isLoading={analysisMutation.isPending}
        error={analysisMutation.error ? analysisMutation.error.message : null}
        requiresLogin={requiresLogin}
        onClose={closeAnalysisDrawer}
      />
    </div>
  );
}
