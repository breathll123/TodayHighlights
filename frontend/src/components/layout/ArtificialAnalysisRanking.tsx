import { CompactTable } from "./CompactTable";
import type { ArtificialAnalysisRankingItem, BlockMeta } from "@/api/types";

const SCORE_LABELS: Record<string, string> = {
  intelligence_index: "智能指数",
  elo: "Elo",
  aa_wer_index: "AA WER",
};

interface Props {
  data: ArtificialAnalysisRankingItem[];
  meta?: BlockMeta | null;
}

export function ArtificialAnalysisRanking({ data, meta }: Props) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-card/60 p-6 text-center text-sm text-muted-foreground">
        暂无排名数据
      </div>
    );
  }

  const scoreLabel = meta?.score_type ? (SCORE_LABELS[meta.score_type] ?? meta.score_type) : "评分";
  const isWer = meta?.score_type === "aa_wer_index";

  const mapped = data.map((item, i) => ({
    id: item.id,
    rank: item.rank ?? i + 1,
    title: item.title ?? item.model,
    subtitle: item.creator ?? item.subtitle,
    score: item.score ?? undefined,
    url: undefined,
    percent: undefined,
  }));

  const fields = [
    { key: "title" as const, label: "模型", type: "text" as const },
    { key: "subtitle" as const, label: "厂商", type: "text" as const },
    { key: "score" as const, label: scoreLabel, type: "number" as const },
  ];

  return (
    <div className="border rounded-lg bg-card overflow-hidden">
      <CompactTable showRank data={mapped} fields={fields} />
      {meta && (
        <div className="border-t border-border/50 bg-muted/20 px-4 py-2.5 space-y-1">
          <div className="flex items-center justify-between gap-3 text-[10px] text-muted-foreground">
            <span>
              {meta.source_name && (
                <a
                  href={meta.source_url ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  数据来源：{meta.source_name}
                </a>
              )}
            </span>
            <span className="tabular-nums">
              {meta.captured_at && (
                <time dateTime={meta.captured_at} className="tabular-nums">
                  {new Date(meta.captured_at).toLocaleDateString("zh-CN")} 更新
                </time>
              )}
              {meta.is_stale && (
                <span className="ml-2 inline-flex items-center rounded bg-yellow-500/10 px-1.5 py-0.5 text-[9px] font-medium text-yellow-400">
                  数据较旧
                </span>
              )}
            </span>
          </div>
          {isWer && (
            <p className="text-[9px] text-muted-foreground/60">WER 越低越好</p>
          )}
          {meta.scope_note && (
            <p className="text-[9px] text-muted-foreground/60">{meta.scope_note}</p>
          )}
        </div>
      )}
    </div>
  );
}
