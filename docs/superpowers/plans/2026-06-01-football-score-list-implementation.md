# Football Score List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the football page's preliminary match rows with a compact league-grouped live score list that displays match time or status and the frontend's latest successful refresh time.

**Architecture:** Keep football rendering isolated in `MatchList`. `GridRenderer` already routes `qiumiwu_matches` blocks to that component, so the implementation only needs to normalize numeric match statuses, format display time, and render the approved four-column score layout. Update the football topic copy separately so the page names the active 球迷屋 source.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, Vitest, Testing Library

---

## File Structure

- Create: `frontend/src/__tests__/match-list.test.tsx`
  - Component-level tests for grouped leagues, match clock/status selection, score rendering, and refresh time.
- Modify: `frontend/src/components/layout/MatchList.tsx`
  - Football-specific data normalization and compact score list rendering.
- Modify: `frontend/src/__tests__/public-pages.test.tsx`
  - Route-level regression test for the football page source description.
- Modify: `frontend/src/pages/StockTopicPage.tsx`
  - Replace the stale 懂球帝 source description with 球迷屋.

### Task 1: Lock Down Match List Behavior

**Files:**
- Create: `frontend/src/__tests__/match-list.test.tsx`
- Modify: `frontend/src/components/layout/MatchList.tsx`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/__tests__/match-list.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MatchList } from "@/components/layout/MatchList";

const matches = [
  {
    id: "fixture",
    title: "阿森纳 vs 利物浦",
    summary: "",
    league: "英超",
    status: 1,
    team_a: "阿森纳",
    team_b: "利物浦",
    score_a: "",
    score_b: "",
    start_time: "2026-06-01T20:30:00",
  },
  {
    id: "live-minute",
    title: "曼城 vs 切尔西",
    summary: "",
    league: "英超",
    status: 2,
    status_name: "上半场",
    team_a: "曼城",
    team_b: "切尔西",
    score_a: "2",
    score_b: "1",
    minute: "67",
    start_time: "2026-06-01T19:00:00",
  },
  {
    id: "live-stage",
    title: "巴塞罗那 vs 赫塔菲",
    summary: "",
    league: "西甲",
    status: 8,
    status_name: "下半场",
    team_a: "巴塞罗那",
    team_b: "赫塔菲",
    score_a: "1",
    score_b: "0",
    start_time: "2026-06-01T21:00:00",
  },
  {
    id: "played",
    title: "热刺 vs 维拉",
    summary: "",
    league: "英超",
    status: 15,
    status_name: "完场",
    team_a: "热刺",
    team_b: "维拉",
    score_a: "1",
    score_b: "1",
    start_time: "2026-06-01T18:00:00",
  },
];

