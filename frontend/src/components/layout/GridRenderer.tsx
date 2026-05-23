import { BlockCard } from "./BlockCard";
import { BlockSkeleton } from "./BlockSkeleton";
import { CompactTable } from "./CompactTable";

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
          className="space-y-2"
          style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}
        >
          <h2 className="text-xs font-bold text-muted-foreground tracking-wide uppercase">{block.title}</h2>

          {block.data?.length === 0 ? (
            <div className="bg-card border rounded-xl p-6 text-center text-sm text-muted-foreground">暂无数据</div>
          ) : block.display_style === "list" ? (
            <div className="border rounded-lg bg-card">
              <CompactTable
                data={block.data.map((item: any) => ({
                  id: item.id,
                  title: item.title ?? item.name ?? "",
                  score: item.score ?? item.value,
                  percent: item.percent,
                  url: item.url,
                }))}
                columns={[
                  { key: "title", label: "名称" },
                  { key: "percent", label: "涨跌" },
                  { key: "score", label: "热度" },
                ]}
              />
            </div>
          ) : (
            <div className="space-y-2">
              {block.data.map((item: any, i: number) => (
                <BlockCard
                  key={item.id ?? i}
                  title={item.title ?? item.name ?? ""}
                  summary={item.summary ?? item.content ?? ""}
                  tags={item.tags_json ?? item.tags}
                  score={item.score ?? item.value}
                  isPinned={item.is_pinned}
                  symbols={item.related_symbols_json ?? item.symbols ?? (item.code ? [item.code] : undefined)}
                  url={item.url}
                />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
