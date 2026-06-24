import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, Check, Languages, Loader2, RotateCcw, Save } from "lucide-react";
import { toast } from "sonner";
import { fetchSkillsPrompts, setSkillsPrompts, type SkillsPrompts } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type PromptKey = keyof SkillsPrompts;

const promptMeta: Record<PromptKey, { label: string; shortLabel: string; description: string; Icon: typeof Braces }> = {
  classify_prompt: {
    label: "内容识别 Prompt",
    shortLabel: "内容识别",
    description: "判断采集内容是否符合 Skills 排行收录标准。修改后重新采集或解析时生效。",
    Icon: Braces,
  },
  translate_prompt: {
    label: "中文整理 Prompt",
    shortLabel: "中文整理",
    description: "将保留内容的原始描述整理为统一、简洁的中文说明。",
    Icon: Languages,
  },
};

const emptyPrompts: SkillsPrompts = { classify_prompt: "", translate_prompt: "" };

export function SkillsPromptsSection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["skills-prompts"], queryFn: fetchSkillsPrompts });
  const [drafts, setDrafts] = useState<SkillsPrompts | null>(null);
  const [activePrompt, setActivePrompt] = useState<PromptKey>("classify_prompt");
  const values = drafts ?? data ?? emptyPrompts;
  const isDirty = Boolean(data && (values.classify_prompt !== data.classify_prompt || values.translate_prompt !== data.translate_prompt));
  const activeMeta = promptMeta[activePrompt];
  const ActiveIcon = activeMeta.Icon;

  const saveMutation = useMutation({
    mutationFn: () => setSkillsPrompts(values),
    onSuccess: (saved) => {
      queryClient.setQueryData(["skills-prompts"], saved);
      setDrafts(saved);
      toast.success("数据清洗 Prompt 已保存，下次采集或重新解析时生效");
    },
    onError: (error: Error) => toast.error(`保存失败：${error.message}`),
  });

  const updateActivePrompt = (value: string) => {
    setDrafts({ ...values, [activePrompt]: value });
  };

  const resetActivePrompt = () => {
    if (!data) return;
    setDrafts({ ...values, [activePrompt]: data[activePrompt] });
  };

  return (
    <section className="overflow-hidden rounded-lg border border-border/80 bg-card" aria-labelledby="cleaning-prompts-title">
      <div className="border-b border-border/70 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 id="cleaning-prompts-title" className="text-base font-semibold text-foreground">Skills 数据清洗</h2>
            <p className="mt-1 text-sm text-muted-foreground">在内容进入排行数据前完成识别和中文整理，不影响页面区块分析模板。</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {isDirty ? (
              <span className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />有未保存修改
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />已保存
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid min-h-[470px] lg:grid-cols-[240px_minmax(0,1fr)]">
        <nav className="border-b border-border/70 bg-muted/15 p-3 lg:border-b-0 lg:border-r" aria-label="数据清洗 Prompt 类型">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
            {(Object.keys(promptMeta) as PromptKey[]).map((key) => {
              const meta = promptMeta[key];
              const Icon = meta.Icon;
              const active = activePrompt === key;
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setActivePrompt(key)}
                  className={cn(
                    "flex min-h-16 cursor-pointer items-start gap-3 rounded-md border px-3 py-3 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary/35 bg-primary/[0.08] text-foreground"
                      : "border-transparent text-muted-foreground hover:border-border hover:bg-background/60 hover:text-foreground",
                  )}
                >
                  <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md", active ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground")}>
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{meta.shortLabel}</span>
                    <span className="mt-0.5 block text-xs leading-5">{key === "classify_prompt" ? "筛选有效内容" : "统一中文描述"}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </nav>

        <div className="flex min-w-0 flex-col p-4 sm:p-5">
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <ActiveIcon className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold text-foreground">{activeMeta.label}</h3>
            </div>
            <p className="mt-1.5 max-w-3xl text-xs leading-5 text-muted-foreground">{activeMeta.description}</p>
          </div>

          <Label htmlFor="skills-prompt-editor" className="sr-only">{activeMeta.label}</Label>
          <div className="relative flex-1">
            {isLoading ? (
              <div className="flex min-h-80 items-center justify-center rounded-md border border-border/70 bg-muted/15 text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />加载 Prompt...
              </div>
            ) : (
              <textarea
                id="skills-prompt-editor"
                aria-label={activeMeta.label}
                className="min-h-80 h-full w-full resize-y rounded-md border border-input bg-background px-4 py-3 font-mono text-[13px] leading-6 outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                value={values[activePrompt]}
                onChange={(event) => updateActivePrompt(event.target.value)}
                spellCheck={false}
              />
            )}
          </div>

          <div className="mt-4 flex flex-col-reverse gap-3 border-t border-border/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted-foreground">保存会同时提交两类数据清洗 Prompt。</p>
            <div className="flex gap-2 self-end sm:self-auto">
              <Button type="button" variant="outline" size="sm" className="h-11 gap-2 sm:h-9" onClick={resetActivePrompt} disabled={!data || values[activePrompt] === data[activePrompt] || saveMutation.isPending}>
                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />撤销当前修改
              </Button>
              <Button type="button" size="sm" className="h-11 gap-2 sm:h-9" onClick={() => saveMutation.mutate()} disabled={!isDirty || saveMutation.isPending}>
                {saveMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Save className="h-3.5 w-3.5" aria-hidden="true" />}
                {saveMutation.isPending ? "保存中..." : "保存全部"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
