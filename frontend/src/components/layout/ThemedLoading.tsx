// -*- coding: utf-8 -*-
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useReducedMotion } from "framer-motion";
import Lottie from "lottie-react";
import { getTopicTheme } from "@/lib/topic-themes";

/**
 * 看板加载态：居中展示当前主题的循环 Lottie 与文案，不渲染骨架框。
 * reduced-motion 只保留文案；动画资源加载失败时静默降级为纯文案。
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
        // 资源加载失败 → 保持纯文案
      });
    return () => {
      cancelled = true;
    };
  }, [theme, reduceMotion]);

  if (!theme) return null;

  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center gap-2" role="status">
      {!reduceMotion && animationData && (
        <Lottie animationData={animationData} loop autoplay style={{ width: 96, height: 96 }} />
      )}
      <p className="text-sm text-muted-foreground">{theme.loadingText}</p>
    </div>
  );
}
