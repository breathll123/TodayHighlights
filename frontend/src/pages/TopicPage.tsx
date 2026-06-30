import { useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { usePageBlocks } from "@/hooks/use-page-blocks";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { GridRenderer } from "@/components/layout/GridRenderer";
import { AITopicSummary } from "@/components/layout/AITopicSummary";
import { MarketIndexBar } from "@/components/layout/MarketIndexBar";
import { fetchAITopicSummary, fetchTopics } from "@/api/client";
import { Button } from "@/components/ui/button";

const TOPIC_META: Record<string, { name: string; description: string }> = {
  "/topics/stocks": {
    name: "股票",
    description: "实时行情、快讯、公告、龙虎榜",
  },
  "/topics/football": {
    name: "足球",
    description: "比分、赛程、积分榜",
  },
  "/topics/ai": {
    name: "AI",
    description: "模型评测排行榜 · DataLearner",
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
  const queryClient = useQueryClient();
  const slug = topicSlug(location.pathname);
  const { data: topics = [] } = useQuery({
    queryKey: ["public-topics"],
    queryFn: fetchTopics,
    staleTime: 5 * 60 * 1000,
  });
  const topic = topics.find((item) => item.slug === slug);
  const meta = topic ? { name: topic.name, description: topicMeta(location.pathname).description } : topicMeta(location.pathname);

  const { data, isLoading, error, dataUpdatedAt } = usePageBlocks(location.pathname);

  const { data: aiSummary, isLoading: aiLoading } = useQuery({
    queryKey: ["ai-topic-summary", slug],
    queryFn: () => fetchAITopicSummary(slug!),
    enabled: slug === "stocks",
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <DashboardShell
      eyebrow="实时看板"
      title={`${meta.name}主题看板`}
      description={meta.description}
      activeTopic={meta.name}
      blockCount={data?.blocks?.length ?? 0}
      isLoading={isLoading}
    >
      {error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-5 flex items-start justify-between gap-4">
          <p className="text-sm text-destructive/90">
            {meta.name}主题加载失败，请检查后端服务或数据源状态。
          </p>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 h-8 gap-1.5 text-xs"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["page-blocks", location.pathname] })}
          >
            <RefreshCw className="h-3 w-3" />重试
          </Button>
        </div>
      ) : (
        <>
          {aiLoading && (
            <div className="mb-6 rounded-xl border border-primary/15 bg-muted/40 animate-pulse px-5 py-8">
              <div className="h-4 w-40 bg-muted-foreground/15 rounded mb-3" />
              <div className="space-y-2">
                <div className="h-3 w-full bg-muted-foreground/10 rounded" />
                <div className="h-3 w-3/4 bg-muted-foreground/10 rounded" />
                <div className="h-3 w-5/6 bg-muted-foreground/10 rounded" />
              </div>
            </div>
          )}
          {aiSummary && !aiLoading && <AITopicSummary summary={aiSummary} />}

          <GridRenderer blocks={data?.blocks ?? []} isLoading={isLoading} dataUpdatedAt={dataUpdatedAt} />
        </>
      )}
    </DashboardShell>
  );
}
