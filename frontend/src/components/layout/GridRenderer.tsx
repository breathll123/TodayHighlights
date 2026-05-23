import { BlockCard } from "./BlockCard";
import { BlockListItem } from "./BlockListItem";
import { BlockSkeleton } from "./BlockSkeleton";

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
      <div className="text-center py-16 text-muted-foreground">
        <p className="text-lg mb-2">暂无内容</p>
        <p className="text-sm">管理员正在准备精彩内容</p>
      </div>
    );
  }

  return (
    <div className="page-grid">
      {blocks.map((block) => (
        <section
          key={block.id}
          className="space-y-3"
          style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
        >
          <h2 className="text-sm font-bold text-muted-foreground tracking-wide uppercase">{block.title}</h2>
          <div className={block.display_style === "list" ? "border rounded-lg bg-card" : "space-y-2"}>
            {block.data?.length === 0 && (
              <div className="bg-card border rounded-xl p-6 text-center text-sm text-muted-foreground">
                暂无数据
              </div>
            )}
            {block.data?.map((item: any, i: number) => {
              const key = item.id ?? i;
              const props = {
                title: item.title ?? item.name ?? "",
                summary: item.summary ?? item.content ?? "",
                tags: item.tags_json ?? item.tags,
                score: item.score ?? item.value,
                isPinned: item.is_pinned,
                symbols: item.related_symbols_json ?? item.symbols ?? (item.code ? [item.code] : undefined),
                url: item.url,
              };
              return block.display_style === "list" ? <BlockListItem key={key} {...props} /> : <BlockCard key={key} {...props} />;
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
