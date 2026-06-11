# Artificial Analysis Rankings Design

## Goal

Replace the AI model leaderboard's request-time DataLearner scraping with a database-backed Artificial Analysis Free API integration. Persist every upstream response before parsing, publish normalized versioned ranking datasets to MySQL, and make all public-page reads database-only.

## Scope

The first release supports seven public rankings:

1. Global language models
2. Chinese language models
3. Text-to-image
4. Text-to-video
5. Image-to-video
6. Text-to-speech
7. Speech-to-text

The Chinese language ranking is derived locally from the global language dataset. It does not consume an additional Artificial Analysis request.

The integration is Free-only:

- Call only documented `/free` endpoints.
- Do not probe standard Pro endpoints.
- Do not retry a Free response against a Pro endpoint.
- Do not depend on Pro-only fields.

## Official API Boundaries

Base URL:

```text
https://artificialanalysis.ai/api/v2
```

Allowed endpoints:

```text
/language/models/free
/media/text-to-image/models/free
/media/text-to-video/models/free
/media/image-to-video/models/free
/media/text-to-speech/models/free
/media/speech-to-text/models/free
```

The language endpoint is paginated. The client follows `pagination.has_more` and `pagination.total_pages`; it does not assume there are always two pages. Media endpoints are treated as single-response datasets unless the official response shape later adds pagination.

The current official V2 documentation states a Free quota of 25 requests per day. Every response updates locally stored values from:

```text
X-AA-Tier
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
Retry-After
```

The API key is sent only through the `x-api-key` request header. Request headers and API keys are never persisted.

## Data Flow

```text
APScheduler or admin trigger
        |
        v
Acquire MySQL named lock
        |
        v
Create sync run
        |
        v
Request one allowed /free endpoint or language page
        |
        v
Commit raw response snapshot
        |
        v
Parse and validate committed snapshot
        |
        v
Create immutable dataset + entries
        |
        v
Publish dataset
        |
        v
Public block queries latest published MySQL dataset
```

No public page request calls Artificial Analysis. Redis may cache ordinary database query results later, but MySQL remains authoritative.

## Database Model

### `aa_sync_runs`

One row per scheduled or manual synchronization.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | bigint PK | Run identifier |
| `trigger_type` | varchar(20) | `scheduled` or `manual` |
| `requested_rankings_json` | JSON | Requested ranking types |
| `status` | varchar(30) | `pending`, `running`, `succeeded`, `partial`, `failed`, `rate_limited`, `skipped_locked`, `skipped_quota` |
| `requests_attempted` | int | Upstream requests started |
| `requests_succeeded` | int | HTTP 2xx responses |
| `datasets_published` | int | Successfully published datasets |
| `rate_limit_tier` | varchar(20) | Last observed `X-AA-Tier` |
| `rate_limit_limit` | int nullable | Last observed daily limit |
| `rate_limit_remaining` | int nullable | Last observed remaining requests |
| `rate_limit_reset_at` | datetime nullable | Converted reset timestamp |
| `started_at` | datetime nullable | Start time |
| `finished_at` | datetime nullable | Finish time |
| `error_message` | text | Run-level error summary |
| `created_at` | datetime | Creation time |

Index status and creation time for admin history queries.

### `aa_raw_snapshots`

One row per upstream HTTP response, including non-2xx responses.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | bigint PK | Snapshot identifier |
| `sync_run_id` | FK | Owning synchronization |
| `ranking_type` | varchar(40) | Requested dataset type |
| `endpoint_path` | varchar(255) | Relative allow-listed endpoint |
| `page_number` | int nullable | Language page number |
| `http_status` | int | Upstream status |
| `response_headers_json` | JSON | Allow-listed rate-limit and content headers |
| `response_body` | LONGTEXT | Exact response body |
| `content_hash` | char(64) | SHA-256 of raw response bytes |
| `parse_status` | varchar(20) | `pending`, `parsed`, `failed`, `skipped` |
| `parse_error` | text | Parser failure without losing raw data |
| `item_count` | int | Number of parsed records |
| `fetched_at` | datetime | Request completion time |
| `created_at` | datetime | Row creation time |

The raw snapshot is committed before parsing starts. The response header allow-list excludes cookies, authorization values, and request headers.

