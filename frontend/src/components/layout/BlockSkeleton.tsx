export function BlockSkeleton({ colSpan = 1, rowSpan = 1 }: { colSpan?: number; rowSpan?: number }) {
  return (
    <div
      className="min-h-[138px] animate-pulse rounded-xl border border-border/70 bg-card/75 p-5 shadow-sm"
      style={{ gridColumn: `span ${colSpan}`, gridRow: `span ${rowSpan}` }}
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="h-6 w-14 rounded-full bg-muted" />
      </div>
      <div className="mb-3 h-4 w-2/3 rounded bg-muted" />
      <div className="mb-2 h-3 w-full rounded bg-muted" />
      <div className="mb-4 h-3 w-4/5 rounded bg-muted" />
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded-full bg-muted" />
        <div className="h-5 w-20 rounded-full bg-muted" />
      </div>
    </div>
  );
}
