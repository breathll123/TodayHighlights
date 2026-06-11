import { useCallback, type RefObject } from "react";
import GridLayout, { useContainerWidth } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import { noCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { CanvasBlock } from "./CanvasBlock";
import { clampSize, reflowBlocks } from "@/lib/grid-utils";
import type { Block } from "@/api/types";
import { toast } from "sonner";

interface Props {
  blocks: Block[];
  onLayoutChange: (blocks: Block[]) => void;
  onEdit: (block: Block) => void;
  onDelete: (id: number) => void;
}

export function CanvasEditor({ blocks, onLayoutChange, onEdit, onDelete }: Props) {
  const { width, containerRef, mounted } = useContainerWidth();
  const layout: Layout = blocks.map((b) => ({
    i: String(b.id),
    x: b.grid_x,
    y: b.grid_y,
    w: b.col_span,
    h: b.row_span,
    minW: 1,
    maxW: 4,
    minH: 1,
    maxH: 6,
  }));

  const handleDragStop = useCallback(
    (_layout: Layout, _oldItem: LayoutItem | null, newItem: LayoutItem | null) => {
      if (!newItem) return;
      onLayoutChange(reflowBlocks(blocks, Number(newItem.i), {
        grid_x: newItem.x,
        grid_y: newItem.y,
        col_span: newItem.w,
        row_span: newItem.h,
      }));
    },
    [blocks, onLayoutChange],
  );

  const handleResizeStop = useCallback(
    (_layout: Layout, _oldItem: LayoutItem | null, newItem: LayoutItem | null) => {
      if (!newItem) return;
      const { col, row } = clampSize(newItem.w, newItem.h);
      if (newItem.x + col > 4) {
        toast.error("方块不能超出画布边界");
        onLayoutChange([...blocks]);
        return;
      }
      onLayoutChange(reflowBlocks(blocks, Number(newItem.i), {
        grid_x: newItem.x,
        grid_y: newItem.y,
        col_span: col,
        row_span: row,
      }));
    },
    [blocks, onLayoutChange],
  );

  return (
    <div ref={containerRef as RefObject<HTMLDivElement>}>
    {mounted && width > 0 ? (
    <GridLayout
      className="layout"
      layout={layout}
      width={width}
      gridConfig={{ cols: 4, rowHeight: 140, margin: [12, 12] }}
      dragConfig={{ handle: ".drag-handle" }}
      resizeConfig={{ enabled: true }}
      compactor={noCompactor}
      onDragStop={handleDragStop}
      onResizeStop={handleResizeStop}
    >
      {blocks.map((b) => (
        <div key={String(b.id)}>
          <CanvasBlock block={b} onEdit={() => onEdit(b)} onDelete={() => onDelete(b.id)} />
        </div>
      ))}
    </GridLayout>
    ) : (
      <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">加载编辑器中...</div>
    )}
    </div>
  );
}
