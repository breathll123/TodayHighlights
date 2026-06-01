# Football UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the football topic page into a compact professional match center while preserving the existing admin-configured block layout and qiumiwu data behavior.

**Architecture:** Add a football-only overview component rendered by `StockTopicPage` instead of the generic `DashboardShell` summary card. Keep the qiumiwu selection logic in `GridRenderer` and keep status formatting, league grouping, and row interaction behavior in `MatchList`.

**Tech Stack:** React, TypeScript, Tailwind CSS, lucide-react, Vitest, Testing Library

---

### Task 1: Add The Football Overview Bar

**Files:**
- Create: `frontend/src/components/layout/FootballTopicOverview.tsx`
- Modify: `frontend/src/pages/StockTopicPage.tsx`
- Test: `frontend/src/__tests__/public-pages.test.tsx`

- [ ] **Step 1: Write failing football page tests**

Add football-specific API data and assert that `/topics/football` renders a compact overview with `足球主题看板`, `球迷屋数据源`, `赛事数量`, `1 场`, `最近更新`, and `运行中`. Assert that the generic `当前主题`, `观测时间`, and `内容模块` summary tiles are absent.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- src/__tests__/public-pages.test.tsx`

Expected: FAIL because the football route still renders the generic `DashboardShell` summary.

- [ ] **Step 3: Implement the compact overview**

Create `FootballTopicOverview` with a title group and compact metadata items. Derive the football match count from `qiumiwu_matches` blocks in `StockTopicPage`, pass `dataUpdatedAt`, and render the football overview only for `/topics/football`. Keep `DashboardShell` unchanged for other topics and keep `GridRenderer` as the content renderer.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- src/__tests__/public-pages.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/FootballTopicOverview.tsx frontend/src/pages/StockTopicPage.tsx frontend/src/__tests__/public-pages.test.tsx
git commit -m "feat(football): add compact topic overview"
```

### Task 2: Flatten The Match List Visual Hierarchy

**Files:**
- Modify: `frontend/src/components/layout/MatchList.tsx`
- Modify: `frontend/src/components/layout/GridRenderer.tsx`
- Test: `frontend/src/__tests__/match-list.test.tsx`

- [ ] **Step 1: Write failing match-list tests**

Add assertions that:

- a live match dot includes a motion-safe pulse class;
- postponed and cancelled statuses render warm semantic status classes;
- URL-backed rows include a trailing chevron affordance;
- rows without URLs do not render that affordance.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- src/__tests__/match-list.test.tsx`

Expected: FAIL because the current rows have repeated rounded-card styling, no warm semantic status treatment, no motion-safe pulse, and no linked-row chevron.

- [ ] **Step 3: Implement flat match-center styling**

Update `MatchList` to:

- use one restrained container hierarchy with league header bars;
- render match rows as flat divider-separated rows;
- preserve the four-column score axis and truncation rules;
- add semantic status tones;
- add `motion-safe:animate-pulse` to live dots;
- add a compact `ChevronRight` only for link rows;
- retain keyboard focus styles and external-link behavior.

Update the qiumiwu wrapper in `GridRenderer` to reduce nested border and padding weight.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- src/__tests__/match-list.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/MatchList.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/__tests__/match-list.test.tsx
git commit -m "style(football): refine match center hierarchy"
```

### Task 3: Verify The Integrated Football Page

**Files:**
- Verify: `frontend/src/components/layout/FootballTopicOverview.tsx`
- Verify: `frontend/src/components/layout/MatchList.tsx`
- Verify: `frontend/src/pages/StockTopicPage.tsx`

- [ ] **Step 1: Run the full frontend test suite**

Run: `npm test`

Expected: all tests PASS.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: TypeScript and Vite build PASS. Existing chunk-size warnings may remain.

- [ ] **Step 3: Check patch formatting**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 4: Verify the page visually**

Open the football topic route with real qiumiwu data and confirm:

- the compact overview bar replaces the large generic dashboard card;
- admin-configured block spans still determine width;
- flat score rows, league bars, semantic status tones, and link affordances are visible;
- no horizontal overflow exists at desktop width or 375px mobile width.

- [ ] **Step 5: Commit any final verification-driven adjustment**

Only commit a final adjustment if browser verification exposes a concrete visual defect. Add a focused regression test first when behavior changes.
