# Artificial Analysis Rankings Design

## 1. Goal

Replace the AI dashboard's live DataLearner model ranking requests with a database-backed Artificial Analysis integration.

The system must:

- collect seven ranking datasets from the Artificial Analysis V2 API;
- save every bounded HTTP response before parsing or error handling it;
- parse and version normalized ranking data in MySQL;
- derive a China language-model ranking without an additional upstream request;
- serve public pages only from MySQL;
- preserve the last successfully published dataset when collection or parsing fails;
- stay within the current Free API allowance of 25 requests per day.

The first release covers:

1. Global language models
2. China language models
3. Text-to-image
4. Text-to-video
5. Image-to-video
6. Text-to-speech
7. Speech-to-text

## 2. Non-goals

- The public page must not call Artificial Analysis directly.
- Redis must not be the authoritative ranking store.
- The integration will not introduce Celery, RQ, or another task queue.
- The first release will not ingest image editing, speech-to-speech, music, or video-with-audio rankings.
- The first release will not automatically delete the DataLearner adapter.
- The first release will not infer creator regions with fuzzy, suffix, or substring matching.

## 3. Upstream API

### 3.1 Endpoints

The Free API endpoints are:

| Dataset | Endpoint |
| --- | --- |
| Global language models | `/api/v2/language/models/free` |
| Text-to-image | `/api/v2/media/text-to-image/models/free` |
| Text-to-video | `/api/v2/media/text-to-video/models/free` |
| Image-to-video | `/api/v2/media/image-to-video/models/free` |
| Text-to-speech | `/api/v2/media/text-to-speech/models/free` |
| Speech-to-text | `/api/v2/media/speech-to-text/models/free` |

China language models are derived from the global language-model response and do not consume another upstream request.

Language models use pagination. The collector must follow `pagination.has_more` and request subsequent pages dynamically. No fixed page count is allowed.

### 3.2 Authentication and attribution

The API key is supplied only by the backend:

```env
ARTIFICIAL_ANALYSIS_API_KEY=
ARTIFICIAL_ANALYSIS_SYNC_ENABLED=true
ARTIFICIAL_ANALYSIS_QUOTA_RESERVE=2
```

The key must never be stored in ranking records, logs, API responses, block configuration, or frontend state.

Public ranking components must display a visible link:

```text
数据来源：Artificial Analysis
```

China rankings must additionally display:

```text
中国模型范围由今日看点根据模型厂商归属整理，原始评分来自 Artificial Analysis。
```

### 3.3 Rate-limit handling

The collector records these headers after every authenticated response:

- `X-AA-Tier`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After`, when present

Quota decisions must use the most recent response headers. They must not assume that a full run always requires a fixed number of requests.

Before requesting another page or dataset:

1. If the remaining quota is unknown, the request may proceed.
2. If `remaining <= ARTIFICIAL_ANALYSIS_QUOTA_RESERVE`, collection stops cleanly.
3. If a response is `429`, collection stops immediately and records the reset time.
4. Completed datasets may publish; incomplete datasets retain their previous published version.

The configured reserve defaults to two requests. It protects recovery and operational inspection but is not a forecast of the remaining run cost.

## 4. Architecture

```text
APScheduler or admin request
        |
        v
ArtificialAnalysisSyncService
        |
        +--> authenticated HTTP request
        |
        +--> persist compressed raw response
        |
        +--> validate and parse response
        |
        +--> create immutable dataset + entries
        |
        +--> publish dataset atomically
        |
        v
MySQL
        |
        v
resolve_block_data(session, block)
        |
        v
public page API
        |
        v
