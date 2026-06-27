# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import AACreatorRegion, AARankingDataset, AARankingEntry
from app.services.artificial_analysis.repository import (
    classify_region, load_manual_overrides,
)


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
