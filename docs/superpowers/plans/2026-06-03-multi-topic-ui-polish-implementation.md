# DataFlow Multi-Topic UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a consistent premium data-dashboard visual language across AI, football, and stock topics, with medal-plus-number badges for every top-three ranking, semantic section icons, restrained motion, and unified spacing.

**Architecture:** Introduce two focused presentation components: `RankBadge` owns rank semantics and top-three rendering, while `SectionHeading` owns section title hierarchy and icons. Extend `CompactTable` with an optional rank column so the AA intelligence index can reuse the same badge. Keep layout spans, API payloads, and backend behavior unchanged.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, Framer Motion, Vitest, Testing Library.

---

## Baseline

Run before implementation:

```bash
cd frontend
npm test
```

Expected baseline: `4` historical failures and `32` passing tests.

Historical failures to correct before feature work:

- `MatchList > refreshes the recent update time...`: implementation displays a full timestamp.
- `MatchList > shows a live dot and minute...`: semantic color class is on the parent status container.
- `MatchList > uses warm semantic emphasis...`: semantic color class is on the parent status container.
- `FootballTopicPage > renders a compact football overview...`: current page uses `DashboardShell`, not the removed `football-topic-overview`.

## File Structure

Create:

- `frontend/src/components/layout/RankBadge.tsx`: rank icon, number, top-three palette, accessible label, and top-row tone helper.
- `frontend/src/components/layout/SectionHeading.tsx`: reusable icon-and-title heading.
- `frontend/src/__tests__/rank-badge.test.tsx`: rank rendering behavior.
- `frontend/src/__tests__/ranking-tables.test.tsx`: compact table, AI leaderboard, and football standings behavior.

Modify:

- `frontend/src/__tests__/match-list.test.tsx`: align historical assertions and test section icon/filter motion hooks.
- `frontend/src/__tests__/public-pages.test.tsx`: align historical `DashboardShell` assertions.
- `frontend/src/components/layout/CompactTable.tsx`: optional rank column and shared row styling.
- `frontend/src/components/layout/GridRenderer.tsx`: retain AA rank, configure compact rank column, render semantic headings, standardize module spacing.
- `frontend/src/components/layout/LeaderboardTable.tsx`: use rank badges, semantic heading, top-three row tone, and restrained row motion.
- `frontend/src/components/layout/StandingsTable.tsx`: use rank badges, semantic heading, top-three row tone, and restrained league switch motion.
- `frontend/src/components/layout/MatchList.tsx`: semantic heading, filter press feedback, and content fade transition.
- `frontend/src/styles/globals.css`: dashboard spacing token classes and reduced-motion coverage.

## Task 1: Restore A Trustworthy Frontend Baseline

**Files:**

- Modify: `frontend/src/__tests__/match-list.test.tsx`
- Modify: `frontend/src/__tests__/public-pages.test.tsx`

- [ ] **Step 1: Update the stale timestamp assertion**

Replace:

```tsx
expect(screen.getByText("最近更新 14:32:08")).toBeInTheDocument();
expect(screen.getByText("最近更新 14:35:09")).toBeInTheDocument();
```

with:

```tsx
expect(screen.getByText("最近更新 2026-06-01 14:32:08")).toBeInTheDocument();
expect(screen.getByText("最近更新 2026-06-01 14:35:09")).toBeInTheDocument();
```

- [ ] **Step 2: Update semantic color assertions to target the status container**

Replace the live assertion with:

```tsx
expect(within(row).getByText("67'").parentElement).toHaveClass("text-red-500");
```

Replace postponed and cancelled assertions with:

```tsx
expect(within(screen.getByRole("link")).getByText("延期").parentElement).toHaveClass("text-amber-500");
expect(within(screen.getByRole("link")).getByText("取消").parentElement).toHaveClass("text-amber-500");
```

- [ ] **Step 3: Replace the removed football overview expectations**

In `public-pages.test.tsx`, assert the current shared shell:

```tsx
expect(await screen.findByText("今日赛程")).toBeInTheDocument();
expect(screen.getByText("足球主题看板")).toBeInTheDocument();
expect(screen.getByText("全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。")).toBeInTheDocument();
expect(screen.getByText("当前主题")).toBeInTheDocument();
expect(screen.getByText("观测时间")).toBeInTheDocument();
expect(screen.getByText("内容模块")).toBeInTheDocument();
expect(screen.getByText("平台状态")).toBeInTheDocument();
```

