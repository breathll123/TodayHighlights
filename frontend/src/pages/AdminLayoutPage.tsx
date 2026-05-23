import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Eye, Pencil, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CanvasEditor } from "@/components/admin/CanvasEditor";
import { SizePresetPicker } from "@/components/admin/SizePresetPicker";
import { BlockConfigPanel } from "@/components/admin/BlockConfigPanel";
import { findAvailablePosition } from "@/lib/grid-utils";
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

  const createMut = useMutation({
    mutationFn: createBlock,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["blocks"] }),
    onError: (err: Error) => toast.error(err.message),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Block> }) => updateBlock(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blocks"] });
      setConfigBlock(null);
      toast.success("已保存");
    },
    onError: (err: Error) => toast.error(err.message),
  });
  const deleteMut = useMutation({
    mutationFn: deleteBlock,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["blocks"] }),
  });
  const publishMut = useMutation({
    mutationFn: publishPage,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["blocks"] }); toast.success("已发布"); },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleAddBlock = (col: number, row: number) => {
    const pos = findAvailablePosition(draftBlocks, col, row);
    createMut.mutate({
      page_route: activePage,
      title: "新方块",
      source_type: "topic",
      source_config: { topic_id: 1 },
      block_key: crypto.randomUUID(),
      col_span: col,
      row_span: row,
      grid_x: pos.x,
      grid_y: pos.y,
      display_style: "card",
      display_count: 5,
      sort_by: "created_at",
      enabled: true,
      sort_order: 0,
      status: "draft",
    } as any);
  };

  const handleLayoutChange = (blocks: Block[]) => {
    blocks.forEach((b) => {
      updateBlock(b.id, { grid_x: b.grid_x, grid_y: b.grid_y, col_span: b.col_span, row_span: b.row_span });
    });
    queryClient.invalidateQueries({ queryKey: ["blocks"] });
  };

  const handleEditBlock = (block: Block) => {
    setConfigBlock(block);
    setConfigForm({
      page_route: block.page_route,
      title: block.title,
      source_type: block.source_type,
      source_config: block.source_config || {},
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
      updateMut.mutate({ id: configBlock.id, data: configForm });
    }
  };

  if (isLoading) return <div className="p-6 text-muted-foreground">加载中...</div>;

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Main area */}
      <div className="flex-1 overflow-auto p-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <Tabs value={activePage} onValueChange={setActivePage}>
            <TabsList>
              {pages.map((p) => (
                <TabsTrigger key={p.route} value={p.route}>{p.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2">
            <Button
              variant={mode === "edit" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("edit")}
            >
              <Pencil className="w-4 h-4 mr-1" />编辑
            </Button>
            <Button
              variant={mode === "preview" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("preview")}
            >
              <Eye className="w-4 h-4 mr-1" />预览
            </Button>
            <Button size="sm" onClick={() => publishMut.mutate(activePage)} disabled={publishMut.isPending}>
              <Send className="w-4 h-4 mr-1" />发布
            </Button>
          </div>
        </div>

        {/* Edit mode */}
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

        {/* Preview mode */}
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
              <div className="col-span-4 text-center py-12 text-muted-foreground text-sm">暂无方块，点击"添加方块"开始</div>
            )}
          </div>
        )}
      </div>

      {/* Config panel */}
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
