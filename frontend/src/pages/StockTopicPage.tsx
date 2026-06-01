import { useLocation } from "react-router-dom";
import { usePageBlocks } from "@/hooks/use-page-blocks";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { GridRenderer } from "@/components/layout/GridRenderer";

const TOPIC_META: Record<string, { name: string; description: string }> = {
  "/topics/stocks": {
    name: "股票",
    description: "聚合股票主题下的实时来源、热点列表、公告、龙虎榜和 AI 生成看点。",
  },
  "/topics/football": {
    name: "足球",
    description: "全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。",
  },
};

export function StockTopicPage() {
  const location = useLocation();
  const meta = TOPIC_META[location.pathname] ?? { name: "主题", description: "" };

  const { data, dataUpdatedAt, isLoading, error } = usePageBlocks(location.pathname);

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
        <GridRenderer blocks={data?.blocks ?? []} isLoading={isLoading} dataUpdatedAt={dataUpdatedAt} />
      )}
    </DashboardShell>
  );
}
