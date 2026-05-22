import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, GripVertical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { BlockEditor } from "@/components/admin/BlockEditor";
import { fetchBlocks, createBlock, updateBlock, deleteBlock } from "@/api/client";
import type { Block } from "@/api/types";
import { toast } from "sonner";

const pages = [
  { route: "/", label: "摘要页" },
  { route: "/topics/stocks", label: "股票页" },
];

export function AdminLayoutPage() {
  const queryClient = useQueryClient();
  const [activePage, setActivePage] = useState("/");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingBlock, setEditingBlock] = useState<Block | null>(null);

  const { data: blocks = [], isLoading } = useQuery({
    queryKey: ["blocks"],
    queryFn: fetchBlocks,
  });

  const pageBlocks = blocks
    .filter((b: Block) => b.page_route === activePage)
    .sort((a: Block, b: Block) => a.sort_order - b.sort_order);

  const createMut = useMutation({
    mutationFn: createBlock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blocks"] });
      setEditorOpen(false);
      toast.success("区块已添加");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Block> }) => updateBlock(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blocks"] });
      setEditorOpen(false);
      setEditingBlock(null);
      toast.success("区块已更新");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMut = useMutation({
    mutationFn: deleteBlock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blocks"] });
      toast.success("区块已删除");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">页面布局</h1>
        <Button
          onClick={() => {
            setEditingBlock(null);
            setEditorOpen(true);
          }}
        >
          <Plus className="w-4 h-4 mr-2" />
          添加区块
        </Button>
      </div>

      <Tabs value={activePage} onValueChange={setActivePage}>
        <TabsList>
          {pages.map((p) => (
            <TabsTrigger key={p.route} value={p.route}>
              {p.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中...</p>
      ) : pageBlocks.length === 0 ? (
        <p className="text-sm text-muted-foreground py-12 text-center">
          暂无区块，点击上方按钮添加
        </p>
      ) : (
        <div className="space-y-3">
          {pageBlocks.map((block: Block) => (
            <Card key={block.id} className={!block.enabled ? "opacity-50" : ""}>
              <CardContent className="flex items-center gap-4 p-4">
                <GripVertical className="w-5 h-5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{block.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {block.source_type} · {block.display_count}条 · 按
                    {block.sort_by === "score" ? "热度" : "时间"}排序
                  </div>
                </div>
                <Switch
                  checked={block.enabled}
                  onCheckedChange={(v) =>
                    updateMut.mutate({ id: block.id, data: { enabled: v } })
                  }
                />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setEditingBlock(block);
                    setEditorOpen(true);
                  }}
                >
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    if (confirm("确定删除？")) deleteMut.mutate(block.id);
                  }}
                >
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <BlockEditor
        open={editorOpen}
        block={editingBlock}
        onClose={() => {
          setEditorOpen(false);
          setEditingBlock(null);
        }}
        onSave={(data) => {
          if (editingBlock) {
            updateMut.mutate({ id: editingBlock.id, data });
          } else {
            createMut.mutate(data as any);
          }
        }}
      />
    </div>
  );
}
