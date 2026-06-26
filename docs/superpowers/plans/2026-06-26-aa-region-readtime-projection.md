# AA 区域归类读时投影 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把中国榜从「同步时冻结的快照」改为「读最新全球榜 + 实时归类」的投影，使关键字/人工 override 改完即生效，无需手动同步。

**Architecture:** 新增单一共享判定 `classify_region`（人工 override 优先，否则本地关键字实时判定）。`get_published_ranking("language_china")` 不再读已存中国榜，而是取最新已发布 `language_global` 快照、实时归类、筛 cn、重排、限量。同步不再产出中国榜；上游全球榜快照不变。

**Tech Stack:** FastAPI + SQLAlchemy 2.0；后端测试 SQLite 内存（`APP_SECRET_KEY=... REDIS_ENABLED=false python3 -m pytest`）。

## Global Constraints

- 最高规格实现，每个功能有清晰边界、可测试、配套测试齐全（CLAUDE.md 质量约束）。
- 不动上游 `language_global` 的抓取、快照、版本化、发布；不改前端、不改区块 `source_config`、不改 `dataset_key="language_china"` 的读契约。
- 人工 override 用 `aa_creator_regions.source == "manual"` 标识；其 `region_code ∈ {"cn","other"}`（见 `AACreatorRegionUpdate`）。自动判定产出 `"cn"/"unknown"`。中国榜筛选恒为 `== "cn"`。
- 全球榜读路径**不变**：`_serialize_entry` 不输出 `creator_region`，无消费者，不在此现算（YAGNI）。
- `is_chinese_creator` 已在 `repository.py` 顶部 import（`from ...parser import ... is_chinese_creator`）。
- 后端测试命令：`cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest <path> -v`
- 提交信息结尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `backend/app/services/artificial_analysis/repository.py` (修改) | 新增 `classify_region`/`load_manual_overrides`/`_china_projection`；`get_published_ranking` 路由中国榜到投影 |
| `backend/app/services/artificial_analysis/sync.py` (修改) | 删除中国榜 derive/store/publish 段及其 import |
| `backend/app/services/blocks.py` (修改) | `_published_aa_dataset_updated_at` 把 china 映射到 global |
| `backend/app/api/artificial_analysis_admin.py` (修改) | `list_creators` 返回实时 region |
| `backend/tests/test_aa_region_projection.py` (新建) | 全部新测试 |

---

## Task 1: `classify_region` + `load_manual_overrides`

**Files:**
- Modify: `backend/app/services/artificial_analysis/repository.py`（在 `_serialize_entry` 之前新增两个函数）
- Test: `backend/tests/test_aa_region_projection.py`（新建，先放纯函数测试）

