import { SIZE_PRESETS } from "@/lib/grid-utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onSelect: (col: number, row: number) => void;
  onClose: () => void;
}

export function SizePresetPicker({ open, onSelect, onClose }: Props) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader><DialogTitle>选择方块尺寸</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          {SIZE_PRESETS.map((p) => (
            <button
              key={p.label}
              className="border rounded-lg p-3 text-left hover:bg-muted transition-colors"
              onClick={() => { onSelect(p.col, p.row); onClose(); }}
            >
              <div className="text-xs text-muted-foreground mb-1">{p.icon}</div>
              <div className="text-sm font-medium">{p.label}</div>
              <div className="text-[10px] text-muted-foreground">{p.col}×{p.row}</div>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
