import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { fetchRawSources, type RawSourceOption } from "@/api/client";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Block } from "@/api/types";

const SORT_OPTIONS_MAP: Record<string, { value: string; label: string }[]> = {
  topic: [{ value: 'score', label: '热度' }, { value: 'created_at', label: '发布时间' }],
  raw: [{ value: 'published_at', label: '发布时间' }, { value: 'created_at', label: '入库时间' }],
  hot_stocks: [{ value: 'score', label: '热度' }, { value: 'percent', label: '涨跌幅' }],
  hot_events: [{ value: 'score', label: '热度' }],
  screener: [{ value: 'percent', label: '涨跌幅' }, { value: 'turnover_rate', label: '换手率' }],
  eastmoney_sectors: [{ value: 'percent', label: '涨跌幅' }],
  eastmoney_industry: [{ value: 'percent', label: '涨跌幅' }],
  eastmoney_indices: [{ value: 'percent', label: '涨跌幅' }],
  xueqiu_hot_cn: [{ value: 'score', label: '热度' }, { value: 'percent', label: '涨跌幅' }],
  xueqiu_hot_hk: [{ value: 'score', label: '热度' }, { value: 'percent', label: '涨跌幅' }],
  xueqiu_hot_us: [{ value: 'score', label: '热度' }, { value: 'percent', label: '涨跌幅' }],
  eastmoney_longhu: [{ value: 'net_amount', label: '净买入额' }, { value: 'buy_amount', label: '总成交额' }],
  eastmoney_capital_flow: [{ value: 'inflow', label: '主力净流入' }, { value: 'percent', label: '涨跌幅' }],
  eastmoney_announcements: [{ value: 'notice_date', label: '公告日期' }],
  tonghuashun_news: [{ value: 'published_at', label: '发布时间' }],
};

interface Props {
  open: boolean;
  block: Block | null;
  onSave: (data: Omit<Block, "id" | "created_at" | "updated_at">) => void;
  onClose: () => void;
}

const defaultForm: Omit<Block, "id" | "created_at" | "updated_at"> = {
  page_route: "/",
  title: "",
  source_type: "topic",
  source_config: {} as Record<string, unknown>,
  display_style: "card",
  display_count: 5,
  sort_by: "created_at",
  enabled: true,
  sort_order: 0,
  block_key: "",
  col_span: 1,
  row_span: 1,
  grid_x: 0,
  grid_y: 0,
  status: "draft",
};

