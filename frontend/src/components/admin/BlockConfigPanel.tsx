import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { SIZE_PRESETS } from "@/lib/grid-utils";
import { FIELD_DEFS, resolveDisplayFieldKeys } from "@/lib/field-defs";
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
  { value: "xueqiu_hot_cn", label: "沪深热度榜" },
  { value: "xueqiu_hot_hk", label: "港股热度榜" },
  { value: "xueqiu_hot_us", label: "美股热度榜" },
];

const SOURCE_TYPE_OPTIONS_EM: { value: Block["source_type"]; label: string }[] = [
  { value: "eastmoney_sectors", label: "概念板块" },
  { value: "eastmoney_industry", label: "行业板块" },
  { value: "eastmoney_indices", label: "指数行情" },
  { value: "eastmoney_longhu", label: "龙虎榜" },
  { value: "eastmoney_capital_flow", label: "主力资金流入" },
  { value: "eastmoney_announcements", label: "A股公告" },
  { value: "market_index_trends", label: "指数行情图" },
];

const SOURCE_TYPE_OPTIONS_THS: { value: Block["source_type"]; label: string }[] = [
  { value: "tonghuashun_news", label: "财经快讯" },
];

const SOURCE_TYPE_OPTIONS_QMW: { value: Block["source_type"]; label: string }[] = [
  { value: "qiumiwu_matches", label: "足球比赛" },
  { value: "qiumiwu_fixtures", label: "足球赛程" },
  { value: "qiumiwu_schedule", label: "赛事赛程表" },
  { value: "qiumiwu_standings", label: "联赛积分榜" },
];

const SOURCE_TYPE_OPTIONS_AI: { value: Block["source_type"]; label: string }[] = [
  { value: "datalearner_aa_index", label: "AI模型智能指数排行榜" },
  { value: "artificial_analysis_ranking", label: "Artificial Analysis 排行榜" },
  { value: "aihot_news", label: "AI 资讯快讯" },
  { value: "github_skills", label: "GitHub Skills 排行" },
];

const SOURCE_TYPE_OPTIONS_GAME: { value: Block["source_type"]; label: string }[] = [
  { value: "game_top_sellers", label: "Steam 热门游戏榜" },
  { value: "game_most_played", label: "Steam 在线热玩榜" },
  { value: "game_specials", label: "Steam 折扣特惠" },
  { value: "game_new_releases", label: "Steam 新游动态" },
];

const THEME_OPTIONS = [
  { value: "default", label: "默认" },
  { value: "arcade", label: "街机（游戏）" },
];

const ARTIFICIAL_ANALYSIS_DATASETS = [
  { value: "language_global", label: "全球大语言模型" },
  { value: "language_china", label: "中国大语言模型" },
  { value: "text_to_image", label: "文生图" },
  { value: "text_to_video", label: "文生视频" },
  { value: "image_to_video", label: "图生视频" },
  { value: "text_to_speech", label: "文本转语音" },
  { value: "speech_to_text", label: "语音转文本" },
] as const;

const DISPLAY_STYLE_OPTIONS = [
  { value: "card", label: "卡片" },
  { value: "list", label: "列表" },
  { value: "timeline", label: "时间线" },
  { value: "schedule", label: "赛程表" },
] as const;

