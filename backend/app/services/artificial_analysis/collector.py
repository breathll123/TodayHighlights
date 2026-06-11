import gzip
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Callable

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AARawSnapshot, AASyncRun
from app.services.artificial_analysis.constants import DatasetDefinition


@dataclass(frozen=True)
class QuotaState:
    tier: str = ""
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None


@dataclass(frozen=True)
class CollectedDataset:
    dataset_key: str
    snapshot_ids: list[int]
    payloads: list[dict]
    tier: str
    source_version: str


class QuotaReserveReached(RuntimeError):
    pass


class UpstreamRateLimited(RuntimeError):
    def __init__(self, retry_after_seconds: int | None):
        super().__init__("Artificial Analysis rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class ResponseTooLarge(RuntimeError):
    pass


def create_default_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.artificial_analysis_request_timeout_seconds,
        follow_redirects=True,
    )


SAFE_HEADERS = {
    "x-aa-tier",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "retry-after",
    "content-type",
}


def _safe_headers(response: httpx.Response) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in response.headers.items():
        if name.lower() in SAFE_HEADERS:
            result[name.lower()] = value
    return result


def _parse_quota_from_headers(headers: dict[str, str]) -> QuotaState:
    tier = headers.get("x-aa-tier", "")
    limit = None
    remaining = None
    reset_at = None

    raw_limit = headers.get("x-ratelimit-limit")
    if raw_limit and raw_limit.isdigit():
        limit = int(raw_limit)

    raw_remaining = headers.get("x-ratelimit-remaining")
    if raw_remaining and raw_remaining.isdigit():
        remaining = int(raw_remaining)

    raw_reset = headers.get("x-ratelimit-reset")
    if raw_reset and raw_reset.isdigit():
        try:
            reset_at = datetime.fromtimestamp(int(raw_reset), tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError):
            pass

    return QuotaState(tier=tier, limit=limit, remaining=remaining, reset_at=reset_at)


class ArtificialAnalysisCollector:
    def __init__(
        self,
        session: Session,
        *,
        client_factory: Callable[[], httpx.Client] = create_default_client,
    ):
        self.session = session
        self.client_factory = client_factory
        self._api_key = settings.artificial_analysis_api_key

    def _check_quota(self, run: AASyncRun) -> None:
        quota = _parse_quota_from_headers({})
        if run.quota_remaining is not None:
            if run.quota_remaining <= settings.artificial_analysis_quota_reserve:
                raise QuotaReserveReached(
                    f"quota remaining {run.quota_remaining} <= reserve {settings.artificial_analysis_quota_reserve}"
                )

    def _persist_snapshot(
        self,
        run: AASyncRun,
        definition: DatasetDefinition,
        page_number: int,
        response: httpx.Response,
        body_bytes: bytes,
    ) -> int:
        compressed = gzip.compress(body_bytes)
        body_sha = sha256(body_bytes).hexdigest()
        safe_hdrs = _safe_headers(response)

        snapshot = AARawSnapshot(
            sync_run_id=run.id,
            dataset_key=definition.key,
            endpoint=definition.endpoint,
            page_number=page_number,
            http_status=response.status_code,
            response_headers_json=safe_hdrs,
            body_compressed=compressed,
            compression="gzip",
            content_type=safe_hdrs.get("content-type", ""),
            body_sha256=body_sha,
            original_size_bytes=len(body_bytes),
            compressed_size_bytes=len(compressed),
            captured_at=datetime.utcnow(),
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot.id

    def collect(self, run: AASyncRun, definition: DatasetDefinition) -> CollectedDataset:
        client = self.client_factory()
        api_base = settings.artificial_analysis_api_base.rstrip("/")
        url = f"{api_base}{definition.endpoint}"

        snapshot_ids: list[int] = []
        payloads: list[dict] = []
        pages_to_fetch = 1
        page = 1
        tier = ""
        source_version = ""
        last_quota: QuotaState | None = None

        try:
            while page <= pages_to_fetch:
                # Quota check before next request (first request always proceeds)
                if page > 1:
                    self._check_quota(run)

                headers = {"x-api-key": self._api_key}
                params = {"page": page} if definition.paginated else {}

                response = client.get(url, headers=headers, params=params)

                # Check rate limit
                if response.status_code == 429:
                    retry_after = None
                    raw = response.headers.get("retry-after")
                    if raw and raw.isdigit():
                        retry_after = int(raw)
                    raise UpstreamRateLimited(retry_after)

                # Check size before reading all bytes
                if response.status_code == 200:
                    content_length = response.headers.get("content-length")
                    if content_length and content_length.isdigit():
                        if int(content_length) > settings.artificial_analysis_max_response_bytes:
                            raise ResponseTooLarge(
                                f"Response {int(content_length)} bytes exceeds limit"
                            )

                body_bytes = response.read()
                response.close()

                # Persist snapshot before decoding
                snapshot_id = self._persist_snapshot(run, definition, page, response, body_bytes)
                snapshot_ids.append(snapshot_id)

                # Update quota from response headers
                safe_hdrs = _safe_headers(response)
                last_quota = _parse_quota_from_headers(safe_hdrs)
                run.quota_tier = last_quota.tier or run.quota_tier
                run.quota_limit = last_quota.limit
                run.quota_remaining = last_quota.remaining
                run.quota_reset_at = last_quota.reset_at
                run.request_count = (run.request_count or 0) + 1
                run.heartbeat_at = datetime.utcnow()

                # Decode after persistence
                if response.status_code != 200:
                    response.request = None  # avoid logging api key
                    break

                if not body_bytes:
                    break

                try:
                    payload = json.loads(body_bytes)
                except Exception:
                    # Mark snapshot parse_status failed but continue
                    self.session.commit()
                    break

                if not isinstance(payload, dict):
                    break

                payloads.append(payload)
                tier = str(payload.get("tier") or tier)
                source_version = str(payload.get("intelligence_index_version") or source_version)

                # Handle pagination
                if definition.paginated:
                    pagination = payload.get("pagination")
                    if isinstance(pagination, dict) and pagination.get("has_more"):
                        pages_to_fetch = max(pages_to_fetch, page + 1)
                page += 1

                # Note: quota check moved to top of next loop iteration

        finally:
            client.close()

        self.session.commit()
        return CollectedDataset(
            dataset_key=definition.key,
            snapshot_ids=snapshot_ids,
            payloads=payloads,
            tier=tier,
            source_version=source_version,
        )
