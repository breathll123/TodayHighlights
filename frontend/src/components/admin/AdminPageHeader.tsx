import type { ReactNode } from "react";
import { motion, type Variants } from "framer-motion";

interface AdminPageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}

const easeOutQuint = [0.22, 1, 0.36, 1] as const;

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: easeOutQuint } },
};

export function AdminPageHeader({ eyebrow, title, description, action }: AdminPageHeaderProps) {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="relative flex flex-col gap-4 border-b border-border/70 pb-5 sm:flex-row sm:items-end sm:justify-between"
    >
      <div>
        <motion.div variants={item} className="mb-2 text-xs font-semibold uppercase text-primary">{eyebrow}</motion.div>
        <motion.h1 variants={item} className="text-2xl font-semibold text-foreground">{title}</motion.h1>
        <motion.p variants={item} className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</motion.p>
      </div>
      {action && <motion.div variants={item} className="shrink-0">{action}</motion.div>}

      {/* Accent rule that extends along the bottom border on entrance. */}
      <motion.span
        aria-hidden="true"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.5, ease: easeOutQuint, delay: 0.12 }}
        className="absolute -bottom-px left-0 h-px w-28 origin-left bg-gradient-to-r from-primary/60 to-transparent"
      />
    </motion.div>
  );
}
