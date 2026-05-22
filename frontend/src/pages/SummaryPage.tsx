import { usePageBlocks } from "@/hooks/use-page-blocks";
import { BlockCard } from "@/components/layout/BlockCard";
import { Separator } from "@/components/ui/separator";

export function SummaryPage() {
  const { data, isLoading, error } = usePageBlocks("/");

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;
  if (error) return <div className="text-center py-12 text-destructive">加载失败</div>;

  const blocks = data?.blocks ?? [];

  if (blocks.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-lg mb-2">暂无内容</p>
        <p className="text-sm">请先在管理后台配置页面区块</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {blocks.map((block) => (
        <section key={block.id}>
          <h2 className="text-lg font-bold mb-4">{block.title}</h2>
          <div className="space-y-3">
            {block.data?.length === 0 && <p className="text-sm text-muted-foreground">暂无数据</p>}
            {block.data?.map((item: any, i: number) => (
              <BlockCard
                key={item.id ?? i}
                title={item.title ?? item.name ?? ""}
                summary={item.summary ?? item.content ?? ""}
                tags={item.tags_json ?? item.tags}
                score={item.score ?? item.value}
                isPinned={item.is_pinned}
                symbols={item.related_symbols_json ?? (item.code ? [item.code] : undefined)}
              />
            ))}
          </div>
          <Separator className="mt-6" />
        </section>
      ))}
    </div>
  );
}