export function BlockConfigPanel({ form, onChange, onSave, onCancel }: Props) {
  const update = <K extends keyof BlockForm>(key: K, value: BlockForm[K]) => {
    onChange({ ...form, [key]: value });
  };

  const [rawSources, setRawSources] = useState<RawSourceOption[]>([]);
  useEffect(() => {
    if (form.source_type === "raw") {
      fetchRawSources().then(setRawSources).catch(() => {});
    }
  }, [form.source_type]);

  const allFields = FIELD_DEFS[form.source_type] || [];
  const configuredFields = form.source_config?.display_fields;
  const selectedFields = resolveDisplayFieldKeys(form.source_type, configuredFields);
  const numericFields = allFields.filter((f) => f.type === "number");

  const toggleField = (key: string) => {
    const next = selectedFields.includes(key)
      ? selectedFields.filter((k) => k !== key)
      : [...selectedFields, key];
    onChange({ ...form, source_config: { ...form.source_config, display_fields: next } });
  };

  return (
    <div className="w-80 max-w-[88vw] border-l bg-card h-full overflow-y-auto p-4 space-y-4 max-md:fixed max-md:inset-y-0 max-md:right-0 max-md:z-50 max-md:shadow-2xl">
      <h3 className="font-semibold text-sm">方块配置</h3>

      {/* Title */}
      <div className="space-y-1.5">
        <Label className="text-xs">标题</Label>
        <Input value={form.title} onChange={(e) => update("title", e.target.value)} className="h-8 text-xs" />
      </div>

      {/* Source Type */}
      <div className="space-y-1.5">
        <Label className="text-xs">数据来源</Label>
        <Select value={form.source_type} onValueChange={(v) => update("source_type", v as Block["source_type"])}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">本地数据</SelectLabel>
              {SOURCE_TYPE_OPTIONS_DB.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">雪球 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_XQ.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">东方财富 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_EM.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">同花顺 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_THS.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">球迷屋 (实时)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_QMW.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">DataLearner (AI)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_AI.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel className="text-[10px] text-muted-foreground">游戏 (Steam)</SelectLabel>
              {SOURCE_TYPE_OPTIONS_GAME.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {/* Source-specific config */}
      {form.source_type === "artificial_analysis_ranking" && (
        <div className="space-y-2">
          <Label className="text-xs">排名数据（可多选）</Label>
          <div className="space-y-1">
            {ARTIFICIAL_ANALYSIS_DATASETS.map((ds) => {
              const cfg = form.source_config as Record<string, unknown> | undefined;
              const raw = cfg?.dataset_keys as string[] | undefined;
              const legacy = cfg?.dataset_key as string | undefined;
              const selected: string[] = raw ?? (legacy ? [legacy] : ["language_global"]);
              const checked = selected.includes(ds.value);
              return (
                <label key={ds.value} className="flex items-center gap-2 cursor-pointer py-0.5">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      const next = checked
                        ? selected.filter((k) => k !== ds.value)
                        : [...selected, ds.value];
                      update("source_config", {
                        dataset_keys: next.length > 0 ? next : ["language_global"],
                        display_fields: ["title", "subtitle", "release", "score"],
                      });
                    }}
                    className="h-3.5 w-3.5 rounded border-border accent-primary"
                  />
                  <span className="text-xs">{ds.label}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
      {form.source_type === "topic" && (
        <div className="space-y-1.5">
          <Label className="text-xs">话题 ID</Label>
          <Input type="number" value={String(form.source_config?.topic_id ?? 1)} onChange={(e) => update("source_config", { topic_id: +e.target.value })} className="h-8 text-xs" />
        </div>
      )}
      {form.source_type === "raw" && (
        <div className="space-y-1.5">
          <Label className="text-xs">数据源</Label>
          <Select value={String(form.source_config?.source_id ?? "")} onValueChange={(v) => update("source_config", { source_id: +v })}>
            <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="选择数据源..." /></SelectTrigger>
            <SelectContent>
              {rawSources.map((s) => <SelectItem key={s.id} value={String(s.id)} className="text-xs">{s.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}
      {form.source_type === "screener" && (
        <div className="space-y-1.5">
          <Label className="text-xs">排序字段</Label>
          <Select value={String(form.source_config?.order_by ?? "percent")} onValueChange={(v) => update("source_config", { order_by: v })}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="percent" className="text-xs">涨跌幅</SelectItem>
              <SelectItem value="turnover_rate" className="text-xs">换手率</SelectItem>
              <SelectItem value="volume" className="text-xs">成交量</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {form.source_type === "qiumiwu_schedule" && (
        <div className="space-y-1.5">
          <Label className="text-xs">选择赛事</Label>
          <Select value={String(form.source_config?.competition ?? "男足世界杯")} onValueChange={(v) => update("source_config", { ...form.source_config, competition: v })}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="男足世界杯" className="text-xs">男足世界杯</SelectItem>
              <SelectItem value="女足世界杯" className="text-xs">女足世界杯</SelectItem>
              <SelectItem value="欧洲杯" className="text-xs">欧洲杯</SelectItem>
              <SelectItem value="美洲杯" className="text-xs">美洲杯</SelectItem>
              <SelectItem value="亚洲杯" className="text-xs">亚洲杯</SelectItem>
              <SelectItem value="欧冠" className="text-xs">欧冠</SelectItem>
              <SelectItem value="欧联杯" className="text-xs">欧联杯</SelectItem>
              <SelectItem value="英超" className="text-xs">英超</SelectItem>
              <SelectItem value="西甲" className="text-xs">西甲</SelectItem>
              <SelectItem value="意甲" className="text-xs">意甲</SelectItem>
              <SelectItem value="德甲" className="text-xs">德甲</SelectItem>
              <SelectItem value="法甲" className="text-xs">法甲</SelectItem>
              <SelectItem value="中超" className="text-xs">中超</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Display Count — hidden for standings (always shows all leagues) */}
      {form.source_type !== "qiumiwu_standings" && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label className="text-xs">展示条数</Label>
            <Input
              type="number" min={1} max={200}
              value={form.display_count}
              onChange={(e) => { const v = Math.max(1, Math.min(200, +e.target.value || 5)); update("display_count", v); }}
              className="h-7 w-14 text-xs text-center"
            />
          </div>
          <Slider value={[form.display_count]} onValueChange={([v]) => update("display_count", v)} min={1} max={50} step={1} />
        </div>
      )}

      {/* Display Style — hidden for AA index (list only) */}
      {form.source_type !== "datalearner_aa_index" && form.source_type !== "artificial_analysis_ranking" && form.source_type !== "market_index_trends" && form.source_type !== "github_skills" && form.source_type !== "game_top_sellers" && form.source_type !== "game_most_played" && form.source_type !== "game_specials" && form.source_type !== "game_new_releases" && (
        <div className="space-y-1.5">
          <Label className="text-xs">展示样式</Label>
          <Select value={form.display_style} onValueChange={(v) => update("display_style", v as Block["display_style"])}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {DISPLAY_STYLE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* 主题选择 */}
      <div className="space-y-1.5">
        <Label className="text-xs">主题</Label>
        <Select value={form.theme ?? "default"} onValueChange={(v) => update("theme", v)}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            {THEME_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Display Fields */}
      {allFields.length > 0 && (
        <div className="space-y-1.5">
          <Label className="text-xs">展示字段</Label>
          <div className="flex flex-wrap gap-1.5">
            {allFields.map((f) => (
              <button
                key={f.key}
                className={cn(
                  "text-[11px] px-2 py-1 rounded border transition-colors",
                  selectedFields.includes(f.key)
                    ? "bg-primary/10 border-primary text-primary"
                    : "border-muted-foreground/20 text-muted-foreground hover:bg-muted"
                )}
                onClick={() => toggleField(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sort By (numeric fields only) */}
      {numericFields.length > 0 && (
        <div className="space-y-1.5">
          <Label className="text-xs">排序方式</Label>
          <Select value={form.sort_by} onValueChange={(v) => update("sort_by", v)}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {numericFields.map((f) => <SelectItem key={f.key} value={f.key} className="text-xs">{f.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Size Presets */}
      <div className="space-y-1.5">
        <Label className="text-xs">预设尺寸</Label>
        <div className="grid grid-cols-3 gap-1">
          {SIZE_PRESETS.map((p) => (
            <button key={p.label}
              className={cn("border rounded p-1.5 text-center text-[10px] leading-tight transition-colors", form.col_span === p.col && form.row_span === p.row ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted text-muted-foreground")}
              onClick={() => onChange({ ...form, col_span: p.col, row_span: p.row })}
            >
              <div>{p.icon}</div><div>{p.label}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Enabled */}
      <div className="flex items-center justify-between py-1">
        <Label className="text-xs">启用</Label>
        <Switch checked={form.enabled} onCheckedChange={(v) => update("enabled", v)} />
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button size="sm" className="flex-1" onClick={onSave}>保存</Button>
        <Button size="sm" variant="outline" className="flex-1" onClick={onCancel}>取消</Button>
      </div>
    </div>
  );
}
