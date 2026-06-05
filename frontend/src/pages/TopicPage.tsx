import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { usePageBlocks } from "@/hooks/use-page-blocks";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { GridRenderer } from "@/components/layout/GridRenderer";
import { AITopicSummary } from "@/components/layout/AITopicSummary";
import { fetchAITopicSummary } from "@/api/client";

const TOPIC_META: Record<string, { name: string; description: string }> = {
  "/topics/stocks": {
    name: "股票",
    description: "聚合股票主题下的实时来源、热点列表、公告、龙虎榜和 AI 生成看点。",
  },
  "/topics/football": {
    name: "足球",
    description: "全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。",
  },
  "/topics/ai": {
    name: "AI",
    description: "AI 大模型性能评测排行榜，DataLearner 数据源。覆盖 HLE、ARC-AGI-2、SWE-bench 等基准。",
  },
};

function topicMeta(pathname: string) {
  return TOPIC_META[pathname] ?? {
    name: pathname.replace("/topics/", ""),
    description: "",
  };
}

function topicSlug(pathname: string): string | null {
  const match = pathname.match(/^\/topics\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

export function TopicPage() {
  const location = useLocation();
  const meta = topicMeta(location.pathname);
  const slug = topicSlug(location.pathname);

  const { data, isLoading, error } = usePageBlocks(location.pathname);

  // Only fetch AI summary for stocks topic
  const { data: aiSummary, isLoading: aiLoading } = useQuery({
    queryKey: ["ai-topic-summary", slug],
    queryFn: () => fetchAITopicSummary(slug!),
    enabled: slug === "stocks",
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <DashboardShell
      eyebrow="Topic Workspace"
      title={`${meta.name}主题看板`}
      description={meta.description}
      activeTopic={meta.name}
      blockCount={data?.blocks?.length ?? 0}
      isLoading={isLoading}
    >
      {error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-sm text-destructive">
          {meta.name}主题加载失败，请检查后端服务、数据源或发布状态。
        </div>
      ) : (
        <>
          {/* AI Summary for stocks topic */}
          {aiLoading && (
            <div className="mb-6 rounded-xl border border-primary/10 bg-primary/5 animate-pulse px-5 py-8">
              <div className="h-4 w-40 bg-primary/10 rounded mb-3" />
              <div className="space-y-2">
                <div className="h-3 w-full bg-primary/5 rounded" />
                <div className="h-3 w-3/4 bg-primary/5 rounded" />
                <div className="h-3 w-5/6 bg-primary/5 rounded" />
              </div>
            </div>
          )}
          {aiSummary && !aiLoading && <AITopicSummary summary={aiSummary} />}

          <GridRenderer blocks={data?.blocks ?? []} isLoading={isLoading} />
        </>
      )}
    </DashboardShell>
  );
}
