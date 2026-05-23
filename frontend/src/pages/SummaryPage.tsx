import { usePageBlocks } from "@/hooks/use-page-blocks";
import { GridRenderer } from "@/components/layout/GridRenderer";

export function SummaryPage() {
  const { data, isLoading, error } = usePageBlocks("/");
  if (error) return <div className="text-center py-12 text-destructive">加载失败</div>;
  return <GridRenderer blocks={data?.blocks ?? []} isLoading={isLoading} />;
}
