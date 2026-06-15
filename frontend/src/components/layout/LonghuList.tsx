import { useId } from "react";
import { Info } from "lucide-react";

import type { FieldDef } from "@/lib/field-defs";
import { cn } from "@/lib/utils";

interface LonghuItem {
  id?: string | number;
  title?: string;
  symbols?: string[];
  percent?: number;
  net_amount?: number;
  reason?: string;
  url?: string;
}

interface Props {
  data: LonghuItem[];
  fields: FieldDef[];
}

function formatPercent(value: number | undefined): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatAmount(value: number | undefined): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  if (absolute >= 1e8) return `${sign}${(absolute / 1e8).toFixed(1)}亿`;
  if (absolute >= 1e4) return `${sign}${(absolute / 1e4).toFixed(1)}万`;
  return `${sign}${Math.round(absolute)}`;
}

function valueTone(value: number | undefined): string {
  if (value == null || value === 0) return "text-muted-foreground";
  return value > 0 ? "text-red-500" : "text-green-500";
}

function StockIdentity({ item }: { item: LonghuItem }) {
  const name = item.title || "—";
  const code = item.symbols?.[0] || "";
  const content = (
    <>
      <span className="truncate font-medium text-foreground">{name}</span>
      {code ? <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{code}</span> : null}
    </>
  );

  return item.url ? (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex min-w-0 items-baseline gap-2 transition-colors hover:text-primary"
    >
      {content}
    </a>
  ) : (
    <div className="flex min-w-0 items-baseline gap-2">{content}</div>
  );
}

function ReasonTooltip({ name, reason }: { name: string; reason: string }) {
  const tooltipId = useId();

  return (
    <div className="longhu-reason-trigger">
      <button
        type="button"
        aria-describedby={tooltipId}
        aria-label={`查看${name}的上榜原因`}
        className="longhu-info-button"
      >
        <Info aria-hidden="true" size={15} strokeWidth={1.8} />
      </button>
      <div id={tooltipId} role="tooltip" className="longhu-tooltip">
        <span className="longhu-tooltip-label">上榜原因</span>
        <span>{reason || "暂无上榜原因"}</span>
      </div>
    </div>
  );
}

export function LonghuList({ data, fields }: Props) {
  const selected = new Set(fields.map((field) => field.key));
  const showTitle = selected.has("title");
  const showPercent = selected.has("percent");
  const showNetAmount = selected.has("net_amount");
  const showReason = selected.has("reason");

  return (
    <div
      data-testid="longhu-list"
      data-layout="compact-list"
      className="longhu-list rounded-lg border bg-card"
    >
      <div role="table" aria-label="龙虎榜">
        <div className="longhu-list-grid longhu-header" role="row">
          {showTitle ? <span role="columnheader">名称</span> : null}
          {showPercent ? <span role="columnheader" className="text-right">涨跌</span> : null}
          {showNetAmount ? <span role="columnheader" className="text-right">净买额</span> : null}
          {showReason ? <span role="columnheader" className="sr-only">上榜原因</span> : null}
        </div>
        {data.map((item, index) => (
          <div className="longhu-list-grid longhu-row" role="row" key={item.id ?? index}>
            {showTitle ? <div role="cell"><StockIdentity item={item} /></div> : null}
            {showPercent ? (
              <span role="cell" className={cn("text-right font-semibold tabular-nums", valueTone(item.percent))}>
                {formatPercent(item.percent)}
              </span>
            ) : null}
            {showNetAmount ? (
              <span role="cell" className={cn("text-right font-semibold tabular-nums", valueTone(item.net_amount))}>
                {formatAmount(item.net_amount)}
              </span>
            ) : null}
            {showReason ? (
              <div role="cell" className="flex justify-end">
                <ReasonTooltip name={item.title || "该股票"} reason={item.reason || ""} />
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
