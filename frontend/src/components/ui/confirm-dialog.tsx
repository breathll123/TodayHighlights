import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion, type MotionProps } from "framer-motion";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "destructive" | "default";
  /** Keeps the dialog open with a spinner on the confirm button while the action runs. */
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * A small, accessible confirmation modal with a deliberate pop-in animation —
 * the in-app replacement for the browser's native confirm(). Portals to
 * <body>, traps Escape, locks scroll, restores focus, and honours
 * prefers-reduced-motion (falling back to a plain fade).
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "确定",
  cancelLabel = "取消",
  tone = "destructive",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const reduceMotion = useReducedMotion();
  const confirmRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => confirmRef.current?.focus());
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      cancelAnimationFrame(raf);
      previouslyFocused?.focus?.();
    };
  }, [open, onCancel]);

  const isDestructive = tone === "destructive";

  const panelMotion: MotionProps = reduceMotion
    ? {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
        transition: { duration: 0.12 },
      }
    : {
        initial: { opacity: 0, scale: 0.94, y: 8 },
        animate: { opacity: 1, scale: 1, y: 0 },
        exit: { opacity: 0, scale: 0.96, y: 6 },
        transition: { type: "spring", stiffness: 320, damping: 26 },
      };

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onCancel}
            aria-hidden="true"
          />
          <motion.div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            {...panelMotion}
            className="relative w-full max-w-sm rounded-xl border bg-card p-5 shadow-2xl"
          >
            <div className="flex gap-4">
              <motion.span
                initial={reduceMotion ? false : { scale: 0.5, opacity: 0 }}
                animate={reduceMotion ? {} : { scale: 1, opacity: 1 }}
                transition={{ delay: 0.06, type: "spring", stiffness: 420, damping: 17 }}
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                  isDestructive ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary",
                )}
              >
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              </motion.span>
              <div className="min-w-0 flex-1 pt-0.5">
                <h2 id={titleId} className="text-sm font-semibold text-foreground">{title}</h2>
                {description ? (
                  <div id={descId} className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {description}
                  </div>
                ) : null}
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
                {cancelLabel}
              </Button>
              <Button
                ref={confirmRef}
                variant={isDestructive ? "destructive" : "default"}
                size="sm"
                onClick={onConfirm}
                disabled={loading}
              >
                {loading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}
                {confirmLabel}
              </Button>
            </div>
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
