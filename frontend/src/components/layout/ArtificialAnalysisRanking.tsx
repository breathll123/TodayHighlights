import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { CompactTable } from "./CompactTable";
import type { BlockMeta } from "@/api/types";

const DATASET_LABELS: Record<string, string> = {
  language_global: "LLM",
  language_china: "中国 LLM",
  text_to_image: "文生图",
  text_to_video: "文生视频",
  image_to_video: "图生视频",
  text_to_speech: "文本转语音",
  speech_to_text: "语音转文本",
};

const DATASET_ORDER = [
  "language_global",
  "language_china",
  "text_to_image",
  "text_to_video",
  "image_to_video",
  "text_to_speech",
  "speech_to_text",
];

const SCORE_LABELS: Record<string, string> = {
  intelligence_index: "智能指数",
  elo: "Elo",
  aa_wer_index: "AA WER",
};

interface RankingItem {
  id: number;
  rank: number | null;
  title?: string;
  model?: string;
  creator?: string;
  subtitle?: string;
  score: number | null;
  score_type?: string;
  dataset_key?: string;
  release_date?: string | null;
}

interface Props {
  data: RankingItem[];
  meta?: BlockMeta | null;
}

function fmtReleaseDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 4);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

export function ArtificialAnalysisRanking({ data, meta }: Props) {
  const keys = useMemo(() => {
    const seen = new Set(data.map((item) => item.dataset_key ?? "language_global"));
    return DATASET_ORDER.filter((k) => seen.has(k));
  }, [data]);

  const [activeKey, setActiveKey] = useState(keys[0] ?? "language_global");

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无排名数据
      </div>
    );
  }

  const filtered = data.filter((item) => (item.dataset_key ?? "language_global") === activeKey);
  const firstItem = filtered[0];
  const scoreType = firstItem?.score_type ?? meta?.score_type ?? "intelligence_index";
  const scoreLabel = SCORE_LABELS[scoreType] ?? scoreType;
  const isWer = scoreType === "aa_wer_index";

  const mapped = filtered.map((item, i) => ({
    id: item.id,
    rank: item.rank ?? i + 1,
    title: item.title ?? item.model ?? "",
    subtitle: item.creator ?? item.subtitle ?? "",
    score: item.score ?? undefined,
    release: fmtReleaseDate(item.release_date),
    url: undefined,
    percent: undefined,
  }));

  const fields = [
    { key: "title" as const, label: "模型", type: "text" as const },
    { key: "subtitle" as const, label: "厂商", type: "text" as const },
    { key: "release" as const, label: "Released", type: "text" as const },
    { key: "score" as const, label: scoreLabel, type: "number" as const },
  ];

  return (
    <div className="border rounded-lg bg-card overflow-hidden">
      {keys.length > 1 && (
        <div className="flex items-center gap-1.5 border-b border-border/50 bg-muted/30 px-4 py-2.5">
          {keys.map((key) => (
            <button
              key={key}
              onClick={() => setActiveKey(key)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-[color,background-color,transform] active:scale-[0.97] ${
                activeKey === key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {DATASET_LABELS[key] ?? key}
            </button>
          ))}
        </div>
      )}
      <motion.div
        key={activeKey}
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        <CompactTable showRank data={mapped} fields={fields} />
      </motion.div>
      <div className="border-t border-border/50 bg-muted/20 px-4 py-2.5 space-y-1">
        <div className="flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <span>
            <a
              href="https://artificialanalysis.ai/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              数据来源：Artificial Analysis
            </a>
          </span>
          <span className="tabular-nums">
            {meta?.captured_at && (
              <time dateTime={meta.captured_at} className="tabular-nums">
                {new Date(meta.captured_at).toLocaleDateString("zh-CN")} 更新
              </time>
            )}
            {meta?.is_stale && (
              <span className="ml-2 inline-flex items-center rounded bg-yellow-500/10 px-1.5 py-0.5 text-[11px] font-medium text-yellow-400">
                数据较旧
              </span>
            )}
          </span>
        </div>
        {isWer && (
          <p className="text-[10px] text-muted-foreground/60">WER 越低越好</p>
        )}
        {meta?.scope_note && (
          <p className="text-[10px] text-muted-foreground/60">{meta.scope_note}</p>
        )}
      </div>
    </div>
  );
}