React dashboard
```

Each upstream response is persisted before parsing. A parser can therefore be rerun against saved data without spending API quota.

Normalized datasets are immutable. Publishing changes which completed dataset is current; it does not overwrite previous entries.

## 5. Data model

### 5.1 `aa_sync_runs`

Tracks one scheduled or manual synchronization attempt.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `trigger_type` | VARCHAR(30) | `scheduled`, `manual`, `reparse` |
| `status` | VARCHAR(30) | `pending`, `running`, `partial`, `succeeded`, `failed`, `quota_exhausted`, `abandoned` |
| `requested_by_user_id` | BIGINT NULL FK | Admin for manual runs |
| `requested_datasets_json` | JSON | Requested dataset keys |
| `completed_datasets_json` | JSON | Successfully published dataset keys |
| `failed_datasets_json` | JSON | Dataset key and error summary |
| `request_count` | INT | Requests used by this run |
| `quota_tier` | VARCHAR(30) | Latest `X-AA-Tier` |
| `quota_limit` | INT NULL | Latest known daily limit |
| `quota_remaining` | INT NULL | Latest known remaining requests |
| `quota_reset_at` | DATETIME NULL | Parsed reset time |
| `started_at` | DATETIME NULL | |
| `heartbeat_at` | DATETIME NULL | Updated between requests and parsing phases |
| `finished_at` | DATETIME NULL | |
| `error_message` | TEXT | Run-level error |
| `created_at` | DATETIME | |

Indexes:

- `(status, created_at)`
- `(trigger_type, created_at)`

Only one `pending` or `running` synchronization may exist at a time.

### 5.2 `aa_raw_snapshots`

Stores one upstream HTTP response before parsing.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `sync_run_id` | BIGINT FK | Owning run |
| `dataset_key` | VARCHAR(50) | Dataset being collected |
| `endpoint` | VARCHAR(500) | Path without credentials |
| `page_number` | INT | One-based page number; media endpoints use `1` |
| `http_status` | INT | |
| `response_headers_json` | JSON | Safe allowlisted headers only |
| `body_compressed` | LONGBLOB | Gzip-compressed original response bytes |
| `compression` | VARCHAR(20) | `gzip` |
| `content_type` | VARCHAR(120) | |
| `body_sha256` | CHAR(64) | Hash of uncompressed bytes |
| `original_size_bytes` | INT | |
| `compressed_size_bytes` | INT | |
| `parse_status` | VARCHAR(30) | `pending`, `parsed`, `failed` |
| `parse_error` | TEXT | |
| `captured_at` | DATETIME | |

Constraints and indexes:

- Unique `(sync_run_id, dataset_key, page_number)`
- Index `(dataset_key, captured_at)`
- Index `(body_sha256)`

The API key and full request headers are never stored.

### 5.3 `aa_ranking_datasets`

Represents one immutable parsed version of a ranking.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `sync_run_id` | BIGINT FK | |
| `dataset_key` | VARCHAR(50) | `language_global`, `language_china`, `text_to_image`, `text_to_video`, `image_to_video`, `text_to_speech`, `speech_to_text` |
| `scope` | VARCHAR(20) | `global`, `china` |
| `score_type` | VARCHAR(40) | `intelligence_index`, `elo`, `aa_wer_index` |
| `status` | VARCHAR(30) | `parsing`, `ready`, `published`, `failed`, `superseded` |
| `source_tier` | VARCHAR(30) | `free`, `pro`, `commercial` |
| `source_version` | VARCHAR(40) | Intelligence Index version when available |
| `entry_count` | INT | |
| `source_snapshot_ids_json` | JSON | Snapshot IDs used by the parser |
| `data_sha256` | CHAR(64) | Hash of canonical normalized entries |
| `captured_at` | DATETIME | Upstream capture time |
| `published_at` | DATETIME NULL | |
| `error_message` | TEXT | |
| `created_at` | DATETIME | |

Indexes and constraints:

- Index `(dataset_key, status, published_at)`
- Unique `(dataset_key, data_sha256)`
- At most one `published` dataset per `dataset_key`, enforced by the publication service transaction.

### 5.4 `aa_ranking_entries`

Stores normalized rows for a dataset.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `dataset_id` | BIGINT FK | |
| `model_external_id` | VARCHAR(120) | Artificial Analysis model ID |
| `model_slug` | VARCHAR(200) | Empty when unavailable |
| `model_name` | VARCHAR(300) | |
| `creator_external_id` | VARCHAR(120) | Empty when creator is null |
| `creator_name` | VARCHAR(200) | |
| `creator_region` | VARCHAR(20) | `cn`, `other`, `unknown` |
| `rank` | INT | Rank recalculated from normalized score |
| `score` | DECIMAL(16,6) NULL | Primary ranking score |
| `score_type` | VARCHAR(40) | |
| `ci_95` | DECIMAL(16,6) NULL | |
| `release_date` | DATE NULL | |
| `metrics_json` | JSON | Dataset-specific metrics |
| `pricing_json` | JSON | Available pricing fields |
| `performance_json` | JSON | Available performance fields |
| `source_url` | VARCHAR(500) | Artificial Analysis ranking URL |
| `created_at` | DATETIME | |

Constraints and indexes:

- Unique `(dataset_id, model_external_id)`
- Index `(dataset_id, rank)`
- Index `(creator_external_id)`

If a model external ID is missing, the parser uses a deterministic fallback key based on dataset key, normalized model name, and normalized creator name. It records this condition in `metrics_json.parser_warnings`.

### 5.5 `aa_creator_regions`

Maintains creator ownership for derived regional rankings.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | BIGINT PK | |
| `creator_external_id` | VARCHAR(120) NULL | Preferred identity |
| `canonical_name` | VARCHAR(200) | |
| `normalized_name` | VARCHAR(200) | Case-folded, whitespace-normalized name |
| `region_code` | VARCHAR(20) | `cn`, `other`, `unknown` |
| `source` | VARCHAR(30) | `observed`, `manual`, `official_country` |
| `notes` | TEXT | |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

Constraints:

- Unique `creator_external_id` when present
- Unique `normalized_name`

The first release does not include `aliases_json`.

## 6. Raw-response persistence

### 6.1 Ordering

For every response:

1. Read the response bytes with a hard client limit.
2. Reject the response if uncompressed bytes exceed 10 MB.
3. Compute SHA-256 over the original bytes.
4. Gzip the original bytes.
5. Insert and commit `aa_raw_snapshots`.
6. Only then decode JSON and parse the response.

If snapshot persistence fails, parsing must not continue.

### 6.2 Size limits

The application soft limit is:

```env
ARTIFICIAL_ANALYSIS_MAX_RESPONSE_BYTES=10485760
```

Responses larger than the limit fail that dataset and preserve its previous published version. Responses must not be truncated because truncated JSON cannot support reliable replay.

Deployment documentation must require:

```text
MySQL max_allowed_packet >= 16MB
```

The compressed body is stored in `LONGBLOB`, but the application limit remains 10 MB uncompressed.

### 6.3 Replay

A reparse operation:

- creates a new `aa_sync_runs` record with `trigger_type=reparse`;
- reads and decompresses selected existing snapshots;
- does not call Artificial Analysis;
- runs the current parser and publication logic;
- creates a new immutable dataset version.

## 7. Parsing

### 7.1 Common validation

The parser must validate:

- response root is an object;
- `data` is a list;
- required model and score fields match the endpoint schema;
- numeric values are finite;
- model identity is non-empty;
- creator identity follows the rules below;
- duplicate models inside one dataset are rejected or deterministically deduplicated with a recorded warning.

One malformed row does not invalidate an otherwise usable dataset unless more than 10% of rows fail validation. Row failures are recorded in the run log and dataset error metadata.

### 7.2 Ranking

Ranks are calculated locally after validation:

- Intelligence Index and Elo: descending score.
- AA WER Index: ascending score because it is a word-error-rate metric and lower error is better.
- Null scores sort after scored models and are excluded from numbered ranks by default.
- Ties use score, then model name, then external ID for deterministic ordering.

### 7.3 Creator identity and region

Official contracts:

- Media `model_creator.id` and `model_creator.name` are required.
- Free language `model_creator` may be null; when present, `id` and `name` are required.
- Pro language responses may include `model_creator.country`.

Region resolution order:

1. If the response contains an official country and it equals `cn`, upsert `source=official_country` and assign `cn`.
2. Match non-empty `creator_external_id` exactly.
3. If a non-empty ID is not known, insert an `observed` creator row with `region_code=unknown`; do not fall back to its name.
4. If the ID is absent, normalize the creator name with Unicode case folding, trim, and whitespace collapse, then perform exact equality against `normalized_name`.
5. Do not use substring, suffix, fuzzy, transliteration, or alias matching.
6. Unmatched creators receive `unknown` and are excluded from the China dataset.

Before enabling scheduled publication, a real Free API response must be collected and a creator coverage report produced:

- total unique creators;
- creators resolved by ID;
- creators resolved by exact normalized name;
- unresolved creators;
- percentage of language entries eligible for regional classification.

## 8. China language-model dataset

The China dataset is derived only after the global language dataset parses successfully.

Steps:

1. Select global language entries with `creator_region=cn`.
2. Preserve the original scores and metrics.
3. Recalculate rank within the selected subset.
4. Create a separate immutable `language_china` dataset linked to the same raw snapshot IDs.
5. Publish the global dataset when it is valid.
6. Publish the China dataset in a separate transaction when it is non-empty and valid. A China derivation failure must not block a valid global update.

An empty China result is a parsing/configuration failure. It must not replace an existing published China dataset.

## 9. Publication and failure behavior

Publication is per dataset.

Within one transaction:

1. Verify the new dataset status is `ready`.
2. Lock the currently published row for the dataset key.
3. Mark the old published dataset `superseded`.
4. Mark the new dataset `published` and set `published_at`.
5. Commit.

Failure behavior:

- HTTP, snapshot, parsing, or publication failure never deletes the current published dataset.
- A partially successful run publishes successful datasets and reports `partial`.
- If nothing publishes, the run is `failed` or `quota_exhausted`.
- Duplicate normalized data may reuse the current published dataset and record the run as successful without inserting duplicate entries.

## 10. Execution model

### 10.1 Scheduled synchronization

APScheduler adds two Asia/Shanghai jobs:

- `08:30`
- `20:30`

Both call the same standalone sync entry point. The entry point creates and closes its own `SessionLocal`.

### 10.2 Manual synchronization

Admin endpoint:

```http
POST /api/admin/artificial-analysis/sync
```

Behavior:

1. Validate admin access and configuration.
2. Open a short-lived dedicated database connection and acquire the synchronization lock.
3. Check for an existing `pending` or `running` run.
4. Insert and commit an `aa_sync_runs` row with `pending`.
5. Release the lock on the same dedicated connection.
6. Register a FastAPI `BackgroundTasks` callback with the run ID.
7. Return `202 Accepted` with the run record.

The background callback opens a new `SessionLocal`; it never uses the request Session.

### 10.3 Mutual exclusion

The synchronization service uses MySQL `GET_LOCK` with a bounded timeout. Because MySQL advisory locks belong to a database connection, lock acquisition, protected work, `RELEASE_LOCK`, and connection close must use the same dedicated SQLAlchemy `Connection`. The lock name is stable and application-prefixed.

The background callback reacquires this lock before moving its run from `pending` to `running`. It also verifies that its run is still the oldest active run. Scheduled synchronization acquires the same lock before creating a run.

If the lock is unavailable:

- the admin endpoint returns `409 Conflict` with `active_run_id`;
- a scheduled invocation logs and exits without consuming quota.

Redis is not used for this critical lock because MySQL is the authoritative store and the feature must work when Redis is disabled.

### 10.4 Abandoned runs

The service updates `heartbeat_at` between network requests, parsing, and publication.

At application startup and before a new run, `pending` or `running` rows with a heartbeat older than 30 minutes are marked `abandoned`. Their unpublished datasets remain available for inspection but are never served.

## 11. Backend integration

### 11.1 Block source type

Add one source type:

```text
artificial_analysis_ranking
```

Its `source_config` is:

```json
{
  "dataset_key": "language_global",
  "display_fields": ["model", "creator", "score"]
}
```

Allowed dataset keys are fixed by the backend enum.

### 11.2 Database-only block resolution

`blocks.py` must use a named constant:

```python
DB_SOURCE_TYPES = {
    "topic",
    "raw",
    "eastmoney_longhu",
    "tonghuashun_news",
    "artificial_analysis_ranking",
}
```

The resolver queries only the latest `published` dataset for the configured key, orders by rank, and applies `display_count`.

This source type must never enter the live adapter executor and must reject a missing Session.

### 11.3 Public response

Each item returned to the frontend includes:

```json
{
  "id": 1,
  "rank": 1,
  "model": "Model name",
  "title": "Model name",
  "creator": "Creator name",
  "subtitle": "Creator name",
  "score": 42.0,
  "score_type": "intelligence_index",
  "ci_95": null,
  "metrics": {},
  "captured_at": "2026-06-11T20:30:00",
  "source_url": "https://artificialanalysis.ai/"
}
```

Each serialized block adds a `meta` object alongside `data`:

```json
{
  "dataset_key": "language_global",
  "score_type": "intelligence_index",
  "captured_at": "2026-06-11T20:30:00",
  "source_name": "Artificial Analysis",
  "source_url": "https://artificialanalysis.ai/",
  "scope_note": null,
  "is_stale": false
}
```

`scope_note` contains the China-ranking attribution when applicable. `is_stale` is true when the published capture time is older than 36 hours. Attribution and dataset metadata are not repeated on every row solely for rendering.

## 12. Admin API

Add:

```http
GET  /api/admin/artificial-analysis/status
GET  /api/admin/artificial-analysis/runs
GET  /api/admin/artificial-analysis/runs/{run_id}
GET  /api/admin/artificial-analysis/creators
PUT  /api/admin/artificial-analysis/creators/{creator_external_id}
POST /api/admin/artificial-analysis/sync
POST /api/admin/artificial-analysis/reparse/{snapshot_id}
```

The first release requires only operational controls:

- configuration present/missing;
- latest quota state;
- latest successful sync;
- active run;
- per-dataset published version and capture time;
- run details and errors;
- manual full sync;
- snapshot reparse.
- list observed and unresolved creators;
- update an observed creator to `cn` or `other`, followed by explicit snapshot reparse.

The first release does not include a creator-region management UI. Initial known mappings may be seeded by migration. Creators discovered from a real response are stored as `observed/unknown` and can be classified through the admin API. A management UI can be justified later by actual maintenance volume.

## 13. Frontend

### 13.1 Layout editor

Replace the DataLearner AI ranking choice with an Artificial Analysis group:

- 全球大语言模型
- 中国大语言模型
- 文生图
- 文生视频
- 图生视频
- 文本转语音
- 语音转文本

These options all save `source_type=artificial_analysis_ranking` with a different `dataset_key`.

The editor exposes:

- ranking type;
- display count;
- supported display fields.

It does not expose raw source IDs, topic IDs, live refresh controls, or API credentials.

### 13.2 Public ranking component

Use a unified ranking table with:

- rank icon for the first three rows;
- model name;
- creator;
- primary score and score label;
- optional confidence interval or secondary metric;
- captured time;
- visible Artificial Analysis attribution.

The component must handle:

- no published dataset;
- stale but usable dataset;
- partial sync where another ranking remains old;
- unknown creator region;
- mobile horizontal constraints without requiring page-level horizontal scrolling.

## 14. Migration and rollout

1. Add Alembic tables and indexes.
2. Add environment variables with synchronization disabled by default.
3. Configure a Free API key locally.
4. Run one manual collection and preserve the raw snapshots.
5. Review creator coverage and classify unresolved creators through the admin API.
6. Reparse the saved language snapshots if region mappings changed.
7. Verify all seven published datasets in MySQL.
8. In the layout editor, modify the AI page's draft blocks from `datalearner_aa_index` to `artificial_analysis_ranking`.
9. Re-publish the AI page so published blocks are regenerated from the updated drafts.
10. Keep the DataLearner adapter for one release as rollback support.
11. Enable the twice-daily scheduler only after quota and dataset monitoring is verified.

Alembic must not directly rewrite published `page_blocks`.

## 15. Retention

Initial retention:

- `aa_sync_runs`: 180 days.
- `aa_raw_snapshots`: 90 days.
- Published datasets: retain indefinitely.
- Superseded datasets and entries: 180 days.
- Failed unpublished datasets: 30 days.

Cleanup must never delete snapshots referenced by retained datasets.

## 16. Testing

### 16.1 Collector tests

- sends `x-api-key` without logging it;
- follows dynamic language pagination;
- persists raw bytes before parsing;
- saves safe rate-limit headers;
- stops at the quota reserve;
- handles `429` and `Retry-After`;
- rejects responses over 10 MB;
- does not parse when snapshot persistence fails.

### 16.2 Parser tests

- parses each of the six upstream endpoint shapes;
- creates seven normalized datasets including derived China language;
- handles null language creators;
- matches creator ID exactly;
- uses normalized-name exact fallback only when ID is absent;
- excludes unknown creators from China ranking;
- produces deterministic ranks and hashes;
- rejects an empty derived China dataset;
- ranks Speech-to-Text entries by ascending AA WER Index.

### 16.3 Publication tests

- atomically replaces one published dataset;
- preserves the old dataset after a failed run;
- permits partial run publication;
- avoids duplicate entries for identical normalized data;
- marks stale running jobs abandoned.

### 16.4 API and block tests

- manual sync returns `202`;
- overlapping manual sync returns `409` with `active_run_id`;
- background callback uses an independent Session;
- `artificial_analysis_ranking` is resolved in the database path;
- block resolution never invokes an upstream HTTP request;
- public page returns the latest published dataset;
- source attribution and capture time are present.

### 16.5 Frontend tests

- all seven ranking choices create the correct block config;
- ranking table renders global and China datasets;
- first three rows retain ranking icons;
- attribution is visible;
- empty and stale states render correctly;
- mobile rendering has no page-level horizontal overflow.

## 17. Deployment checks

- Run `alembic upgrade head`.
- Confirm `max_allowed_packet >= 16MB`.
- Set the API key only in the backend environment.
- Start with `ARTIFICIAL_ANALYSIS_SYNC_ENABLED=false`.
- Run and inspect one manual sync.
- Verify the response headers report the expected Free tier and remaining quota.
- Confirm frontend requests do not produce Artificial Analysis traffic.
- Enable scheduled synchronization after the draft AI blocks have been updated and published.
