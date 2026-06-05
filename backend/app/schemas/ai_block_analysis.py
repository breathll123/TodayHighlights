from datetime import datetime

from pydantic import BaseModel


class BlockAnalysisValidated(BaseModel):
    summary_points: list[str]
    key_changes: list[str]
    risk_points: list[str]
    related_entities: list[str]
    confidence: float


class BlockAnalysisEvidenceRead(BaseModel):
    title: str
    source: str = ""
    published_at: str | None = None
    url: str | None = None


class BlockAnalysisRead(BaseModel):
    id: int
    page_route: str
    block_id: int
    block_title: str
    status: str
    summary_points: list[str]
    key_changes: list[str]
    risk_points: list[str]
    related_entities: list[str]
    evidence_refs: list[BlockAnalysisEvidenceRead]
    generated_by_model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    token_estimated: bool = False
    generated_at: datetime | None = None
    expires_at: datetime | None = None
