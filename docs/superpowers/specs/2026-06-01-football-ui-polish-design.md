# Football UI Polish Design

## Scope

Polish the football topic page into a compact professional match center without adding new product features.

The backend layout contract remains unchanged:

- Block width and height continue to follow the admin-configured `col_span` and `row_span`.
- Existing qiumiwu match data, status mapping, league grouping, links, and refresh timestamp semantics remain unchanged.
- Other topic pages keep their existing dashboard header and block rendering.

## Football Topic Header

Replace the football page's large generic dashboard summary card with a football-specific compact overview bar.

The overview bar contains:

- Page title: `足球主题看板`
- Short source description: `全球足球联赛实时比分与赛程，球迷屋数据源`
- Match count derived from the published qiumiwu match block data
- Latest successful frontend fetch time
- Platform status: `运行中`

Desktop layout is a single horizontal row with a title group on the left and compact metadata items on the right. Mobile layout wraps naturally into a compact two-column metadata grid below the title. The header must not recreate the current four large statistic cards.

## Match List

Keep the existing central-axis score layout, but remove the repeated card appearance.

### Container

- Use one restrained outer surface for the complete match list.
- Keep the list compatible with any admin-configured block span.
- Reduce nested borders and shadows.
- Preserve horizontal overflow protection at narrow widths.

### League Groups

- Render each league name and match count in a subtle section header.
- Use a lightly tinted background or divider treatment to create hierarchy.
- Keep spacing compact so long schedules remain scannable.

### Match Rows

- Render each match as a flat row separated by subtle dividers.
- Preserve the fixed structure: `time/status | home team | score | away team`.
- Keep team names truncated safely where required.
- Use tabular figures for times and scores.
- Emphasize the centered score with stronger weight and contrast.
- Keep completed matches visually quiet.
- Use warm semantic emphasis for postponed and cancelled matches.
- Use a red dot, red minute label, and a subtle pulse for live matches.
- Disable pulse animation under `prefers-reduced-motion`.

### Interaction

- Rows with a URL remain links that open in a new tab.
- Linked rows gain a restrained hover background and border-independent visual feedback.
- Linked rows show a small trailing chevron as an affordance without reducing room for team names.
- Keyboard focus remains visible.
- Rows without URLs remain non-interactive and must not show clickable affordances.

## Component Boundaries

- Add a football-specific compact header component or an explicit football rendering branch near `StockTopicPage`.
- Keep match row formatting and status presentation inside `MatchList`.
- Keep `GridRenderer` responsible for selecting `MatchList` for qiumiwu blocks and respecting admin layout spans.
- Do not modify the shared `DashboardShell` appearance for all topics solely to satisfy the football page.

## Responsive Behavior

- Verify at 375px mobile width and a desktop viewport.
- The overview bar wraps without horizontal scrolling.
- Match rows remain one-line scan targets and do not expand into stacked mobile cards.
- League groups and match rows remain readable when the block is assigned a narrow admin span.

## Testing

Add focused tests for:

- Football page renders the compact overview instead of the generic four-card summary.
- Match count and latest update time are exposed in the football overview.
- Live rows retain the live dot and provide a motion-safe pulse class.
- Cancelled and postponed rows use semantic emphasis.
- Linked rows show an affordance while unlinked rows remain non-clickable.

Run:

- `npm test`
- `npm run build`
- `git diff --check`
- Browser verification with real football data at desktop and 375px widths
