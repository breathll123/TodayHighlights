import { GripHorizontal, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Block } from "@/api/types";

interface Props {
  block: Block;
  onEdit: () => void;
  onDelete: () => void;
}

export function CanvasBlock({ block, onEdit, onDelete }: Props) {
  return (
    <div className="h-full bg-card border rounded-xl shadow-sm overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b drag-handle cursor-grab active:cursor-grabbing">
        <div className="flex items-center gap-2 min-w-0">
          <GripHorizontal className="w-4 h-4 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium truncate">{block.title}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onEdit(); }}>
            <Pencil className="w-3 h-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onDelete(); }}>
            <Trash2 className="w-3 h-3 text-destructive" />
          </Button>
        </div>
      </div>
      <div className="flex-1 p-3 text-xs text-muted-foreground flex items-center justify-center">
        {block.display_count}条 · {block.display_style === "list" ? "列表" : "卡片"}
      </div>
    </div>
  );
}
