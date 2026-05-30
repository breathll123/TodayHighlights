import { useCallback } from "react";
import GridLayout, { WidthProvider } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import { noCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { CanvasBlock } from "./CanvasBlock";
import { hasCollision, clampSize } from "@/lib/grid-utils";
import type { Block } from "@/api/types";
import { toast } from "sonner";

const ResponsiveGridLayout = WidthProvider(GridLayout);

interface Props {
  blocks: Block[];
  onLayoutChange: (blocks: Block[]) => void;
  onEdit: (block: Block) => void;
  onDelete: (id: number) => void;
}

export function CanvasEditor({ blocks, onLayoutChange, onEdit, onDelete }: Props) {
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
      const moved = blocks.find((b) => String(b.id) === newItem.i);
      if (!moved) return;
      const candidate: Block = { ...moved, grid_x: newItem.x, grid_y: newItem.y, col_span: newItem.w, row_span: newItem.h };
      const others = blocks.filter((b) => String(b.id) !== newItem.i);
      if (others.some((b) => hasCollision(candidate, b))) {
        toast.error("该位置已有其他组件");
        onLayoutChange([...blocks]);
        return;
      }
      const updated = blocks.map((b) => (String(b.id) === newItem.i ? candidate : b));
      onLayoutChange(updated);
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
      const resized = blocks.find((b) => String(b.id) === newItem.i);
      if (!resized) return;
      const candidate: Block = { ...resized, grid_x: newItem.x, grid_y: newItem.y, col_span: col, row_span: row };
      const others = blocks.filter((b) => String(b.id) !== newItem.i);
      if (others.some((b) => hasCollision(candidate, b))) {
        toast.error("该位置已有其他组件");
        onLayoutChange([...blocks]);
        return;
      }
      const updated = blocks.map((b) => (String(b.id) === newItem.i ? candidate : b));
      onLayoutChange(updated);
    },
    [blocks, onLayoutChange],
  );

  return (
    <ResponsiveGridLayout
      className="layout"
      layout={layout}
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
    </ResponsiveGridLayout>
  );
}

