import { usePageBlocks } from "@/hooks/use-page-blocks";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { GridRenderer } from "@/components/layout/GridRenderer";

export function SummaryPage() {
  const { data, isLoading, error } = usePageBlocks("/");
  return (
    <DashboardShell
      eyebrow="Multi-topic Intelligence"
      title="全局实时信息聚合"
      description="DataFlow 将不同垂直领域的来源、快讯、榜单和 AI 看点组织成统一的信息工作台。股票是第一批主题，AI 与足球将以相同结构接入。"
      activeTopic="全局"
      blockCount={data?.blocks?.length ?? 0}
      isLoading={isLoading}
    >
      {error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-sm text-destructive">
          内容加载失败，请检查后端服务或页面发布状态。
        </div>
      ) : (
        <GridRenderer blocks={data?.blocks ?? []} isLoading={isLoading} />
      )}
    </DashboardShell>
  );
}
