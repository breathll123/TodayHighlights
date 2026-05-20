# Daily Highlights Design

## Context

The project is a daily highlights system based on web crawling. The first product direction is a thin full-stack MVP: one site, one topic, one frontend reading flow, and one admin workflow.

The confirmed first implementation target is:

- Topic: stocks
- Source site: Xueqiu
- Authentication mode: user-provided Cookie stored from the admin UI
- Backend: Python
- Frontend: React
- Database: MySQL
- AI summarization: OpenAI-compatible API with configurable `base_url`, `api_key`, and `model`

The system does not automate Xueqiu login, solve captchas, bypass anti-bot systems, or use proxy pools in the first version.

## Goals

- Run one complete data flow from Xueqiu source configuration to crawled raw items, AI-generated highlights, frontend display, and admin review.
- Keep each site crawler isolated behind a stable adapter interface so later sources such as Tonghuashun can be added without changing the rest of the system.
- Provide enough admin visibility to diagnose Cookie expiration, crawl failures, parser failures, AI failures, and content quality issues.
- Separate raw crawled content from edited highlights so the frontend can show polished content while the admin can trace every highlight back to source material.

## Non-Goals

- Automatic login or captcha handling.
- Distributed crawling, proxy pools, or multi-process worker infrastructure.
- Production-grade multi-user permission management.
- Real adapters for multiple websites.
- Complex BI charts or market analytics dashboards.
- Full text search beyond basic topic, tag, stock, and time filters.

## Architecture

Use a modular monolith for the first version.

The backend is one Python service with clear internal modules:

- `api/public`: frontend reading APIs.
- `api/admin`: admin APIs.
- `sources`: source configuration and adapter dispatch.
- `sources/xueqiu`: Xueqiu-specific adapter.
- `jobs`: manual and scheduled crawl job orchestration.
- `content`: raw item persistence, deduplication, highlight review operations.
- `summarizer`: OpenAI-compatible model calls and response normalization.
- `settings`: encrypted storage for Cookie and model credentials.

The frontend is one React application with public and admin routes:

- Public routes for the daily summary and stock topic detail page.
- Admin routes for source management, job logs, content review, and model settings.

MySQL stores source configuration, job logs, raw crawled items, generated highlights, topics, and application settings.

This architecture keeps deployment simple while preserving future extraction points. A later version can move `jobs`, `sources`, or `summarizer` into separate workers without changing the public API shape.

## Data Model

### `topics`

Stores available navigation topics such as `stocks`, later `ai`, `football`, and summary views.

Key fields:

- `id`
- `name`
- `slug`
- `sort_order`
- `enabled`
- `created_at`
- `updated_at`

### `sources`

Stores crawler source configuration. In the MVP this represents one or more Xueqiu stock sources.

Key fields:

- `id`
- `topic_id`
- `site`
- `name`
- `entry_url`
- `cookie_encrypted`
- `enabled`
- `crawl_interval_minutes`
- `last_crawled_at`
- `created_at`
- `updated_at`

The backend must never return Cookie plaintext. Admin APIs only return whether a Cookie is configured.

### `crawl_jobs`

Stores each crawl execution.

Key fields:

- `id`
- `source_id`
- `trigger_type`: `manual` or `scheduled`
- `status`: `pending`, `running`, `success`, `failed`, or `partial_success`
- `started_at`
- `finished_at`
- `items_found`
- `items_saved`
- `error_message`
- `log_excerpt`
- `created_at`

Only one `running` job should exist for a source at the same time.

### `raw_items`

Stores source material exactly as parsed from Xueqiu.

Key fields:

- `id`
- `source_id`
- `external_id`
- `url`
- `author`
- `title`
- `body`
- `published_at`
- `metrics_json`
- `content_hash`
- `created_at`

Deduplication uses `external_id` when available and `content_hash` as fallback.

### `highlights`

Stores AI-generated and manually edited daily highlight content.

Key fields:

- `id`
- `topic_id`
- `raw_item_id`
- `title`
- `summary`
- `related_symbols_json`
- `tags_json`
- `score`
- `is_pinned`
- `is_hidden`
- `review_status`
- `generated_by_model`
- `created_at`
- `updated_at`

The frontend reads from `highlights`, not directly from `raw_items`.

### `app_settings`

Stores model and system settings.

Key fields:

- `key`
- `value_json`
- `value_encrypted`
- `created_at`
- `updated_at`

Examples:

- `llm.base_url`
- `llm.api_key`
- `llm.model`

The backend must never return API key plaintext. Admin APIs only return whether a key is configured.

## Crawl And Summary Flow

The source adapter interface should expose a stable method such as:

```python
SourceAdapter.fetch(source_config) -> list[RawItemDraft]
```