Raw snapshots are retained indefinitely in the first release. Their expected volume is small at two runs per day; cleanup can be added after real storage growth is measured.

### `aa_ranking_datasets`

An immutable successfully parsed version of one ranking.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | bigint PK | Dataset identifier |
| `sync_run_id` | FK | Publishing run |
| `ranking_type` | varchar(40) | One of the seven supported types |
| `source_snapshot_ids_json` | JSON | Raw snapshots used to build it |
| `derived_from_dataset_id` | FK nullable | Global language dataset used for Chinese derivation |
| `score_key` | varchar(80) | `intelligence_index`, `elo`, or `aa_wer_index` |
| `source_version` | varchar(40) | Intelligence Index version when available |
| `item_count` | int | Published entry count |
| `captured_at` | datetime | Upstream capture time |
| `published_at` | datetime | Publication time |
| `source_url` | varchar(500) | Official source page |
| `attribution` | varchar(255) | Visible attribution text |
| `metadata_json` | JSON | Pagination and parser metadata |
| `created_at` | datetime | Creation time |

A dataset and all its entries are inserted in one transaction. Public queries select the latest dataset ordered by `published_at DESC, id DESC`. Failed or incomplete parses never create a dataset.

### `aa_ranking_entries`

Normalized rows belonging to one immutable dataset.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | bigint PK | Entry identifier |
| `dataset_id` | FK | Owning dataset |
| `external_model_id` | varchar(80) | Artificial Analysis model ID |
| `model_slug` | varchar(180) | Model slug when provided |
| `model_name` | varchar(255) | Display name |
| `creator_external_id` | varchar(80) | Artificial Analysis creator ID |
| `creator_name` | varchar(180) | Creator display name |
| `creator_country` | char(2) nullable | Locally resolved country |
| `source_rank` | int | Order returned by the Free endpoint |
| `rank` | int | Published rank after local derivation |
| `score` | decimal(18,6) nullable | Primary displayed score |
| `score_key` | varchar(80) | Meaning of `score` |
| `ci_95` | decimal(18,6) nullable | Arena confidence interval |
| `release_date` | date nullable | Present for Free language models |
| `metrics_json` | JSON | All supported Free fields not promoted to columns |
| `created_at` | datetime | Creation time |

Use a unique constraint on `(dataset_id, external_model_id)` and an index on `(dataset_id, rank)`.

For language models, `metrics_json` retains the three headline indices, pricing, median performance, and Intelligence Index evaluation cost. For media rankings it retains the complete Free response object after known identifiers are normalized.

`source_rank` preserves the upstream order. This is important for speech-to-text because the Free documentation exposes `aa_wer_index` but does not define a local sorting contract. The parser does not invent a new global ordering.

### `aa_creator_regions`

A maintainable mapping used only for local regional derivation.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | bigint PK | Mapping identifier |
| `creator_external_id` | varchar(80) unique | Stable Artificial Analysis creator ID |
| `canonical_name` | varchar(180) | Creator name |
| `country_code` | char(2) | Lowercase ISO code, such as `cn` |
| `aliases_json` | JSON | Historical or alternate names |
| `enabled` | boolean | Whether mapping participates |
| `notes` | text | Maintenance context |
| `created_at` / `updated_at` | datetime | Audit timestamps |

The migration seeds confirmed Chinese creators already needed by the current datasets, including ByteDance Seed and Kuaishou KlingAI. Additional mappings are maintained in MySQL, not hard-coded into the parser.

Unknown creators remain global-only. Name matching is permitted only as a logged fallback when no stable creator ID mapping exists.

## Parsing and Publication Rules

### Global language models

- Fetch every language page.
- Require every page reported by pagination.
- Reject duplicate model IDs across pages.
- Use `evaluations.artificial_analysis_intelligence_index` as the primary score.
- Preserve API order as `source_rank`.
- Publish only when the full page set succeeds.

### Chinese language models

- Never call another upstream endpoint.
- Derive from the newly published global language dataset.
- Include entries whose enabled creator mapping has `country_code = "cn"`.
- Sort by non-null Intelligence Index descending, then global source rank.
- Re-number `rank` from one.
- Store `derived_from_dataset_id`.

The public page states:

```text
中国模型范围由今日看点根据模型厂商归属整理；原始评分来自 Artificial Analysis。
```