describe("MatchList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 1, 14, 32, 8));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("groups matches by league and shows the latest successful refresh time", () => {
    render(<MatchList data={matches} />);

    expect(screen.getByText("今日赛程与比分")).toBeInTheDocument();
    expect(screen.getByText("最近更新 14:32:08")).toBeInTheDocument();
    expect(screen.getByText("英超")).toBeInTheDocument();
    expect(screen.getByText("3 场")).toBeInTheDocument();
    expect(screen.getByText("西甲")).toBeInTheDocument();
    expect(screen.getByText("1 场")).toBeInTheDocument();
  });

  it("renders fixture time, live minute with stage fallback, and final score", () => {
    render(<MatchList data={matches} />);

    expect(within(screen.getByTestId("match-fixture")).getByText("20:30")).toBeInTheDocument();
    expect(within(screen.getByTestId("match-fixture")).getByText("vs")).toBeInTheDocument();
    expect(within(screen.getByTestId("match-live-minute")).getByText("67'")).toBeInTheDocument();
    expect(within(screen.getByTestId("match-live-stage")).getByText("下半场")).toBeInTheDocument();
    expect(within(screen.getByTestId("match-played")).getByText("完场")).toBeInTheDocument();
    expect(within(screen.getByTestId("match-played")).getByText("1 - 1")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend
npm test -- match-list.test.tsx
```

Expected: FAIL because the preliminary list does not render `今日赛程与比分`, does not display refresh time, and compares status against legacy strings instead of numeric 球迷屋 statuses.

- [ ] **Step 3: Implement the compact score list**

Replace `frontend/src/components/layout/MatchList.tsx` with:

```tsx
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

interface MatchItem {
  id: string | number;
  title: string;
  summary: string;
  url?: string;
  league: string;
  status: number | string;
  status_name?: string;
  team_a: string;
  team_b: string;
  score_a: string;
  score_b: string;
  minute?: string;
  start_time: string;
}

interface Props {
  data: MatchItem[];
}

const STATUS_LABELS: Record<string, string> = {
  "2": "上半场",
  "8": "下半场",
  "15": "完场",
  "18": "延期",
  "19": "取消",
  Playing: "进行中",
  Played: "完场",
  Fixture: "未开始",
  Postponed: "延期",
  Cancelled: "取消",
  Uncertain: "待定",
};

function groupByLeague(items: MatchItem[]): Record<string, MatchItem[]> {
  const groups: Record<string, MatchItem[]> = {};
  for (const item of items) {
    const league = item.league || "其他";
    if (!groups[league]) groups[league] = [];
    groups[league].push(item);
  }
  return groups;
}

function formatClock(date: Date): string {
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function formatStartTime(startTime: string): string {
  if (!startTime) return "待定";
  const date = new Date(startTime);
  if (Number.isNaN(date.getTime())) return "待定";
  return [date.getHours(), date.getMinutes()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function isFixture(match: MatchItem): boolean {
  return String(match.status) === "1" || match.status === "Fixture";
}

function isLive(match: MatchItem): boolean {
  return ["2", "8", "Playing"].includes(String(match.status));
}

function displayStatus(match: MatchItem): string {
  if (isFixture(match)) return formatStartTime(match.start_time);
  if (isLive(match) && match.minute) {
    return match.minute.endsWith("'") ? match.minute : `${match.minute}'`;
  }
  return STATUS_LABELS[String(match.status)] || match.status_name || "待定";
}

function displayScore(match: MatchItem): string {
  if (isFixture(match)) return "vs";
  return `${match.score_a || "-"} - ${match.score_b || "-"}`;
}

export function MatchList({ data }: Props) {
  const [updatedAt, setUpdatedAt] = useState(() => new Date());
  const groups = groupByLeague(data);

  useEffect(() => {
    setUpdatedAt(new Date());
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 pb-3">
        <h3 className="text-sm font-semibold text-foreground">今日赛程与比分</h3>
        <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          最近更新 {formatClock(updatedAt)}
        </span>
      </div>

      {Object.entries(groups).map(([league, matches]) => (
        <section key={league} className="space-y-2">
          <div className="flex items-center justify-between gap-3 px-1">
            <h4 className="truncate text-xs font-semibold text-muted-foreground">{league}</h4>
            <span className="shrink-0 text-[11px] font-medium text-primary">{matches.length} 场</span>
          </div>
          <div className="divide-y divide-border/60 overflow-hidden rounded-lg border border-border/60 bg-background/25">
            {matches.map((match) => (
              <a
                key={match.id}
                data-testid={`match-${match.id}`}
                href={match.url}
                target="_blank"
                rel="noopener noreferrer"
                className="grid grid-cols-[3.5rem_minmax(0,1fr)_3.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-2.5 text-xs transition-colors hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[4rem_minmax(0,1fr)_4.5rem_minmax(0,1fr)] sm:gap-3 sm:px-3"
              >
                <span className="inline-flex min-w-0 items-center gap-1 font-medium tabular-nums text-muted-foreground">
                  {isLive(match) && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" aria-hidden="true" />}
                  <span className={isLive(match) ? "truncate text-rose-400" : "truncate"}>
                    {displayStatus(match)}
                  </span>
                </span>
                <span className="truncate text-sm font-medium text-foreground">{match.team_a || "待定"}</span>
                <span className="text-center text-sm font-semibold tabular-nums text-foreground">{displayScore(match)}</span>
                <span className="truncate text-right text-sm font-medium text-foreground">{match.team_b || "待定"}</span>
              </a>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd frontend
npm test -- match-list.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the match list implementation**

```bash
git add frontend/src/__tests__/match-list.test.tsx frontend/src/components/layout/MatchList.tsx
git commit -m "feat(football): add compact live score list"
```

### Task 2: Correct Football Topic Source Copy

**Files:**
- Modify: `frontend/src/__tests__/public-pages.test.tsx`
- Modify: `frontend/src/pages/StockTopicPage.tsx`

- [ ] **Step 1: Add a failing route-level regression test**

Add this wrapper and test to `frontend/src/__tests__/public-pages.test.tsx`:

```tsx
function FootballWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/topics/football"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("FootballTopicPage", () => {
  it("names the active football data source", async () => {
    render(<StockTopicPage />, { wrapper: FootballWrapper });
    expect(await screen.findByText("足球主题看板")).toBeInTheDocument();
    expect(screen.getByText("全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the route-level test to verify it fails**

Run:

```bash
cd frontend
npm test -- public-pages.test.tsx
```

Expected: FAIL because the football page still says `懂球帝数据源`.

- [ ] **Step 3: Correct the football source description**

Change the `/topics/football` entry in `frontend/src/pages/StockTopicPage.tsx`:

```tsx
  "/topics/football": {
    name: "足球",
    description: "全球足球联赛实时比分、赛程、积分榜，球迷屋数据源。",
  },
```

- [ ] **Step 4: Run the route-level test to verify it passes**

Run:

```bash
cd frontend
npm test -- public-pages.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the source copy correction**

```bash
git add frontend/src/__tests__/public-pages.test.tsx frontend/src/pages/StockTopicPage.tsx
git commit -m "fix(football): name qiumiwu as active source"
```

### Task 3: Verify the Football Dashboard

**Files:**
- Verify only

- [ ] **Step 1: Run the complete frontend test suite**

Run:

```bash
cd frontend
npm test
```

Expected: all test files pass.

- [ ] **Step 2: Build the production frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite production build succeed. The existing bundle-size advisory may remain.

- [ ] **Step 3: Check patch whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Verify the football route visually**

Open `http://127.0.0.1:5173/topics/football` in the in-app browser and verify:

- `1440px` viewport: the score list remains compact and aligned.
- `375px` viewport: no horizontal overflow.
- Fixture rows show `HH:mm` and `vs`.
- Live rows show a red dot and minute or stage fallback.
- Finished rows show `完场` and the final score.
- The title bar shows `最近更新 HH:mm:ss`.
