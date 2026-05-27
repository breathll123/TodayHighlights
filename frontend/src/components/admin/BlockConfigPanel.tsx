import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { SIZE_PRESETS } from "@/lib/grid-utils";
import type { Block } from "@/api/types";
import { fetchRawSources, type RawSourceOption } from "@/api/client";
import { cn } from "@/lib/utils";

type BlockForm = Omit<Block, "id" | "created_at" | "updated_at">;

interface Props {
  form: BlockForm;
  onChange: (f: BlockForm) => void;
  onSave: () => void;
  onCancel: () => void;
}

const SOURCE_TYPE_OPTIONS_DB: { value: Block["source_type"]; label: string }[] = [
  { value: "topic", label: "本地看点 (AI摘要)" },
  { value: "raw", label: "原始数据" },
];

const SOURCE_TYPE_OPTIONS_XQ: { value: Block["source_type"]; label: string }[] = [
  { value: "hot_stocks", label: "热门股票" },
  { value: "hot_events", label: "热门话题" },
  { value: "screener", label: "涨跌幅榜" },
];

const SOURCE_TYPE_OPTIONS_THS: { value: Block["source_type"]; label: string }[] = [
  { value: "tonghuashun_news", label: "财经快讯" },
];

const SOURCE_TYPE_OPTIONS_EM: { value: Block["source_type"]; label: string }[] = [
  { value: "eastmoney_sectors", label: "概念板块" },
  { value: "eastmoney_industry", label: "行业板块" },
  { value: "eastmoney_indices", label: "指数行情" },
  { value: "eastmoney_gainers", label: "A股涨幅榜" },
  { value: "eastmoney_losers", label: "A股跌幅榜" },
  { value: "eastmoney_capital_flow", label: "主力资金流入" },
  { value: "eastmoney_announcements", label: "A股公告" },
];

const DISPLAY_STYLE_OPTIONS: { value: Block["display_style"]; label: string }[] = [
  { value: "card", label: "卡片" },
  { value: "list", label: "列表" },
  { value: "timeline", label: "时间线" },
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

  const [rawSources, setRawSources] = useState<RawSourceOption[]>([]);
  useEffect(() => {
    if (form.source_type === "raw") {
      fetchRawSources().then(setRawSources).catch(() => {});
    }
  }, [form.source_type]);

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
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">本地数据</SelectLabel>
              {SOURCE_TYPE_OPTIONS_DB.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">雪球 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_XQ.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">东方财富 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_EM.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">同花顺 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_THS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {/* Source-specific Config */}
      {form.source_type === "topic" && (
        <div className="space-y-1.5">
          <Label className="text-xs">话题 ID</Label>
          <Input
            type="number"
            value={String(form.source_config?.topic_id ?? 1)}
            onChange={(e) => update("source_config", { topic_id: +e.target.value })}
            className="h-8 text-xs"
          />
        </div>
      )}
      {form.source_type === "raw" && (
        <div className="space-y-1.5">
          <Label className="text-xs">数据源</Label>
          <Select
            value={String(form.source_config?.source_id ?? "")}
            onValueChange={(v) => update("source_config", { source_id: +v })}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder="选择数据源..." />
            </SelectTrigger>
            <SelectContent>
              {rawSources.map((s) => (
                <SelectItem key={s.id} value={String(s.id)} className="text-xs">
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {form.source_type === "hot_stocks" && (
        <div className="space-y-1.5">
          <Label className="text-xs">榜单类型</Label>
          <Select
            value={String(form.source_config?.type ?? 10)}
            onValueChange={(v) => update("source_config", { type: +v })}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10" className="text-xs">A股热度榜</SelectItem>
              <SelectItem value="11" className="text-xs">美股热度榜</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      {form.source_type === "screener" && (
        <div className="space-y-1.5">
          <Label className="text-xs">排序字段</Label>
          <Select
            value={String(form.source_config?.order_by ?? "percent")}
            onValueChange={(v) => update("source_config", { order_by: v })}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="percent" className="text-xs">涨跌幅</SelectItem>
              <SelectItem value="turnover_rate" className="text-xs">换手率</SelectItem>
              <SelectItem value="volume" className="text-xs">成交量</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

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