### Image, video, and text-to-speech

- Use `elo` as primary score.
- Preserve upstream order as `source_rank` and published `rank`.
- Store `ci_95`.

### Speech-to-text

- Use `aa_wer_index` as primary score.
- Preserve upstream order as rank instead of assuming whether a future index revision is ascending or descending.

### Validation

A ranking is not published when:

- HTTP status is not 2xx.
- JSON is invalid.
- Required `data` is missing or not a list.
- A required model or creator identifier is absent.
- The result is empty.
- Language pagination is incomplete.
- Duplicate model IDs are found in one dataset.

The raw snapshot remains available with `parse_status = "failed"` and a bounded error message.

## Synchronization and Quota Control

Scheduled times are:

```text
08:30 Asia/Shanghai
20:30 Asia/Shanghai
```

A normal run currently consumes approximately seven requests:

- Two or more language pages, determined dynamically
- Five single-response media endpoints

At two runs per day this is expected to stay below the documented 25-request Free limit while leaving retry and manual-operation headroom.

Before a full run:

- Read the latest known quota state.
- Treat quota as unknown when the stored reset timestamp has passed; do not let yesterday's exhausted value block a new daily window.
- Skip an optional manual full run when known remaining requests are below eight.
- Scheduled runs may start only when known remaining requests are sufficient for the six first requests plus one language continuation page.
- Before every additional language page, re-check the latest response header.
- Stop immediately on `429`; persist the response and `Retry-After`, mark the run `rate_limited`, and publish no incomplete affected dataset.

Retries are conservative:

- Network failure: one retry with short backoff.
- `5xx`: one retry only when remaining quota is unknown or safely above the reserve.
- `401`, `403`, and `429`: no retry.
- A `403` is treated as configuration or endpoint-contract failure; the client does not try a Pro route.

Each upstream attempt counts in `requests_attempted`, including retries.

## Concurrency

Every synchronization acquires a MySQL named lock:

```text
today-highlights:artificial-analysis-sync
```

The lock is acquired on a dedicated database connection with zero wait and released in `finally`. This prevents duplicate quota consumption when multiple FastAPI workers each start APScheduler.

If the lock is unavailable, a scheduled invocation exits without creating duplicate HTTP traffic. Manual requests return a conflict response identifying the active synchronization.

## Configuration

Add environment settings:

```env
ARTIFICIAL_ANALYSIS_ENABLED=false
ARTIFICIAL_ANALYSIS_API_KEY=
ARTIFICIAL_ANALYSIS_BASE_URL=https://artificialanalysis.ai/api/v2
ARTIFICIAL_ANALYSIS_SYNC_HOURS=8,20
ARTIFICIAL_ANALYSIS_SYNC_MINUTE=30
ARTIFICIAL_ANALYSIS_TIMEOUT_SECONDS=20
```

The API key remains in environment configuration and is never returned by admin or public APIs.

The client has a code-level endpoint allow-list. A configured base URL may change for tests, but requested paths must still be one of the six `/free` paths.

## Service Boundaries

### `artificial_analysis_client.py`

- Authenticated HTTP transport
- `/free` endpoint allow-list
- Timeout and conservative retry policy
- Safe response header extraction
- No parsing into application ranking models

### `artificial_analysis_parser.py`

- Pure parsing functions per response shape
- Validation and normalization
- No HTTP or database access

### `artificial_analysis_sync.py`

- MySQL lock lifecycle
- Sync run state
- Raw snapshot-first persistence
- Dataset publication transactions
- Quota decisions
- Chinese dataset derivation

### `artificial_analysis_rankings.py`

- Latest published dataset queries
- Conversion into public block response objects
- No third-party HTTP access

## Admin API

Add:

```text
GET  /api/admin/artificial-analysis/status
GET  /api/admin/artificial-analysis/runs
POST /api/admin/artificial-analysis/sync
GET  /api/admin/artificial-analysis/creator-regions
POST /api/admin/artificial-analysis/creator-regions
PUT  /api/admin/artificial-analysis/creator-regions/{id}
```

The sync request accepts either all rankings or selected ranking types. Selecting `language_china` automatically requests `language_global` because China is derived.
The endpoint returns `202 Accepted` with a run ID after scheduling background execution. It returns `409 Conflict` when the MySQL synchronization lock is already held.

