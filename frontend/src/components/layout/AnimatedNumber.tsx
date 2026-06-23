import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

// easeOutQuint — the same curve used for block/row reveals, so numbers
// settle with the same physics as everything else on the page.
const easeOutQuint = (t: number): number => 1 - Math.pow(1 - t, 5);

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

interface AnimatedNumberProps {
  value: number;
  /** Render the (possibly fractional, mid-animation) value to a string. */
  format?: (value: number) => string;
  durationMs?: number;
  /** Roll up from zero on first mount — for KPI/stat reveals. */
  animateOnMount?: boolean;
  className?: string;
  style?: CSSProperties;
}

/**
 * Rolls from its current displayed value to a new one whenever `value`
 * changes — the live-tape count-up. Interrupts mid-flight cleanly (a new
 * target picks up from whatever is on screen) and honours reduced-motion.
 */
export function AnimatedNumber({
  value,
  format = (n) => n.toFixed(2),
  durationMs = 650,
  animateOnMount = false,
  className,
  style,
}: AnimatedNumberProps) {
  const initial = animateOnMount ? 0 : value;
  const [display, setDisplay] = useState(initial);
  const displayRef = useRef(initial);
  const rafRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const from = displayRef.current;
    if (from === value) return;

    if (prefersReducedMotion()) {
      displayRef.current = value;
      setDisplay(value);
      return;
    }

    const start = performance.now();
    const delta = value - from;

    const tick = (now: number) => {
      const progress = Math.min((now - start) / durationMs, 1);
      const next = from + delta * easeOutQuint(progress);
      displayRef.current = next;
      setDisplay(next);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        displayRef.current = value;
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current);
    };
  }, [value, durationMs]);

  return (
    <span className={cn("tabular-nums", className)} style={style}>
      {format(display)}
    </span>
  );
}

/**
 * Returns a flash class for ~0.75s whenever `value` changes, coloured by
 * direction (红涨绿跌). Apply it to the container behind the value. The
 * double-rAF reset guarantees the CSS animation restarts on repeat ticks.
 */
export function useTickFlash(value: number): string {
  const prevRef = useRef(value);
  const [flashClass, setFlashClass] = useState("");
  const timerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const prev = prevRef.current;
    if (prev === value) return;
    const direction = value > prev ? "tick-flash-up" : "tick-flash-down";
    prevRef.current = value;

    setFlashClass("");
    const raf = requestAnimationFrame(() => setFlashClass(direction));
    if (timerRef.current !== undefined) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setFlashClass(""), 760);

    return () => cancelAnimationFrame(raf);
  }, [value]);

  useEffect(
    () => () => {
      if (timerRef.current !== undefined) clearTimeout(timerRef.current);
    },
    [],
  );

  return flashClass;
}

/**
 * Wraps an already-formatted value so its cell washes red/green (红涨绿跌)
 * the moment the underlying number changes — the per-row "tape". Layout is
 * neutral (padding is cancelled by matching negative margins).
 */
export function FlashValue({
  value,
  className,
  children,
}: {
  value: number | null | undefined;
  className?: string;
  children: ReactNode;
}) {
  const flashClass = useTickFlash(typeof value === "number" ? value : 0);
  return (
    <span className={cn("-mx-1.5 -my-0.5 inline-block rounded px-1.5 py-0.5", flashClass, className)}>
      {children}
    </span>
  );
}
