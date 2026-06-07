import { useState, type CSSProperties, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface Props {
  blockId: number;
  heading: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const COLLAPSED_KEY_PREFIX = "df-block-collapsed-";

function isCollapsed(blockId: number): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY_PREFIX + blockId) === "1";
  } catch {
    return false;
  }
}

function setCollapsed(blockId: number, value: boolean) {
  try {
    if (value) localStorage.setItem(COLLAPSED_KEY_PREFIX + blockId, "1");
    else localStorage.removeItem(COLLAPSED_KEY_PREFIX + blockId);
  } catch { /* noop */ }
}

export function CollapsibleSection({ blockId, heading, children, className, style }: Props) {
  const [collapsed, setCollapsedState] = useState(() => isCollapsed(blockId));

  const toggle = () => {
    const next = !collapsed;
    setCollapsedState(next);
    setCollapsed(blockId, next);
  };

  return (
    <section className={cn("space-y-3", className)} style={style}>
      <div
        className="group flex cursor-pointer items-center gap-2 select-none"
        onClick={toggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } }}
        aria-expanded={!collapsed}
      >
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform duration-200",
            collapsed && "-rotate-90"
          )}
        />
        <div className="min-w-0 flex-1">{heading}</div>
      </div>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
