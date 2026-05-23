import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { SIZE_PRESETS } from "@/lib/grid-utils";
import type { Block } from "@/api/types";
import { cn } from "@/lib/utils";

type BlockForm = Omit<Block, "id" | "created_at" | "updated_at">;

interface Props {
  form: BlockForm;
  onChange: (f: BlockForm) => void;
  onSave: () => void;
  onCancel: () => void;
}

const SOURCE_TYPE_OPTIONS: { value: Block["source_type"]; label: string }[] = [
  { value: "topic", label: "话题" },
  { value: "search", label: "搜索" },
  { value: "hot_stocks", label: "热门股票" },
  { value: "hot_events", label: "热门事件" },
  { value: "screener", label: "筛选器" },
];

const DISPLAY_STYLE_OPTIONS: { value: Block["display_style"]; label: string }[] = [
  { value: "card", label: "卡片" },
  { value: "list", label: "列表" },
];

const SORT_OPTIONS: { value: Block["sort_by"]; label: string }[] = [
  { value: "score", label: "评分" },
  { value: "created_at", label: "创建时间" },
];

export function BlockConfigPanel({ form, onChange, onSave, onCancel }: Props) {
  const update = <K extends keyof BlockForm>(key: K, value: BlockForm[K]) => {
    onChange({ ...form, [key]: value });
  };

  const handlePresetSize = (col: number, row: number) => {
    onChange({ ...form, col_span: col, row_span: row });
  };

  return (
    <div className="w-80 border-l bg-card h-full overflow-y-auto p-4 space-y-4">
      <h3 className="font-semibold text-sm">方块配置</h3>

      {/* Block Key (read-only) */}
      {form.block_key && (
        <div className="space-y-1.5">
          <Label className="text-xs">标识符</Label>
          <Input value={form.block_key} disabled className="h-8 text-xs" />
        </div>
      )}

      {/* Title */}
      <div className="space-y-1.5">
        <Label className="text-xs">标题</Label>
        <Input
          value={form.title}
          onChange={(e) => update("title", e.target.value)}
          className="h-8 text-xs"
        />
      </div>

      {/* Source Type */}
      <div className="space-y-1.5">
        <Label className="text-xs">数据来源</Label>
        <Select
          value={form.source_type}
          onValueChange={(v) => update("source_type", v as Block["source_type"])}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SOURCE_TYPE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-xs">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Display Count */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">展示条数</Label>
          <span className="text-xs text-muted-foreground">{form.display_count}</span>
        </div>
        <Slider
          value={[form.display_count]}
          onValueChange={([v]) => update("display_count", v)}
          min={1}
          max={20}
          step={1}
        />
      </div>

      {/* Display Style */}
      <div className="space-y-1.5">
        <Label className="text-xs">展示样式</Label>
        <Select
          value={form.display_style}
          onValueChange={(v) => update("display_style", v as Block["display_style"])}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DISPLAY_STYLE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-xs">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Sort By */}
      <div className="space-y-1.5">
        <Label className="text-xs">排序方式</Label>
        <Select
          value={form.sort_by}
          onValueChange={(v) => update("sort_by", v as Block["sort_by"])}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-xs">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Size Presets */}
      <div className="space-y-1.5">
        <Label className="text-xs">预设尺寸</Label>
        <div className="grid grid-cols-3 gap-1">
          {SIZE_PRESETS.map((p) => (
            <button
              key={p.label}
              className={cn(
                "border rounded p-1.5 text-center text-[10px] leading-tight transition-colors",
                form.col_span === p.col && form.row_span === p.row
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted text-muted-foreground"
              )}
              onClick={() => handlePresetSize(p.col, p.row)}
            >
              <div>{p.icon}</div>
              <div>{p.label}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Enabled */}
      <div className="flex items-center justify-between py-1">
        <Label className="text-xs">启用</Label>
        <Switch
          checked={form.enabled}
          onCheckedChange={(v) => update("enabled", v)}
        />
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 pt-2">
        <Button size="sm" className="flex-1" onClick={onSave}>
          保存
        </Button>
        <Button size="sm" variant="outline" className="flex-1" onClick={onCancel}>
          取消
        </Button>
      </div>
    </div>
  );
}