The Xueqiu adapter:

- Reads `entry_url` and encrypted Cookie from the source configuration.
- Requests the configured Xueqiu page or endpoint using the configured Cookie.
- Extracts `external_id`, `url`, `author`, `title`, `body`, `published_at`, and interaction metrics.
- Returns normalized raw item drafts.

Failure behavior:

- Expired Cookie, HTTP 403, captcha pages, parser changes, and unexpected responses mark the job as `failed` or `partial_success`.
- Failures are visible through `crawl_jobs.error_message` and `crawl_jobs.log_excerpt`.
- The system does not attempt automatic login, captcha solving, or anti-bot bypass.

Scheduling:

- Admin users can manually trigger a crawl.
- The backend scheduler reads `sources.crawl_interval_minutes` and runs enabled sources periodically.
- A source cannot have more than one active `running` job at a time.

Content processing:

- New raw items are deduplicated and inserted into `raw_items`.
- Newly inserted items are sent to the summarizer.
- AI-generated outputs are saved into `highlights`.
- AI failure does not roll back raw item insertion. The job records the failure and the item remains available for retry.

AI summarization output:

- Highlight title.
- Summary of roughly 100-200 Chinese characters.
- Related stock symbols or names.
- Tags.
- Importance score.

## Frontend Design

### Public Summary Page

Route: `/`

The summary page shows daily highlights, initially focused on stocks.

Core content:

- Top navigation: summary and stocks, with AI and football reserved as disabled future topic entries if shown.
- Highlight cards with title, summary, related stocks, tags, source, published time, and generated time.
- Pinned highlights appear first.
- Hidden highlights are not shown.

### Stock Topic Detail Page

Route: `/topics/stocks`

The stock detail page shows all stock highlights with filters.

Core content:

- Filter by tag.
- Filter by related stock symbol or name.
- Sort by time or score.
- Open a highlight detail view showing AI summary, related raw Xueqiu content, source URL, crawl time, and job status.

## Admin Design

### Source Management

Route: `/admin/sources`

Capabilities:

- Create and edit Xueqiu sources.
- Set entry URL.
- Set or replace Cookie.
- Enable or disable the source.
- Configure crawl interval.
- Trigger immediate crawl.

Sensitive fields are write-only. The UI displays configured/not configured states.

### Job Logs

Route: `/admin/jobs`

Capabilities:

- View recent crawl jobs.
- See status, duration, found count, saved count, and failure summary.
- Diagnose Cookie expiration, HTTP failures, parser failures, and AI failures.

### Content Review

Route: `/admin/highlights`

Capabilities:

- Edit highlight title.
- Edit highlight summary.
- Pin or unpin.
- Hide or restore.
- Regenerate AI summary for one highlight.

### Model Settings

Route: `/admin/settings`

Capabilities:

- Configure OpenAI-compatible `base_url`.
- Configure API key.
- Configure model name.
- Show whether the API key is configured without exposing plaintext.

## Testing Strategy

Backend tests:

- Xueqiu adapter parsing with saved HTML or JSON fixtures.
- API tests for source configuration, manual crawl trigger, job log listing, content review, and model settings.
- Deduplication tests for `external_id` and `content_hash`.
- Summarizer tests using mocked OpenAI-compatible responses.
- Credential handling tests proving Cookie and API key plaintext are not returned by read APIs.

Frontend tests:

- Summary page renders visible highlights and excludes hidden highlights.
- Pinned highlights sort before normal highlights.
- Stock topic detail page shows associated raw source metadata.
- Admin source form saves configuration and can trigger a crawl.
- Job log page displays success, failure, and partial success states.
- Content review supports edit, pin, hide, restore, and regenerate actions.

Manual verification:

- Configure a Xueqiu source with Cookie.
- Trigger one manual crawl.
- Confirm raw items are inserted.
- Confirm AI highlights are generated.
- Confirm public pages show the generated highlights.
- Confirm admin pages show source state, job logs, and editable content.

## Delivery Scope

The first implementation should deliver:

- Python backend project.
- React frontend project.
- MySQL schema or migrations.
- `.env.example`.
- Xueqiu stock source adapter.
- Manual Cookie-based source configuration.
- Manual and scheduled crawl execution.
- OpenAI-compatible AI summarization.
- Public summary and stock detail pages.
- Admin source, job log, content review, and model settings pages.
- Development startup instructions.

## Open Decisions

- Exact Python framework: FastAPI is the default recommendation unless existing project constraints require Django or another framework.
- Exact frontend build tool: Vite React is the default recommendation unless existing project constraints require Next.js.
- Exact scheduler library: APScheduler is the default recommendation for the modular monolith MVP.