The status response includes:

- Enabled/configured state without exposing the key
- Latest run
- Latest successful dataset time per ranking
- Last known rate limit and reset time
- Current sync-in-progress state

## Public Block Integration

Introduce one database-backed source type:

```text
artificial_analysis_ranking
```

`source_config`:

```json
{
  "ranking_type": "language_global",
  "display_fields": ["model", "creator", "score"]
}
```

Supported `ranking_type` values:

```text
language_global
language_china
text_to_image
text_to_video
image_to_video
text_to_speech
speech_to_text
```

`resolve_block_data()` treats this source as database-dependent. It queries the latest published dataset and never enters the live-adapter executor.

Public response entries include:

```text
id
rank
model
creator
creator_country
score
score_key
ci_95
metrics
captured_at
source_url
```

Every ranking block displays:

- Artificial Analysis attribution link
- Dataset capture time
- Score label appropriate to the ranking
- A stale-data badge when the latest dataset is older than 36 hours

## Frontend Configuration

The layout editor presents an `Artificial Analysis` group with one source type and a ranking selector. It does not expose endpoint paths, tier selection, API keys, arbitrary sort fields, or Pro options.

Ranking labels:

```text
全球语言模型
中国语言模型
文生图
文生视频
图生视频
文本转语音
语音转文本
```

Use one reusable ranking table. The first three ranks retain the existing medal/icon treatment. Mobile layouts prioritize rank, model, and score; creator and confidence interval move to secondary text.

## Migration and Cutover

1. Add the five Artificial Analysis tables and initial Chinese creator mappings.
2. Configure the Free API key in the backend environment.
3. Run one manual synchronization and verify all raw snapshots and datasets.
4. Add the new database-backed block source.
5. Change existing published `datalearner_aa_index` blocks to:

```json
{
  "source_type": "artificial_analysis_ranking",
  "source_config": {
    "ranking_type": "language_global"
  }
}
```

6. Remove DataLearner ranking choices from the layout editor.
7. Keep the old adapter code unreferenced for one release as rollback support; delete it only after the new source has completed several successful scheduled runs.

If no Artificial Analysis dataset exists at cutover time, the block returns an empty state rather than calling DataLearner or Artificial Analysis during the page request.

## Testing

### Client

- Every request path ends in an allowed `/free` endpoint.
- Pro paths are rejected before network access.
- API keys never appear in persisted headers or errors.
- `401`, `403`, and `429` are not retried.
- Quota headers are parsed correctly.

### Raw persistence

- Raw response is committed before parser execution.
- Invalid JSON and parser exceptions leave a retrievable snapshot.
- Non-2xx response bodies are retained.
- Duplicate response hashes may exist across runs for audit history.

### Parsers

- Language pagination merges complete pages.
- Missing pages prevent publication.
- Free language metrics are retained.
- Arena Elo and confidence intervals normalize correctly.
- Speech-to-text preserves upstream ordering.
- Empty and malformed payloads fail validation.

### Publication

- Dataset and entries publish atomically.
- Failed refresh leaves the previous dataset readable.
- One failed ranking does not block successful independent rankings.
- China derivation uses creator IDs and produces consecutive ranks.
- Unknown creators are excluded from China without disappearing globally.

### Scheduling and concurrency

- Scheduled jobs use 08:30 and 20:30 Asia/Shanghai.
- MySQL lock prevents concurrent runs.
- Low known quota skips manual full sync.
- `429` stops remaining requests.

### Public and frontend

- Public block resolution performs only SQL queries.
- All seven ranking types render.
- Attribution and capture time are visible.
- Stale state appears after 36 hours.
- Mobile ranking rows do not overflow.

## Out of Scope

- Pro or Commercial endpoints
- Automatic plan detection or upgrade
- Provider-level benchmark details
- Paid pricing fields unavailable in Free responses
- Real-time page-triggered refresh
- Redis as the source of truth
- Deleting historical raw snapshots in the first release

## Sources

- [Artificial Analysis Data API documentation](https://artificialanalysis.ai/data-api/docs#overview-hero)
- [Artificial Analysis OpenAPI specification](https://artificialanalysis.ai/api/v2/openapi)
