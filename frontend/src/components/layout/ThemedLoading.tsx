// -*- coding: utf-8 -*-
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useReducedMotion } from "framer-motion";
import Lottie from "lottie-react";
import { BlockSkeleton } from "./BlockSkeleton";
import { getTopicTheme } from "@/lib/topic-themes";

/**
 * 看板加载态：骨架屏网格打底，中央叠加当前主题的循环 Lottie 与文案。
 * reduced-motion 只保留骨架屏与文案；动画资源加载失败时静默降级为纯骨架屏。
 */
export function ThemedLoading() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const theme = getTopicTheme(location.pathname);
  const [animationData, setAnimationData] = useState<object | null>(null);

  useEffect(() => {
    if (!theme || reduceMotion) return;
    let cancelled = false;
    theme
      .loadAnimation()
      .then((data) => {
        if (!cancelled) setAnimationData(data);
      })
      .catch(() => {
        // 资源加载失败 → 保持纯骨架屏
      });
    return () => {
      cancelled = true;
    };
  }, [theme, reduceMotion]);

  return (
    <div className="relative">
      <div className="page-grid" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <BlockSkeleton key={i} colSpan={i % 2 === 0 ? 1 : 2} />
        ))}
      </div>
      {theme && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2" role="status">
          {!reduceMotion && animationData && (
            <Lottie animationData={animationData} loop autoplay style={{ width: 96, height: 96 }} />
          )}
          <p className="text-sm text-muted-foreground">{theme.loadingText}</p>
        </div>
      )}
    </div>
  );
}
