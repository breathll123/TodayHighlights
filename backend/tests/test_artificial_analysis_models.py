from app.core.config import Settings
from app.models.entities import (
    AACreatorRegion,
    AARankingDataset,
    AARankingEntry,
    AARawSnapshot,
    AASyncRun,
)


def test_artificial_analysis_settings_have_safe_defaults() -> None:
    isolated = Settings(
        app_secret_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        _env_file=None,
    )
    assert isolated.artificial_analysis_api_base == "https://artificialanalysis.ai/api/v2"
    assert isolated.artificial_analysis_sync_enabled is False
    assert isolated.artificial_analysis_quota_reserve == 2
    assert isolated.artificial_analysis_max_response_bytes == 10 * 1024 * 1024


def test_artificial_analysis_tables_are_registered() -> None:
    assert AASyncRun.__tablename__ == "aa_sync_runs"
    assert AARawSnapshot.__tablename__ == "aa_raw_snapshots"
    assert AARankingDataset.__tablename__ == "aa_ranking_datasets"
    assert AARankingEntry.__tablename__ == "aa_ranking_entries"
    assert AACreatorRegion.__tablename__ == "aa_creator_regions"
