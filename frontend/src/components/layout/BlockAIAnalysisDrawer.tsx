import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, BrainCircuit, ChevronDown, Loader2, LogIn, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { BlockAIAnalysis } from "@/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function BlockAIAnalysisDrawer({
  open,
  title,
  analysis,
  isLoading,
  error,
  requiresLogin,
  onClose,
}: {
  open: boolean;
  title: string;
  analysis: BlockAIAnalysis | null;
  isLoading: boolean;
  error: string | null;
  requiresLogin: boolean;
  onClose: () => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 24 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-x-0 bottom-0 z-50 max-h-[82dvh] rounded-t-2xl border bg-background shadow-2xl md:inset-x-auto md:right-4 md:top-4 md:h-[calc(100dvh-2rem)] md:w-[420px] md:max-h-none md:rounded-xl"
          aria-label="AI 分析"
        >
          <div className="flex h-full flex-col">
            <header className="flex items-center justify-between border-b px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <BrainCircuit className="h-4 w-4 text-primary" aria-hidden="true" />
                  <span className="truncate">{title}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">区块级 AI 分析</p>
              </div>
              <Button variant="ghost" size="icon" aria-label="关闭 AI 分析" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              {requiresLogin ? (
                <div className="space-y-4">
                  <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-6">
                    <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-primary/10">
                      <LogIn className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="mb-1.5 text-base font-semibold">需要登录</h3>
                    <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
                      登录后即可使用 AI 分析功能，获取区块内容的智能摘要、关键变化和风险评估。
                    </p>
                    <Link
                      to="/login"
                      className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      onClick={onClose}
                    >
                      去登录
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                </div>
              ) : null}
              {isLoading ? <div className="space-y-3"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /><div className="h-4 w-2/3 animate-pulse rounded bg-muted" /><div className="h-20 animate-pulse rounded bg-muted" /></div> : null}
              {error ? <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</p> : null}
              {analysis ? (
                <>
                  <section>
                    <h3 className="mb-2 text-xs font-medium text-muted-foreground">核心总结</h3>
                    <ul className="space-y-2">
                      {analysis.summary_points.map((item) => <li key={item} className="rounded-lg bg-muted/50 px-3 py-2 text-sm leading-6">{item}</li>)}
                    </ul>
                  </section>
                  {analysis.key_changes.length > 0 ? <InsightList title="关键变化" items={analysis.key_changes} /> : null}
                  {analysis.risk_points.length > 0 ? <InsightList title="风险/不确定性" items={analysis.risk_points} /> : null}
                  {analysis.related_entities.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {analysis.related_entities.map((item) => <span key={item} className="rounded-md border px-2 py-1 text-xs">{item}</span>)}
                    </div>
                  ) : null}
                  <button className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm" onClick={() => setEvidenceOpen((value) => !value)}>
                    <span>分析依据 {analysis.evidence_refs.length} 条</span>
                    <ChevronDown className={cn("h-4 w-4 transition-transform", evidenceOpen && "rotate-180")} />
                  </button>
                  {evidenceOpen ? (
                    <div className="space-y-2">
                      {analysis.evidence_refs.map((item, index) => <p key={`${item.title}-${index}`} className="text-xs leading-5 text-muted-foreground">{item.title}</p>)}
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

function InsightList({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium text-muted-foreground">{title}</h3>
      <ul className="space-y-2">
        {items.map((item) => <li key={item} className="text-sm leading-6">{item}</li>)}
      </ul>
    </section>
  );
}
