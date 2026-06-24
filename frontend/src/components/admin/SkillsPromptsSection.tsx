import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchSkillsPrompts, setSkillsPrompts } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TEXTAREA_CLS =
  "min-h-[160px] w-full rounded-md border border-input bg-background/70 px-3 py-2 font-mono text-xs leading-relaxed outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring";

/**
 * GitHub Skills 解析提示词 — kept visually and storage-wise separate from the
 * topic content templates below (these are full system prompts in app_settings,
 * not the content-analysis fragments).
 */
export function SkillsPromptsSection() {
  const { data } = useQuery({ queryKey: ["skills-prompts"], queryFn: fetchSkillsPrompts });
  const [classify, setClassify] = useState("");
  const [translate, setTranslate] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (data && !dirty) {
      setClassify(data.classify_prompt);
      setTranslate(data.translate_prompt);
    }
  }, [data, dirty]);

  const saveMut = useMutation({
    mutationFn: () => setSkillsPrompts({ classify_prompt: classify, translate_prompt: translate }),
    onSuccess: () => { setDirty(false); toast.success("已保存，下次采集/重新解析将用新提示词重判"); },
    onError: (err: Error) => toast.error(`保存失败: ${err.message}`),
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Skills 解析提示词</CardTitle>
        <p className="text-xs text-muted-foreground">
          用于 GitHub Skills 排行的 AI 分类与描述翻译。改了分类提示词后，下次「采集」或「重新解析」会自动重判全部仓库。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label className="text-xs">分类提示词（判定是否为 skill）</Label>
          <textarea
            className={TEXTAREA_CLS}
            value={classify}
            onChange={(e) => { setClassify(e.target.value); setDirty(true); }}
            spellCheck={false}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">翻译提示词（描述译成中文）</Label>
          <textarea
            className={TEXTAREA_CLS}
            value={translate}
            onChange={(e) => { setTranslate(e.target.value); setDirty(true); }}
            spellCheck={false}
          />
        </div>
        <div className="flex justify-end">
          <Button size="sm" onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !dirty}>
            保存提示词
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
