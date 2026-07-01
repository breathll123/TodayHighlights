import { AnimatePresence, motion } from "framer-motion";
import { Check, Copy, Loader2, X } from "lucide-react";
import { useState } from "react";
import type { AITokenUsageDetail } from "@/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button variant="ghost" size="icon" className="h-7 w-7 absolute top-2 right-2 opacity-60 hover:opacity-100" onClick={handleCopy} aria-label="复制">
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </Button>
  );
}

function CodeBlock({ label, text, variant = "default" }: { label: string; text: string; variant?: "default" | "response" }) {
  if (!text) return null;
  let formatted = text;
  if (variant === "response") {
    try { formatted = JSON.stringify(JSON.parse(text), null, 2); } catch { /* not JSON, show raw */ }
  }
  return (
    <div className="space-y-1.5">
      <h4 className="text-xs font-medium text-muted-foreground">{label}</h4>
      <div className={cn(
        "relative rounded-lg border p-3 max-h-64 overflow-auto",
        variant === "response" ? "bg-emerald-50/50 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800" : "bg-muted/50 border-border"
      )}>
        <CopyButton text={formatted} />
        <pre className={cn("text-xs leading-relaxed whitespace-pre-wrap break-all pr-8 font-mono", variant === "response" ? "text-emerald-900 dark:text-emerald-100" : "text-foreground/80")}>
          {formatted}
        </pre>
      </div>
    </div>
  );
}

const USAGE_TYPE_LABELS: Record<string, string> = {
  block_analysis: "方块 AI 分析",
  game_description: "游戏简介翻译",
};

function usageTypeLabel(type: string): string {
  return USAGE_TYPE_LABELS[type] ?? type;
}

interface Props {
  open: boolean;
  detail: AITokenUsageDetail | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

export function AIUsageDetailDrawer({ open, detail, isLoading, error, onClose }: Props) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
            onClick={onClose}
          />
          {/* Panel */}
          <motion.aside
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-x-0 bottom-0 z-50 max-h-[82dvh] overflow-hidden rounded-t-2xl border bg-background shadow-2xl md:inset-x-auto md:right-4 md:top-4 md:h-[calc(100dvh-2rem)] md:w-[520px] md:max-h-none md:rounded-xl"
            aria-label="AI 请求详情"
          >
            <div className="flex h-full flex-col">
              {/* Header */}
              <header className="flex items-center justify-between border-b px-5 py-3.5 shrink-0">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold truncate">AI 请求详情</h3>
                  {detail && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {detail.model_name} · {usageTypeLabel(detail.usage_type)}
                      {detail.topic ? ` · ${detail.topic}` : ""}
                    </p>
                  )}
                </div>
                <Button variant="ghost" size="icon" aria-label="关闭" onClick={onClose}>
                  <X className="h-4 w-4" />
                </Button>
              </header>

              {/* Body */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {isLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : error ? (
                  <p className="text-sm text-destructive bg-destructive/5 rounded-lg p-3">{error}</p>
                ) : detail ? (
                  <>
                    {/* Token stats */}
                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <p className="text-[10px] text-muted-foreground uppercase">Prompt</p>
                        <p className="text-lg font-bold tabular-nums">{detail.prompt_tokens.toLocaleString()}</p>
                        <p className="text-[10px] text-muted-foreground">tokens</p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <p className="text-[10px] text-muted-foreground uppercase">Completion</p>
                        <p className="text-lg font-bold tabular-nums">{detail.completion_tokens.toLocaleString()}</p>
                        <p className="text-[10px] text-muted-foreground">tokens</p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <p className="text-[10px] text-muted-foreground uppercase">Total</p>
                        <p className="text-lg font-bold tabular-nums">{detail.total_tokens.toLocaleString()}</p>
                        <p className="text-[10px] text-muted-foreground">{detail.estimated ? "估算" : "实际"}</p>
                      </div>
                    </div>

                    {/* Content blocks */}
                    {detail.prompt_text || detail.completion_text ? (
                      <>
                        <CodeBlock label="System Prompt + User Prompt" text={detail.prompt_text} />
                        <CodeBlock label="AI 返回" text={detail.completion_text} variant="response" />
                      </>
                    ) : (
                      <p className="rounded-lg border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
                        这条历史记录只保存了 Token 统计，没有保存请求与返回正文。重新触发对应任务后，新记录会显示完整详情。
                      </p>
                    )}
                  </>
                ) : null}
              </div>
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