- [ ] **Step 4: Run the suite**

Run:

```bash
cd frontend
npm test
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/__tests__/match-list.test.tsx frontend/src/__tests__/public-pages.test.tsx
git commit -m "test: align frontend assertions with current dashboard"
```

## Task 2: Add The Shared Ranking Primitive

**Files:**

- Create: `frontend/src/components/layout/RankBadge.tsx`
- Create: `frontend/src/__tests__/rank-badge.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `rank-badge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RankBadge, rankRowTone } from "../components/layout/RankBadge";

describe("RankBadge", () => {
  it.each([1, 2, 3])("renders a medal and number for rank %s", (rank) => {
    render(<RankBadge rank={rank} />);
    expect(screen.getByLabelText(`第 ${rank} 名`)).toBeInTheDocument();
    expect(screen.getByTestId(`rank-medal-${rank}`)).toBeInTheDocument();
    expect(screen.getByText(String(rank))).toBeInTheDocument();
  });

  it("renders a plain number outside the top three", () => {
    render(<RankBadge rank={4} />);
    expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
    expect(screen.queryByTestId("rank-medal-4")).not.toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders a placeholder when rank is missing", () => {
    render(<RankBadge />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("returns restrained row tones only for the top three", () => {
    expect(rankRowTone(1)).toContain("rank-row-gold");
    expect(rankRowTone(2)).toContain("rank-row-silver");
    expect(rankRowTone(3)).toContain("rank-row-bronze");
    expect(rankRowTone(4)).toBe("");
  });
});
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/rank-badge.test.tsx
```

Expected: FAIL because `RankBadge.tsx` does not exist.

- [ ] **Step 3: Implement `RankBadge`**

Create `RankBadge.tsx`:

```tsx
import { Medal } from "lucide-react";
import { cn } from "@/lib/utils";

const TOP_RANKS = {
  1: { icon: "text-amber-400", number: "text-amber-300" },
  2: { icon: "text-slate-300", number: "text-slate-200" },
  3: { icon: "text-orange-400", number: "text-orange-300" },
} as const;

export function rankRowTone(rank?: number): string {
  if (rank === 1) return "rank-row-gold";
  if (rank === 2) return "rank-row-silver";
  if (rank === 3) return "rank-row-bronze";
  return "";
}

export function RankBadge({ rank, className }: { rank?: number; className?: string }) {
  const palette = rank && rank <= 3 ? TOP_RANKS[rank as keyof typeof TOP_RANKS] : undefined;
  if (!rank) return <span className={cn("text-muted-foreground", className)}>—</span>;

  return (
    <span aria-label={`第 ${rank} 名`} className={cn("inline-flex items-center justify-center gap-1 tabular-nums", className)}>
      {palette ? <Medal data-testid={`rank-medal-${rank}`} className={cn("h-3.5 w-3.5", palette.icon)} aria-hidden="true" /> : null}
      <span className={cn("font-semibold", palette?.number ?? "text-muted-foreground")}>{rank}</span>
    </span>
  );
}
```

- [ ] **Step 4: Run the new test and verify GREEN**

Run:

```bash
cd frontend
npx vitest run src/__tests__/rank-badge.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/RankBadge.tsx frontend/src/__tests__/rank-badge.test.tsx
git commit -m "feat(ui): add shared top-three rank badge"
```

## Task 3: Add Semantic Section Headings

**Files:**

- Create: `frontend/src/components/layout/SectionHeading.tsx`
- Create: `frontend/src/__tests__/section-heading.test.tsx`

- [ ] **Step 1: Write a failing heading test**

Create `section-heading.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { BrainCircuit } from "lucide-react";
import { describe, expect, it } from "vitest";
import { SectionHeading } from "../components/layout/SectionHeading";

it("renders a semantic icon, title, and optional metadata", () => {
  render(<SectionHeading icon={BrainCircuit} title="AI模型排行" meta="10 个模型" />);
  expect(screen.getByRole("heading", { name: "AI模型排行" })).toBeInTheDocument();
  expect(screen.getByTestId("section-heading-icon")).toBeInTheDocument();
  expect(screen.getByText("10 个模型")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/section-heading.test.tsx
```

Expected: FAIL because `SectionHeading.tsx` does not exist.

- [ ] **Step 3: Implement `SectionHeading`**

Create `SectionHeading.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function SectionHeading({
  icon: Icon,
  title,
  meta,
  className,
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center justify-between gap-3", className)}>
      <h2 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-foreground/85">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
          <Icon data-testid="section-heading-icon" className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <span className="truncate">{title}</span>
      </h2>
      {meta ? <span className="shrink-0 text-[11px] text-muted-foreground">{meta}</span> : null}
    </div>
  );
}
```

- [ ] **Step 4: Run the new test and verify GREEN**

Run:

```bash
cd frontend
npx vitest run src/__tests__/section-heading.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/SectionHeading.tsx frontend/src/__tests__/section-heading.test.tsx
git commit -m "feat(ui): add semantic section heading"
```

## Task 4: Extend CompactTable For AA Intelligence Rankings

**Files:**

- Modify: `frontend/src/components/layout/CompactTable.tsx`
- Modify: `frontend/src/components/layout/GridRenderer.tsx`
- Create: `frontend/src/__tests__/ranking-tables.test.tsx`

- [ ] **Step 1: Write the failing compact table test**

Create `ranking-tables.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CompactTable } from "../components/layout/CompactTable";

const fields = [
  { key: "title", label: "模型", type: "text" as const },
  { key: "score", label: "智能指数", type: "number" as const },
];

describe("CompactTable rankings", () => {
  it("renders an optional rank column with top-three medals", () => {
    render(<CompactTable showRank data={[{ id: 1, rank: 1, title: "Claude", score: 61 }, { id: 2, rank: 4, title: "Gemini", score: 57 }]} fields={fields} />);
    expect(screen.getByText("排名")).toBeInTheDocument();
    expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
    expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/ranking-tables.test.tsx
```

Expected: FAIL because `CompactTable` does not support `showRank`.

- [ ] **Step 3: Add rank support to `CompactTable`**

Extend the row and props:

```tsx
interface Row {
  id?: string | number;
  rank?: number;
  title: string;
  subtitle?: string;
  percent?: number;
  score?: string | number;
  url?: string;
}

interface Props {
  data: Row[];
  fields: FieldDef[];
  showRank?: boolean;
}
```

Import:

```tsx
import { RankBadge, rankRowTone } from "./RankBadge";
```

Render a `排名` header and `RankBadge` cell when `showRank` is true. Prepend `2.75rem` to the existing grid template. Add `data-rank-row` and `rankRowTone(item.rank)` to rows and use `min-h-10 px-3 py-2.5` for compact but readable density:

```tsx
<div
  key={item.id ?? idx}
  data-rank-row={showRank ? item.rank : undefined}
  className={cn("grid min-h-10 items-center gap-x-3 border-b px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30", showRank && rankRowTone(item.rank))}
  style={{ gridTemplateColumns: cols }}
>
  {showRank ? <RankBadge rank={item.rank} className="justify-center" /> : null}
  {fields.map((f, i) => (
    <div key={f.key} className={colAlign(f, i)}>
      {cell(f.key, item)}
    </div>
  ))}
</div>
```

- [ ] **Step 4: Preserve AA ranks in `GridRenderer`**

Add `rank: item.rank` to `mapItem()` output and render:

```tsx
<CompactTable
  showRank
  data={filtered.map((item: any) => mapItem(item, block.source_type))}
  fields={displayFields}
/>
```

for `AAIndexBlock`.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run:

```bash
cd frontend
npx vitest run src/__tests__/ranking-tables.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/CompactTable.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/__tests__/ranking-tables.test.tsx
git commit -m "feat(ai): show ranked AA intelligence index"
```

## Task 5: Polish AI And Football Ranking Tables

**Files:**

- Modify: `frontend/src/components/layout/LeaderboardTable.tsx`
- Modify: `frontend/src/components/layout/StandingsTable.tsx`
- Modify: `frontend/src/__tests__/ranking-tables.test.tsx`

- [ ] **Step 1: Add failing table tests**

Append:

```tsx
import { LeaderboardTable } from "../components/layout/LeaderboardTable";
import { StandingsTable } from "../components/layout/StandingsTable";

it("renders medals in the AI multi-benchmark leaderboard", () => {
  render(<LeaderboardTable data={[{ id: 1, title: "Claude", summary: "", rank: 1, HLE: "61" }, { id: 2, title: "Gemini", summary: "", rank: 4, HLE: "57" }]} />);
  expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
  expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  expect(screen.getByText("AI 模型排行榜")).toBeInTheDocument();
});

it("renders medals in football standings but keeps fourth place plain", () => {
  render(<StandingsTable data={[{ id: 1, title: "", summary: "", league: "英超", rank: 1, team: "阿森纳" }, { id: 2, title: "", summary: "", league: "英超", rank: 4, team: "切尔西" }]} />);
  expect(screen.getByTestId("rank-medal-1")).toBeInTheDocument();
  expect(screen.getByLabelText("第 4 名")).toBeInTheDocument();
  expect(screen.queryByTestId("rank-medal-4")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/ranking-tables.test.tsx
```

Expected: FAIL because both tables still render plain rank text.

- [ ] **Step 3: Update `LeaderboardTable`**

Import:

```tsx
import { BrainCircuit, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";
import { RankBadge, rankRowTone } from "./RankBadge";
```

Replace the rank span with:

```tsx
<RankBadge rank={item.rank} className="justify-center" />
```

Use `data-rank-row={item.rank}`, `rankRowTone(item.rank)`, a right-side `ExternalLink` affordance, and a short `motion.a` entrance with:

```tsx
initial={{ opacity: 0, y: 4 }}
animate={{ opacity: 1, y: 0 }}
transition={{ duration: 0.22, delay: Math.min(i, 6) * 0.03, ease: "easeOut" }}
```

Add `BrainCircuit` to the table header. Preserve all benchmark columns.

- [ ] **Step 4: Update `StandingsTable`**

Import:

```tsx
import { ChevronLeft, ChevronRight, Trophy } from "lucide-react";
import { motion } from "framer-motion";
import { RankBadge, rankRowTone } from "./RankBadge";
```

Replace the rank span with:

```tsx
<RankBadge rank={item.rank} className="justify-center" />
```

Use `data-rank-row={item.rank}` and `rankRowTone(item.rank)`, add `Trophy` to the league header, apply `active:scale-[0.98]` to tabs, and render rows as `motion.a` with the same restrained entrance timing.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
cd frontend
npx vitest run src/__tests__/ranking-tables.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/LeaderboardTable.tsx frontend/src/components/layout/StandingsTable.tsx frontend/src/__tests__/ranking-tables.test.tsx
git commit -m "feat(ui): polish AI and football ranking tables"
```

## Task 6: Apply Semantic Headings And Restrained Motion Across Topics

**Files:**

- Modify: `frontend/src/components/layout/GridRenderer.tsx`
- Modify: `frontend/src/components/layout/MatchList.tsx`
- Modify: `frontend/src/styles/globals.css`
- Modify: `frontend/src/__tests__/match-list.test.tsx`
- Modify: `frontend/src/__tests__/ranking-tables.test.tsx`

- [ ] **Step 1: Add failing interaction tests**

In `match-list.test.tsx`, append:

```tsx
it("shows a semantic match heading and press feedback on filters", () => {
  render(<MatchList data={[match()]} />);
  expect(screen.getByText("比赛中心")).toBeInTheDocument();
  expect(screen.getByText("全部").className).toContain("active:scale");
});
```

In `ranking-tables.test.tsx`, append:

```tsx
it("uses restrained top-three glow hooks", () => {
  render(<CompactTable showRank data={[{ id: 1, rank: 1, title: "Claude", score: 61 }]} fields={fields} />);
  expect(screen.getByLabelText("第 1 名").closest("[data-rank-row]")).toHaveClass("rank-row-gold");
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/match-list.test.tsx src/__tests__/ranking-tables.test.tsx
```

Expected: FAIL because heading, press feedback, and CSS hook are missing.

- [ ] **Step 3: Add semantic heading selection in `GridRenderer`**

Import:

```tsx
import { BrainCircuit, CalendarClock, ChartNoAxesCombined, Newspaper, Trophy } from "lucide-react";
import { SectionHeading } from "./SectionHeading";
```

Add:

```tsx
function sectionIcon(sourceType: string) {
  if (sourceType === "qiumiwu_matches") return CalendarClock;
  if (sourceType === "qiumiwu_standings") return Trophy;
  if (sourceType.startsWith("datalearner_")) return BrainCircuit;
  if (sourceType === "tonghuashun_news") return Newspaper;
  return ChartNoAxesCombined;
}
```

Replace block-level plain `h2` with:

```tsx
<SectionHeading icon={sectionIcon(st)} title={block.title} />
```

Change section spacing to `space-y-3`.

- [ ] **Step 4: Add `MatchList` heading and content transition**

Import `CalendarClock` and `motion`. Add a compact header:

```tsx
<div className="flex items-center justify-between gap-3 border-b border-border/50 bg-muted/30 px-3 py-2">
  <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground/85">
    <CalendarClock className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
    比赛中心
  </span>
  <span className="text-[10px] text-muted-foreground/60">最近更新 {updatedAt}</span>
</div>
```

Keep filters in a second compact row with `active:scale-[0.97] transition-[color,background-color,transform]`. Wrap filtered date content in a keyed `motion.div`:

```tsx
<motion.div
  key={statusFilter}
  initial={{ opacity: 0, y: 3 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.18, ease: "easeOut" }}
>
```

- [ ] **Step 5: Add global row tone hooks and spacing**

Append to `globals.css`:

```css
@layer components {
  .rank-row-gold {
    background: linear-gradient(90deg, hsl(38 92% 54% / 0.09), transparent 68%);
    box-shadow: inset 2px 0 0 hsl(38 92% 54% / 0.72);
  }
  .rank-row-silver {
    background: linear-gradient(90deg, hsl(215 16% 68% / 0.07), transparent 68%);
    box-shadow: inset 2px 0 0 hsl(215 16% 68% / 0.56);
  }
  .rank-row-bronze {
    background: linear-gradient(90deg, hsl(24 72% 48% / 0.07), transparent 68%);
    box-shadow: inset 2px 0 0 hsl(24 72% 48% / 0.56);
  }
}
```

Change `.page-grid` gap from `18px` to `16px`.

Keep the existing global reduced-motion block unchanged. It already collapses animation and transition durations for `prefers-reduced-motion: reduce`, covering the new Framer Motion wrappers and Tailwind transitions.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```bash
cd frontend
npx vitest run src/__tests__/match-list.test.tsx src/__tests__/ranking-tables.test.tsx src/__tests__/section-heading.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/GridRenderer.tsx frontend/src/components/layout/MatchList.tsx frontend/src/styles/globals.css frontend/src/__tests__/match-list.test.tsx frontend/src/__tests__/ranking-tables.test.tsx
git commit -m "feat(ui): unify topic headings motion and spacing"
```

## Task 7: Full Verification And Browser QA

**Files:**

- Verify only.

- [ ] **Step 1: Run the full frontend test suite**

Run:

```bash
cd frontend
npm test
```

Expected: PASS.

- [ ] **Step 2: Run a production build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS with TypeScript and Vite build output.

- [ ] **Step 3: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Verify AI in the in-app browser**

Open:

```text
http://localhost:5175/topics/ai
```

Check:

- Global AA ranking shows medal plus number for ranks `1`, `2`, and `3`.
- Domestic ranking switch retains medal plus number rendering.
- Fourth place is a plain number.
- Section icons are visible but secondary to data.
- Switching regions fades content without layout jump.

- [ ] **Step 5: Verify football in the in-app browser**

Open:

```text
http://localhost:5175/topics/football
```

Check:

- Match list shows `比赛中心` with `CalendarClock`.
- Live match pulse remains visible.
- Standings show `Trophy`.
- Standings ranks `1`, `2`, and `3` show medals and numbers; fourth place is plain.
- Match rows remain readable without horizontal overflow on a narrow viewport.

- [ ] **Step 6: Verify stocks in the in-app browser**

Open:

```text
http://localhost:5175/topics/stocks
```

Check:

- Section icons and spacing align with AI and football.
- Existing percentage colors and stock table readability are unchanged.

- [ ] **Step 7: Review final diff**

Run:

```bash
git status --short
git diff --stat master...HEAD
git log --oneline --decorate -8
```

Expected: only planned frontend, test, and plan files changed.
