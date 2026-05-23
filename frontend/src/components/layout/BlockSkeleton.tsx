export function BlockSkeleton({ colSpan = 1, rowSpan = 1 }: { colSpan?: number; rowSpan?: number }) {
  return (
    <div
      className="animate-pulse bg-card rounded-xl border p-5"
      style={{ gridColumn: `span ${colSpan}`, gridRow: `span ${rowSpan}` }}
    >
      <div className="h-4 bg-muted rounded w-2/3 mb-3" />
      <div className="h-3 bg-muted rounded w-full mb-2" />
      <div className="h-3 bg-muted rounded w-4/5 mb-2" />
      <div className="h-3 bg-muted rounded w-1/2" />
    </div>
  );
}
