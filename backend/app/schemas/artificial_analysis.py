from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AASyncRunRead(BaseModel):
    id: int
    trigger_type: str
    status: str
    requested_datasets: list[str]
    completed_datasets: list[str]
    failed_datasets: list[dict[str, Any]]
    request_count: int
    quota_tier: str
    quota_limit: int | None
    quota_remaining: int | None
    quota_reset_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str
    created_at: datetime


class AACreatorRegionRead(BaseModel):
    id: int
    creator_external_id: str | None
    canonical_name: str
    normalized_name: str
    region_code: str
    source: str
    notes: str


class AACreatorRegionUpdate(BaseModel):
    region_code: Literal["cn", "other"]
    notes: str = ""


class AACreatorCoverageRead(BaseModel):
    total_unique_creators: int
    resolved_by_id: int
    resolved_by_name: int
    unresolved: int
    classified_entry_percent: float


class AADatasetStatusRead(BaseModel):
    dataset_key: str
    status: str
    entry_count: int
    captured_at: datetime | None
    published_at: datetime | None
    is_stale: bool


class AAStatusRead(BaseModel):
    configured: bool
    sync_enabled: bool
    quota_tier: str
    quota_limit: int | None
    quota_remaining: int | None
    quota_reset_at: datetime | None
    active_run: AASyncRunRead | None
    latest_successful_run: AASyncRunRead | None
    datasets: list[AADatasetStatusRead]
    creator_coverage: AACreatorCoverageRead


class AAManualSyncRequest(BaseModel):
    dataset_keys: list[str] | None = None


class AASyncRunListRead(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AASyncRunRead]
