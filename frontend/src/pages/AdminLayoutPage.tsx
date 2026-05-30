import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Eye, Pencil, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CanvasEditor } from "@/components/admin/CanvasEditor";
import { SizePresetPicker } from "@/components/admin/SizePresetPicker";
import { BlockConfigPanel } from "@/components/admin/BlockConfigPanel";
import { findAvailablePosition } from "@/lib/grid-utils";
import { safeUUID } from "@/lib/utils";
import { fetchBlocks, createBlock, updateBlock, deleteBlock, publishPage } from "@/api/client";
import type { Block } from "@/api/types";
import { toast } from "sonner";

const pages = [
  { route: "/", label: "摘要页" },
  { route: "/topics/stocks", label: "股票页" },
];

export function AdminLayoutPage() {
  const queryClient = useQueryClient();
  const [activePage, setActivePage] = useState("/");
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [sizePickerOpen, setSizePickerOpen] = useState(false);
  const [configBlock, setConfigBlock] = useState<Block | null>(null);
  const [configForm, setConfigForm] = useState<Omit<Block, "id" | "created_at" | "updated_at"> | null>(null);

  const { data: allBlocks = [], isLoading } = useQuery({ queryKey: ["blocks"], queryFn: fetchBlocks });

  const draftBlocks = allBlocks
    .filter((b: Block) => b.page_route === activePage && b.status === "draft")
    .sort((a: Block, b: Block) => a.grid_y - b.grid_y || a.grid_x - b.grid_x);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["blocks"] });

  const createMut = useMutation({
    mutationFn: createBlock,
    onSuccess: () => { invalidate(); toast.success("方块已添加"); },
    onError: (err: Error) => toast.error(`添加失败: ${err.message}`),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Block> }) => updateBlock(id, data),
    onSuccess: () => { invalidate(); setConfigBlock(null); toast.success("已保存"); },
    onError: (err: Error) => toast.error(`保存失败: ${err.message}`),
  });
  const deleteMut = useMutation({
    mutationFn: deleteBlock,
    onSuccess: () => { invalidate(); toast.success("已删除"); },
    onError: (err: Error) => toast.error(`删除失败: ${err.message}`),
  });
  const publishMut = useMutation({
    mutationFn: publishPage,
    onSuccess: () => { invalidate(); toast.success("已发布"); },
    onError: (err: Error) => toast.error(`发布失败: ${err.message}`),
  });

  const handleAddBlock = (col: number, row: number) => {
    const pos = findAvailablePosition(draftBlocks, col, row);
    createMut.mutate({
      page_route: activePage, title: "新方块", source_type: "topic",
      source_config: { topic_id: 1 }, block_key: safeUUID(),
      col_span: col, row_span: row, grid_x: pos.x, grid_y: pos.y,
      display_style: "card", display_count: 5, sort_by: "created_at",
      enabled: true, sort_order: 0, status: "draft",
    } as any);
  };

  const handleLayoutChange = async (blocks: Block[]) => {
    for (const b of blocks) {
      try {
        await updateBlock(b.id, { grid_x: b.grid_x, grid_y: b.grid_y, col_span: b.col_span, row_span: b.row_span });
      } catch (err: any) {
        toast.error(`保存位置失败: ${err.message}`);
        return;
      }
    }
    invalidate();
  };

  const handleEditBlock = (block: Block) => {
    setConfigBlock(block);
    setConfigForm({
      page_route: block.page_route,
      title: block.title,
      source_type: block.source_type,
      source_config: { ...(block.source_config || {}) },
      display_style: block.display_style,
      display_count: block.display_count,
      sort_by: block.sort_by,
      enabled: block.enabled,
      sort_order: block.sort_order,
      block_key: block.block_key,
      col_span: block.col_span,
      row_span: block.row_span,
      grid_x: block.grid_x,
      grid_y: block.grid_y,
      status: block.status,
    });
  };

  const handleSaveConfig = () => {
    if (configBlock && configForm) {
      updateMut.mutate({ id: configBlock.id, data: configForm as Partial<Block> });
    }
  };

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      <div className="flex-1 overflow-auto p-6 max-w-[calc(100vw-20rem)]">
        <div className="flex items-center justify-between mb-6">
          <Tabs value={activePage} onValueChange={setActivePage}>
            <TabsList>
              {pages.map((p) => (
                <TabsTrigger key={p.route} value={p.route}>{p.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2">
            <Button variant={mode === "edit" ? "default" : "outline"} size="sm" onClick={() => setMode("edit")}>
              <Pencil className="w-4 h-4 mr-1" />编辑
            </Button>
            <Button variant={mode === "preview" ? "default" : "outline"} size="sm" onClick={() => setMode("preview")}>
              <Eye className="w-4 h-4 mr-1" />预览
            </Button>
            <Button size="sm" onClick={() => publishMut.mutate(activePage)} disabled={publishMut.isPending}>
              <Send className="w-4 h-4 mr-1" />发布
            </Button>
          </div>
        </div>

        {mode === "edit" && (
          <div className="space-y-4">
            <CanvasEditor
              blocks={draftBlocks}
              onLayoutChange={handleLayoutChange}
              onEdit={handleEditBlock}
              onDelete={(id) => { if (confirm("确定删除？")) deleteMut.mutate(id); }}
            />
            <Button variant="outline" onClick={() => setSizePickerOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />添加方块
            </Button>
            <SizePresetPicker
              open={sizePickerOpen}
              onSelect={handleAddBlock}
              onClose={() => setSizePickerOpen(false)}
            />
          </div>
        )}

        {mode === "preview" && (
          <div className="grid grid-cols-4 gap-3">
            {draftBlocks.map((b: Block) => (
              <div
                key={b.id}
                className="bg-card border rounded-xl p-4"
                style={{ gridColumn: `span ${b.col_span}`, gridRow: `span ${b.row_span}` }}
              >
                <div className="font-medium text-sm mb-1">{b.title}</div>
                <div className="text-xs text-muted-foreground">
                  {b.source_type} · {b.display_count}条 · {b.display_style}
                </div>
              </div>
            ))}
            {draftBlocks.length === 0 && (
              <div className="col-span-4 text-center py-12 text-muted-foreground text-sm">
                暂无方块，点击"添加方块"开始
              </div>
            )}
          </div>
        )}
      </div>

      {configBlock && configForm && (
        <BlockConfigPanel
          form={configForm}
          onChange={setConfigForm}
          onSave={handleSaveConfig}
          onCancel={() => setConfigBlock(null)}
        />
      )}
    </div>
  );
}
