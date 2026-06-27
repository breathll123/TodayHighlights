# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import AACreatorRegion, AARankingDataset, AARankingEntry, PageBlock
from app.services.artificial_analysis.repository import (
    classify_region, load_manual_overrides, get_published_ranking,
)
from app.services.blocks import _published_aa_dataset_updated_at


def _session():
    """
    创建一个内存 SQLite 数据库会话，用于单元测试。
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_classify_region_auto_recognizes_z_ai():
    """
    测试自动分类器是否可以通过厂商关键字 (例如 'Z AI') 自动识别判定为中国厂商 (cn)。
    """
    assert classify_region("c-zai", "Z AI", {}) == "cn"


def test_classify_region_auto_unknown_for_foreign():
    """
    测试对于外国厂商 (例如 'OpenAI')，在无人工覆盖时，分类器应默认判定为 unknown。
    """
    assert classify_region("c-openai", "OpenAI", {}) == "unknown"


def test_classify_region_manual_override_wins_by_id():
    """
    测试当存在基于 creator_external_id 的人工覆盖规则时，人工设定优先（即便该厂商在自动识别下属于 unknown）。
    """
    # 人工把一个本会判 unknown 的创作者钉成 cn
    assert classify_region("c-x", "Mystery Labs", {"c-x": "cn"}) == "cn"


def test_classify_region_manual_override_can_force_other_over_auto_cn():
    """
    测试人工覆盖的最高优先权：即便关键字判断其为中国厂商 (cn)，但人工将其 override 覆盖为 other 时，应以 manual other 为准。
    """
    # 关键字会判 cn，但人工 override 为 other → 以 override 为准
    assert classify_region("c-zai", "Z AI", {"c-zai": "other"}) == "other"


def test_classify_region_override_by_normalized_name():
    """
    测试人工覆盖是否可以通过规范化的厂商名称 (normalized_name) 进行匹配和覆盖。
    """
    assert classify_region(None, "Some Name", {"some name": "cn"}) == "cn"


def test_load_manual_overrides_only_manual_rows():
    """
    测试 load_manual_overrides 数据库加载函数，确保只计入人工定义 (source='manual') 的覆盖规则，忽略系统自动检测 (source='observed') 的行。
    """
    with _session() as s:
        s.add(AACreatorRegion(creator_external_id="c-a", canonical_name="A",
                              normalized_name="a", region_code="cn", source="manual"))
        s.add(AACreatorRegion(creator_external_id="c-b", canonical_name="B",
                              normalized_name="b", region_code="cn", source="observed"))
        s.commit()
        overrides = load_manual_overrides(s)
        assert overrides == {"c-a": "cn", "a": "cn"}  # observed 行不计入


def _seed_global(s, rows):
    """
    向测试数据库中写入已发布的全球大模型数据。
    rows 格式为：list of (model_name, creator_external_id, creator_name, rank, score)。
    """
    ds = AARankingDataset(
        sync_run_id=1, dataset_key="language_global", scope="global", score_type="elo",
        status="published", data_sha256="x", captured_at=datetime(2026, 6, 26),
        published_at=datetime(2026, 6, 26),
    )
    s.add(ds)
    s.flush()
    for model, cid, cname, rank, score in rows:
        s.add(AARankingEntry(
            dataset_id=ds.id, model_external_id=model, model_name=model,
            creator_external_id=cid, creator_name=cname, rank=rank, score=score,
            score_type="elo",
        ))
    s.commit()
    return ds


def test_china_projection_filters_and_reranks_without_any_sync():
    """
    测试中国榜的读时投影映射功能，即使在没有任何中国榜单物化同步的条件下，
    也能实时过滤全球榜中的中国厂商并完成相对重新排序。
    """
    with _session() as s:
        _seed_global(s, [
            ("GPT", "c-openai", "OpenAI", 1, 1400),
            ("GLM", "c-zai", "Z AI", 2, 1380),     # 中国厂商 (关键字 z ai 实时命中)
            ("Qwen3", "c-qwen", "Qwen", 3, 1370),  # 中国厂商 (关键字 qwen 实时命中)
        ])
        items, meta = get_published_ranking(s, "language_china", 50)
        assert [i["creator"] for i in items] == ["Z AI", "Qwen"]
        assert [i["rank"] for i in items] == [1, 2]  # 在中国厂商集合内相对重排
        assert meta["dataset_key"] == "language_china"


def test_china_projection_respects_manual_override():
    """
    测试中国榜投影在过滤时是否能实时响应人工覆盖：
    即当人工把原本会被关键字识别为中国厂商 (cn) 的 'Z AI' 手动覆盖为 'other' 时，
    读取中国榜时该厂商应实时不再出现在列表中。
    """
    with _session() as s:
        _seed_global(s, [("GLM", "c-zai", "Z AI", 1, 1380)])
        s.add(AACreatorRegion(creator_external_id="c-zai", canonical_name="Z AI",
                              normalized_name="z ai", region_code="other", source="manual"))
        s.commit()
        items, _ = get_published_ranking(s, "language_china", 50)
        assert items == []  # 人工标 other → 不应出现在中国大模型榜中


def test_china_projection_empty_when_no_cn():
    """
    测试当最新全球榜中没有任何创作者被标记为中国厂商时，读取中国榜应正常返回空列表。
    """
    with _session() as s:
        _seed_global(s, [("GPT", "c-openai", "OpenAI", 1, 1400)])
        items, meta = get_published_ranking(s, "language_china", 50)
        assert items == []
        assert meta["dataset_key"] == "language_china"


def test_china_projection_none_when_no_global_published():
    """
    测试当数据库中没有任何已发布的全球榜单时，读取中国榜投影应返回空列表且元数据为 None。
    """
    with _session() as s:
        items, meta = get_published_ranking(s, "language_china", 50)
        assert items == []
        assert meta is None


def test_china_block_freshness_uses_global_published_at():
    """
    测试当获取中国榜大模型区块的新鲜度时间戳时，由于中国榜没有物化数据集，
    系统应能正确路由到使用全球榜数据集的发布时间 published_at 作为新鲜度判定。
    """
    with _session() as s:
        ds = _seed_global(s, [("GPT", "c-openai", "OpenAI", 1, 1400)])
        block = PageBlock(
            page_route="/topics/ai", title="中国大模型榜", source_type="artificial_analysis_ranking",
            source_config={"dataset_keys": ["language_china"]}, display_count=10, status="published",
        )
        s.add(block)
        s.commit()
        assert _published_aa_dataset_updated_at(s, block) == ds.published_at
