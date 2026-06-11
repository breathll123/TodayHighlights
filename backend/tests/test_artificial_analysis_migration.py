from pathlib import Path


def test_artificial_analysis_migration_defines_all_tables() -> None:
    text = Path("migrations/versions/20260611_0012_artificial_analysis_rankings.py").read_text()
    assert 'revision: str = "0012"' in text
    assert 'down_revision: Union[str, None] = "0011"' in text
    for table in (
        "aa_sync_runs",
        "aa_raw_snapshots",
        "aa_ranking_datasets",
        "aa_ranking_entries",
        "aa_creator_regions",
    ):
        assert f'op.create_table(\n        "{table}"' in text
