// -*- coding: utf-8 -*-
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Lottie from "lottie-react";
import { getTopicTheme, type TopicTheme } from "@/lib/topic-themes";

interface PlayingState {
  theme: TopicTheme;
  pathname: string;
  animationData: object | null;
}

/**
 * 主题切换开场过场：进入 "/" 或 /topics/* 时全屏播放主题 Lottie，
 * openingDuration 后淡出。快速切换会取消上一场重播新主题；
 * reduced-motion 或动画资源加载失败时直接跳过。
 */
export function TopicTransitionOverlay() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const [playing, setPlaying] = useState<PlayingState | null>(null);

  useEffect(() => {
    if (reduceMotion) return;
    const theme = getTopicTheme(location.pathname);
    if (!theme) return;

    let cancelled = false;
    setPlaying({ theme, pathname: location.pathname, animationData: null });
    theme
      .loadAnimation()
      .then((data) => {
        if (cancelled) return;
        setPlaying((cur) => (cur && cur.pathname === location.pathname ? { ...cur, animationData: data } : cur));
      })
      .catch(() => {
        if (!cancelled) setPlaying(null);
      });
    const timer = setTimeout(() => {
      if (!cancelled) setPlaying(null);
    }, theme.openingDuration);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [location.pathname, reduceMotion]);

  return (
    <AnimatePresence>
      {playing && (
        <motion.div
          key={playing.pathname}
          data-testid="topic-transition-overlay"
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center bg-background"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
        >
          <div
            className="absolute inset-0"
            style={{ background: `radial-gradient(circle at center, ${playing.theme.accent}26 0%, transparent 60%)` }}
          />
          {playing.animationData && (
            <Lottie animationData={playing.animationData} loop={false} autoplay style={{ width: 180, height: 180 }} />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