**Interfaces:**
- Produces:
  - `classify_region(creator_external_id: str | None, creator_name: str | None, overrides: dict[str, str]) -> str`
  - `load_manual_overrides(session: Session) -> dict[str, str]`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_aa_region_projection.py`:

```python
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import AACreatorRegion, AARankingDataset, AARankingEntry
from app.services.artificial_analysis.repository import (
    classify_region, load_manual_overrides,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_classify_region_auto_recognizes_z_ai():
    assert classify_region("c-zai", "Z AI", {}) == "cn"


def test_classify_region_auto_unknown_for_foreign():
    assert classify_region("c-openai", "OpenAI", {}) == "unknown"


def test_classify_region_manual_override_wins_by_id():
    # 人工把一个本会判 unknown 的创作者钉成 cn
    assert classify_region("c-x", "Mystery Labs", {"c-x": "cn"}) == "cn"


def test_classify_region_manual_override_can_force_other_over_auto_cn():
    # 关键字会判 cn，但人工 override 为 other → 以 override 为准
    assert classify_region("c-zai", "Z AI", {"c-zai": "other"}) == "other"


def test_classify_region_override_by_normalized_name():
    assert classify_region(None, "Some Name", {"some name": "cn"}) == "cn"


def test_load_manual_overrides_only_manual_rows():
    with _session() as s:
        s.add(AACreatorRegion(creator_external_id="c-a", canonical_name="A",
                              normalized_name="a", region_code="cn", source="manual"))
        s.add(AACreatorRegion(creator_external_id="c-b", canonical_name="B",
                              normalized_name="b", region_code="cn", source="observed"))
        s.commit()
        overrides = load_manual_overrides(s)
        assert overrides == {"c-a": "cn", "a": "cn"}  # observed 行不计入
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -v`
Expected: FAIL — `ImportError: cannot import name 'classify_region'`.

- [ ] **Step 3: 实现两个函数**

在 `repository.py`，紧接 `_serialize_entry` 定义之前插入：

```python
def classify_region(
    creator_external_id: str | None,
    creator_name: str | None,
    overrides: dict[str, str],
) -> str:
    """区域判定的唯一真相：人工 override 优先，否则本地关键字实时判定。

    overrides: {creator_external_id 或 normalized_name -> region_code}，仅含 source='manual'。
    """
    key_id = (creator_external_id or "").strip()
    key_name = (creator_name or "").lower().strip()
    if key_id and key_id in overrides:
        return overrides[key_id]
    if key_name and key_name in overrides:
        return overrides[key_name]
    return "cn" if is_chinese_creator(creator_external_id, creator_name) else "unknown"


def load_manual_overrides(session: Session) -> dict[str, str]:
    """加载人工 override（source='manual'），按 external_id 与 normalized_name 双键索引。"""
    out: dict[str, str] = {}
    for cr in session.scalars(select(AACreatorRegion).where(AACreatorRegion.source == "manual")):
        if cr.creator_external_id:
            out[cr.creator_external_id] = cr.region_code
        if cr.normalized_name:
            out[cr.normalized_name] = cr.region_code
    return out
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -v`
Expected: PASS（6 passed）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/artificial_analysis/repository.py tests/test_aa_region_projection.py
git commit -m "feat(aa): classify_region + load_manual_overrides（区域判定唯一真相）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 中国榜读时投影 `_china_projection` + 路由

**Files:**
- Modify: `backend/app/services/artificial_analysis/repository.py`（新增 `_china_projection`；`get_published_ranking` 顶部加路由）
- Test: `backend/tests/test_aa_region_projection.py`（追加）

**Interfaces:**
- Consumes: `classify_region`, `load_manual_overrides`, `_serialize_entry`（已存在）。
- Produces: `_china_projection(session: Session, limit: int) -> tuple[list[dict], dict | None]`；`get_published_ranking(session, "language_china", limit)` 走投影。

- [ ] **Step 1: 写失败测试（追加到 test_aa_region_projection.py）**

顶部补 import：

```python
from app.services.artificial_analysis.repository import get_published_ranking
```

追加 seed 助手 + 测试：

```python
def _seed_global(s, rows):
    """rows: list of (model_name, creator_external_id, creator_name, rank, score)."""
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
    with _session() as s:
        _seed_global(s, [
            ("GPT", "c-openai", "OpenAI", 1, 1400),
            ("GLM", "c-zai", "Z AI", 2, 1380),     # 中国（关键字 z ai 实时命中）
            ("Qwen3", "c-qwen", "Qwen", 3, 1370),  # 中国
        ])
        items, meta = get_published_ranking(s, "language_china", 50)
        assert [i["creator"] for i in items] == ["Z AI", "Qwen"]
        assert [i["rank"] for i in items] == [1, 2]  # 在中国集合内重排
        assert meta["dataset_key"] == "language_china"


def test_china_projection_respects_manual_override():
    with _session() as s:
        _seed_global(s, [("GLM", "c-zai", "Z AI", 1, 1380)])
        s.add(AACreatorRegion(creator_external_id="c-zai", canonical_name="Z AI",
                              normalized_name="z ai", region_code="other", source="manual"))
        s.commit()
        items, _ = get_published_ranking(s, "language_china", 50)
        assert items == []  # 人工标 other → 不进中国榜


def test_china_projection_empty_when_no_cn():
    with _session() as s:
        _seed_global(s, [("GPT", "c-openai", "OpenAI", 1, 1400)])
        items, meta = get_published_ranking(s, "language_china", 50)
        assert items == []
        assert meta["dataset_key"] == "language_china"


def test_china_projection_none_when_no_global_published():
    with _session() as s:
        items, meta = get_published_ranking(s, "language_china", 50)
        assert items == []
        assert meta is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -k china -v`
Expected: FAIL（投影未实现，china 仍走旧路径返回空/None 不符）。

- [ ] **Step 3: 实现 `_china_projection` 并在 `get_published_ranking` 顶部路由**

在 `repository.py` `get_published_ranking` 定义**之前**新增：

```python
def _china_projection(session: Session, limit: int) -> tuple[list[dict], dict | None]:
    """中国榜 = 对最新已发布全球榜的读时投影：实时归类 → 筛 cn → 重排 → 限量。"""
    g = session.scalar(
        select(AARankingDataset).where(
            AARankingDataset.dataset_key == "language_global",
            AARankingDataset.status == "published",
        ).order_by(AARankingDataset.published_at.desc()).limit(1)
    )
    if g is None:
        return [], None

    overrides = load_manual_overrides(session)
    entries = list(session.scalars(
        select(AARankingEntry)
        .where(AARankingEntry.dataset_id == g.id)
        .order_by(AARankingEntry.rank.is_(None), AARankingEntry.rank.asc())
    ))

    out: list[dict] = []
    rank = 1
    for e in entries:
        if classify_region(e.creator_external_id, e.creator_name, overrides) != "cn":
            continue
        item = _serialize_entry(e)
        item["rank"] = rank if e.score is not None else None
        out.append(item)
        if e.score is not None:
            rank += 1
        if len(out) >= limit:
            break

    is_stale = g.captured_at < datetime.utcnow() - timedelta(hours=settings.artificial_analysis_stale_hours)
    meta = {
        "dataset_key": "language_china",
        "score_type": g.score_type,
        "captured_at": g.captured_at.isoformat() if g.captured_at else None,
        "source_name": "Artificial Analysis",
        "source_url": "https://artificialanalysis.ai/",
        "scope_note": "中国模型范围由今日看点根据模型厂商归属整理，原始评分来自 Artificial Analysis。",
        "is_stale": is_stale,
    }
    return out, meta
```

在 `get_published_ranking` 函数体**第一行**（docstring 之后）加路由：

```python
    """Return ranked items and metadata for a published dataset."""
    if dataset_key == "language_china":
        return _china_projection(session, limit)
```

（其余 global/其它 key 的逻辑保持不变。）

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -v`
Expected: PASS（全部，含 Task 1 的 6 个 + 4 个 china）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/artificial_analysis/repository.py tests/test_aa_region_projection.py
git commit -m "feat(aa): 中国榜改为读时投影（取全球榜快照实时归类，改完即生效）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 区块新鲜度 china → global 映射

**Files:**
- Modify: `backend/app/services/blocks.py`（`_published_aa_dataset_updated_at`）
- Test: `backend/tests/test_aa_region_projection.py`（追加）

**Interfaces:**
- Consumes: `_published_aa_dataset_updated_at(session, block)`（已存在）。

- [ ] **Step 1: 写失败测试（追加）**

顶部补 import：

```python
from app.models.entities import PageBlock
from app.services.blocks import _published_aa_dataset_updated_at
```

追加：

```python
def test_china_block_freshness_uses_global_published_at():
    with _session() as s:
        ds = _seed_global(s, [("GPT", "c-openai", "OpenAI", 1, 1400)])
        block = PageBlock(
            page_route="/topics/ai", title="中国大模型榜", source_type="artificial_analysis_ranking",
            source_config={"dataset_keys": ["language_china"]}, display_count=10, status="published",
        )
        s.add(block)
        s.commit()
        assert _published_aa_dataset_updated_at(s, block) == ds.published_at
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -k freshness -v`
Expected: FAIL（china 没有已发布数据集 → 返回 None ≠ global published_at）。

- [ ] **Step 3: 实现映射**

`blocks.py` 的 `_published_aa_dataset_updated_at`，在 `keys = [str(key) for key in keys if key]` 之后、`if not keys:` 之前，插入一行把 china 映射成 global：

```python
    keys = [str(key) for key in keys if key]
    # 中国榜是全球榜的读时投影，自身不再发布数据集；新鲜度按全球榜的发布时间。
    keys = ["language_global" if k == "language_china" else k for k in keys]
    if not keys:
        return None
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -k freshness -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/blocks.py tests/test_aa_region_projection.py
git commit -m "fix(aa): 中国榜区块新鲜度按全球榜发布时间（投影无自身快照）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 后台创作者列表实时 region

**Files:**
- Modify: `backend/app/api/artificial_analysis_admin.py`（`list_creators`）
- Test: `backend/tests/test_aa_region_projection.py`（追加，走函数级直接调用）

**Interfaces:**
- Consumes: `classify_region`, `load_manual_overrides`。

- [ ] **Step 1: 写失败测试（追加）**

顶部补 import：

```python
from app.api.artificial_analysis_admin import list_creators
```

追加：

```python
def test_list_creators_returns_live_region():
    with _session() as s:
        # observed 行：表里存的是旧的 unknown，但实时应判为 cn
        s.add(AACreatorRegion(creator_external_id="c-zai", canonical_name="Z AI",
                              normalized_name="z ai", region_code="unknown", source="observed"))
        # manual 行：override 为 other
        s.add(AACreatorRegion(creator_external_id="c-x", canonical_name="X Labs",
                              normalized_name="x labs", region_code="other", source="manual"))
        s.commit()
        result = {c.canonical_name: c.region_code for c in list_creators(session=s)}
        assert result["Z AI"] == "cn"      # 实时判定覆盖存量 unknown
        assert result["X Labs"] == "other" # 人工 override 原样
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -k list_creators -v`
Expected: FAIL（`Z AI` 返回存量 "unknown"）。

- [ ] **Step 3: 实现实时 region**

`artificial_analysis_admin.py`，在文件已有 import 区补：

```python
from app.services.artificial_analysis.repository import classify_region, load_manual_overrides
```

把 `list_creators` 改为：

```python
@router.get("/creators", response_model=list[AACreatorRegionRead])
def list_creators(session: Session = Depends(get_session)) -> list[AACreatorRegionRead]:
    overrides = load_manual_overrides(session)
    creators = session.scalars(select(AACreatorRegion).order_by(AACreatorRegion.canonical_name)).all()
    return [AACreatorRegionRead(
        id=c.id,
        creator_external_id=c.creator_external_id,
        canonical_name=c.canonical_name,
        normalized_name=c.normalized_name,
        region_code=classify_region(c.creator_external_id, c.canonical_name, overrides),
        source=c.source,
        notes=c.notes,
    ) for c in creators]
```

> 注：`classify_region` 对 manual 行命中 overrides → 返回 override 值；对 observed 行 → 返回实时自动判定。统一一行覆盖两种情况。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_aa_region_projection.py -k list_creators -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/api/artificial_analysis_admin.py tests/test_aa_region_projection.py
git commit -m "feat(aa): 后台创作者列表用实时区域判定，override 改完即一致

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 同步去掉中国榜物化

**Files:**
- Modify: `backend/app/services/artificial_analysis/sync.py`

**Interfaces:**
- 无新接口。删除 `language_global` 分支里派生/存储/发布 `language_china` 的整段。

> 本任务是删除，验证由 Task 2 的投影测试（证明中国榜无需存量数据集即可工作）+ 全量回归保证。`derive_china_dataset` 纯函数本身保留（仍被 `test_artificial_analysis_parser.py` 独立测试），只摘掉它在 sync 的接线。

- [ ] **Step 1: 删除 sync 中的中国榜派生段**

`sync.py` 删除这一整段（紧接 `publish_dataset(session, dataset.id)` 之后）：

```python
                        # Derive China dataset for language_global
                        if dataset_key == "language_global":
                            try:
                                china = derive_china_dataset(parsed)
                                observe_unknown_creators(session, china.entries)
                                china_ds = store_parsed_dataset(
                                    session,
                                    run_id=run_id,
                                    parsed=china,
                                    snapshot_ids=collected.snapshot_ids,
                                    captured_at=datetime.utcnow(),
                                )
                                session.commit()
                                publish_dataset(session, china_ds.id)
                                completed.append("language_china")
                            except DatasetParseError as exc:
                                log_event(
                                    logger,
                                    channel="application",
                                    category="ai",
                                    event="aa.dataset.failed",
                                    level=logging.WARNING,
                                    dataset_key="language_china",
                                    error_type=type(exc).__name__,
```

并删除该 `except` 块剩余的几行（`reason`/日志收尾，直到这段 `try/except` 结束）。删除后，`for dataset_key in ...` 循环体在 `publish_dataset(session, dataset.id)` 后直接进入下一轮。

> 实施提示：用 Read 打开 `sync.py` 第 ~215-245 行，确认 `try/except` 的确切结束行，整段删除到 except 闭合，保持缩进与外层 `for`/`with` 结构完整。

- [ ] **Step 2: 清理 import**

`sync.py` 第 18 行：
```python
from app.services.artificial_analysis.parser import DatasetParseError, derive_china_dataset, parse_dataset
```
改为（`DatasetParseError`/`derive_china_dataset` 删段后已不再使用）：
```python
from app.services.artificial_analysis.parser import parse_dataset
```

- [ ] **Step 3: 语法校验 + 全量 AA 回归**

Run:
```bash
cd backend && python3 -m py_compile app/services/artificial_analysis/sync.py && \
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false \
  python3 -m pytest tests/test_aa_region_projection.py tests/test_artificial_analysis_parser.py -v
```
Expected: py_compile 无输出；测试全绿（投影证明中国榜照常工作；parser 的 `derive_china_dataset` 测试仍在、仍过）。

> 若 py_compile 或 pytest 报 `DatasetParseError`/`derive_china_dataset` 未定义/未使用，说明删除不彻底或漏删引用——回到 Step 1/2 修正，不要新增引用。

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/services/artificial_analysis/sync.py
git commit -m "refactor(aa): 同步不再物化中国榜（已改为读时投影）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 全量验证 + 文档

**Files:**
- 无新代码——验证 + 文档。

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/ -q`
Expected: 全绿（含新建 `test_aa_region_projection.py` 与既有全部）。

- [ ] **Step 2: 线上回归确认（用户环境）**

部署+重启后，到后台 AI 榜 / `topics/ai` 中国榜确认智谱「Z AI」已出现在中国榜；并确认**未触发任何同步**的情况下，改一次关键字（或后台 override）刷新即生效。

- [ ] **Step 3: 收尾**

无 CLAUDE.md 踩坑需补记（本次为读路径重构，无新迁移、无新事件码）。如需，可在 `## 踩坑记录` 备注：中国榜为 `language_global` 的读时投影，不存在独立 `language_china` 快照，新鲜度按全球榜。

---

## Self-Review

**1. Spec coverage：**
- §1 `classify_region`（override 优先 + 实时） → Task 1 ✓
- §2 读路径中国榜投影；global 路径不变（region 不序列化） → Task 2 ✓
- §3 同步去中国榜物化 → Task 5 ✓
- §4 区块新鲜度 china→global → Task 3 ✓
- §5 后台创作者列表实时 → Task 4 ✓
- §错误处理（无 cn → 空；无全球榜 → None） → Task 2 测试覆盖 ✓
- §测试（classify_region、投影、override 优先与免同步生效、空、新鲜度、后台列表） → Task 1-4 测试 ✓

**2. Placeholder scan：** 无 TBD/TODO；每个代码步骤含完整代码与确切命令。Task 5 Step 1 的"确认 except 结束行"是删除操作的必要现场核对，非占位（已给行号范围与判定方法）。

**3. Type consistency：** `classify_region(creator_external_id, creator_name, overrides)` / `load_manual_overrides(session)->dict[str,str]` / `_china_projection(session, limit)->tuple[list[dict],dict|None]` 在 Task 1/2/4 三处签名一致；override 值域 `{"cn","other"}`、自动 `{"cn","unknown"}`、筛选恒 `=="cn"` 全程一致；`get_published_ranking` 返回 `(list[dict], dict|None)` 不变。

**4. 取舍声明：** `derive_china_dataset` 重构后无生产调用方，但作为纯函数仍被 `test_artificial_analysis_parser.py` 独立测试而保留（避免跨 4 文件删除的风险）；如要彻底清除可作独立后续。中国榜重排逻辑在 `_china_projection` 内按 ORM 行重写（需保留 entry.id，`ParsedRankingEntry` 无此字段，故不复用 `derive_china_dataset`）。