export function BlockEditor({ open, block, onSave, onClose }: Props) {
  const [form, setForm] = useState(defaultForm);

  useEffect(() => {
    if (block) {
      setForm({
        page_route: block.page_route,
        title: block.title,
        source_type: block.source_type,
        source_config: block.source_config || {},
        display_style: block.display_style,
        display_count: block.display_count,
        sort_by: block.sort_by,
        enabled: block.enabled,
        sort_order: block.sort_order,
        block_key: block.block_key || "",
        col_span: block.col_span || 1,
        row_span: block.row_span || 1,
        grid_x: block.grid_x || 0,
        grid_y: block.grid_y || 0,
        status: block.status || "draft",
      });
    } else {
      setForm(defaultForm);
    }
  }, [block, open]);

  const [rawSources, setRawSources] = useState<RawSourceOption[]>([]);
  useEffect(() => {
    if (form.source_type === "raw") {
      fetchRawSources().then(setRawSources).catch(() => {});
    }
  }, [form.source_type]);

  const handleSave = () => {
    onSave(form);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{block ? "编辑区块" : "添加区块"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>标题</Label>
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="今日热股" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>所属页面</Label>
              <Select value={form.page_route} onValueChange={(v) => setForm({ ...form, page_route: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="/">摘要页</SelectItem>
                  <SelectItem value="/topics/stocks">股票页</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>数据来源</Label>
              <Select value={form.source_type} onValueChange={(v) => setForm({ ...form, source_type: v as Block["source_type"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>本地数据</SelectLabel>
                    <SelectItem value="topic">本地看点 (AI摘要)</SelectItem>
                    <SelectItem value="raw">原始数据</SelectItem>
                  </SelectGroup>
                  <SelectSeparator />
                  <SelectGroup>
                    <SelectLabel>雪球 (实时)</SelectLabel>
                    <SelectItem value="hot_stocks">热股榜</SelectItem>
                    <SelectItem value="hot_events">热门话题</SelectItem>
                    <SelectItem value="screener">涨跌幅榜</SelectItem>
                    <SelectItem value="xueqiu_hot_cn">沪深热度榜</SelectItem>
                    <SelectItem value="xueqiu_hot_hk">港股热度榜</SelectItem>
                    <SelectItem value="xueqiu_hot_us">美股热度榜</SelectItem>
                  </SelectGroup>
                  <SelectSeparator />
                  <SelectGroup>
                    <SelectLabel>东方财富 (实时)</SelectLabel>
                    <SelectItem value="eastmoney_sectors">概念板块</SelectItem>
                    <SelectItem value="eastmoney_industry">行业板块</SelectItem>
                    <SelectItem value="eastmoney_indices">指数行情</SelectItem>
                    <SelectItem value="eastmoney_longhu">龙虎榜</SelectItem>
                    <SelectItem value="eastmoney_capital_flow">主力资金流入</SelectItem>
                    <SelectItem value="eastmoney_announcements">A股公告</SelectItem>
                  </SelectGroup>
                  <SelectSeparator />
                  <SelectGroup>
                    <SelectLabel>同花顺 (实时)</SelectLabel>
                    <SelectItem value="tonghuashun_news">财经快讯</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </div>

          {form.source_type === "topic" && (
            <div className="space-y-2">
              <Label>话题 ID</Label>
              <Input type="number" value={String(form.source_config?.topic_id ?? 1)} onChange={(e) => setForm({ ...form, source_config: { topic_id: +e.target.value } })} />
            </div>
          )}
          {form.source_type === "raw" && (
            <div className="space-y-2">
              <Label>数据源</Label>
              <Select value={String(form.source_config?.source_id ?? "")} onValueChange={(v) => setForm({ ...form, source_config: { source_id: +v } })}>
                <SelectTrigger><SelectValue placeholder="选择数据源..." /></SelectTrigger>
                <SelectContent>
                  {rawSources.map((s: RawSourceOption) => (
                    <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {form.source_type === "hot_stocks" && (
            <div className="space-y-2">
              <Label>榜单类型</Label>
              <Select value={String(form.source_config?.type ?? 10)} onValueChange={(v) => setForm({ ...form, source_config: { type: +v } })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">A股热度榜</SelectItem>
                  <SelectItem value="11">美股热度榜</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {form.source_type === "screener" && (
            <div className="space-y-2">
              <Label>排序字段</Label>
              <Select value={String(form.source_config?.order_by ?? "percent")} onValueChange={(v) => setForm({ ...form, source_config: { order_by: v, size: 20 } })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="percent">涨跌幅</SelectItem>
                  <SelectItem value="turnover_rate">换手率</SelectItem>
                  <SelectItem value="volume">成交量</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>展示条数 ({form.display_count})</Label>
              <Slider value={[form.display_count]} onValueChange={([v]) => setForm({ ...form, display_count: v })} min={1} max={20} step={1} />
            </div>
            <div className="space-y-2">
              <Label>排序方式</Label>
              <Select value={form.sort_by} onValueChange={(v) => setForm({ ...form, sort_by: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(SORT_OPTIONS_MAP[form.source_type] || SORT_OPTIONS_MAP.topic).map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>展示形式</Label>
              <Select value={form.display_style} onValueChange={(v) => setForm({ ...form, display_style: v as Block["display_style"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="card">卡片</SelectItem>
                  <SelectItem value="list">列表</SelectItem>
                  <SelectItem value="timeline">时间线</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={form.enabled} onCheckedChange={(v) => setForm({ ...form, enabled: v })} />
            <Label>启用</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSave}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
