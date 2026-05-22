import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
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
      });
    } else {
      setForm(defaultForm);
    }
  }, [block, open]);

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
                  <SelectItem value="topic">本地看点</SelectItem>
                  <SelectItem value="hot_stocks">热股榜</SelectItem>
                  <SelectItem value="hot_events">热门话题</SelectItem>
                  <SelectItem value="screener">活跃股票</SelectItem>
                  <SelectItem value="search">关键词搜索</SelectItem>
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
          {form.source_type === "search" && (
            <div className="space-y-2">
              <Label>搜索关键词</Label>
              <Input value={String(form.source_config?.query ?? "")} onChange={(e) => setForm({ ...form, source_config: { query: e.target.value, count: 20 } })} placeholder="芯片" />
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

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>展示条数 ({form.display_count})</Label>
              <Slider value={[form.display_count]} onValueChange={([v]) => setForm({ ...form, display_count: v })} min={1} max={20} step={1} />
            </div>
            <div className="space-y-2">
              <Label>排序方式</Label>
              <Select value={form.sort_by} onValueChange={(v) => setForm({ ...form, sort_by: v as Block["sort_by"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="score">热度</SelectItem>
                  <SelectItem value="created_at">时间</SelectItem>
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
