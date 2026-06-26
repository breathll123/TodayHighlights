# AA 创作者区域归类 — 读时投影重构 设计

- 日期：2026-06-26
- 状态：已与用户确认设计，待写实施计划
- 范围：把「中国厂商归类 + 中国榜」从 sync 时物化、改为读时投影，使关键字/人工 override 改完即生效，无需手动同步。

## 背景与问题

Artificial Analysis（AA）榜单里，「哪些创作者是中国厂商」是本项目自己的编辑性归类，由本地代码 `is_chinese_creator(creator_id, creator_name)`（一张关键字子串匹配表）决定。中国榜 `language_china` 是在此归类基础上派生的。

当前实现把这个归类**物化**进了上游快照、并**绑定到爬虫同步的生命周期**：

```
parser.cn_keywords ──(仅同步时)──► aa_creator_regions.region_code（每个创作者）
   └ load_creator_regions: 只把 region_code="unknown" 升级成 "cn"
       └ parse_dataset: 给每条 aa_ranking_entries.creator_region 盖章
           └ derive_china_dataset: 筛 cn → 生成 language_china
               └ store_parsed_dataset + publish: 存成不可变已发布快照
                   └ 前端按 dataset_key 读最新已发布快照
```

后果：改一个关键字（纯本地、确定性、零 I/O 的归类）后，库里已存的 `unknown`/中国榜快照不会自己更新——必须 ① 部署新代码并重启进程，② 再跑一次**全量上游同步**才会重算。一个本该「改完即生效」的本地筛选被迫等爬取。

实测佐证：智谱现在在 AA 里叫 **"Z AI"**（不再叫 Zhipu），其 `aa_creator_regions` 行为 `Z AI | <uuid> | unknown | observed`。关键字 `"z ai"` 子串能匹配 `"z ai"`（"Z AI" 小写），本应升级为 cn，但因物化+同步耦合而未生效。

## 根本设计错误

两类性质不同的数据被焊进了同一条生命周期：

| | 上游评分（AA 分数） | 本地区域归类 + 中国榜 |
|---|---|---|
| 来源 | 外部、需爬取、限流 | 本地代码里的关键字表 |
| 性质 | I/O、慢、会变 | 纯函数、确定性、零 I/O |
| 应如何存 | 快照、不可变、按版本留档 | **读时投影，永远跟随最新代码** |

物化只在「计算昂贵 / 非确定 / 需冻结审计」时才值得；区域归类三者都不占。修复方向：**把上游真相的快照与本地编辑性的投影解耦**——快照保持不可变、照常同步；归类与中国榜改为读时计算。

## 目标

- 改关键字或人工 override 后，**下一次页面读取即生效**，无需手动同步、无需按钮。
- 上游分数快照保持不可变、按版本留档（不退化）。
- 人工 override（后台手动指定区域）永远优先于自动关键字判定，且同样改完即生效。
- 全站区域归类一致（中国榜、全球榜、后台创作者列表都用同一判定，且都是实时）。
- 不为省时降质：清晰边界、可测试、配套测试齐全（CLAUDE.md 质量约束）。

## 非目标（YAGNI）

- 不动上游全球榜 `language_global` 的抓取、快照、版本化、发布逻辑。
- 不删历史 `language_china` 存量数据集行（读路径不再使用它们；删除是额外迁移，留着无害）。
- 不改前端、不改区块 `source_config`、不改 `dataset_key="language_china"` 的读契约。
- 暂不加新缓存层（读时投影成本与原先「读已存中国榜」相当，详见性能小节）。

## 设计

### 1. 单一共享判定函数 `classify_region`

新增（放在 `repository.py` 或新建小模块 `region.py`）：

```python
def classify_region(creator_external_id: str | None, creator_name: str | None,
                    overrides: dict[str, str]) -> str:
    """区域判定的唯一真相：人工 override 优先，否则本地关键字实时判定。
    overrides: {creator_external_id 或 normalized_name -> region_code}，仅含 source='manual' 的行。
    """
    key_id = (creator_external_id or "").strip()
    key_name = (creator_name or "").lower().strip()
    if key_id and key_id in overrides:
        return overrides[key_id]
    if key_name and key_name in overrides:
        return overrides[key_name]
    return "cn" if is_chinese_creator(creator_external_id, creator_name) else "unknown"
```

配套加载器：

```python
def load_manual_overrides(session) -> dict[str, str]:
    """加载人工 override（source='manual'），按 external_id 与 normalized_name 双键索引。"""
    out: dict[str, str] = {}
    for cr in session.scalars(select(AACreatorRegion).where(AACreatorRegion.source == "manual")):
        if cr.creator_external_id:
            out[cr.creator_external_id] = cr.region_code
        if cr.normalized_name:
            out[cr.normalized_name] = cr.region_code
    return out
```

### 2. 读路径 `get_published_ranking` 改为实时归类

- `dataset_key == "language_china"` → 调 `_china_projection(session, limit)`：
  1. 取最新**已发布的 `language_global`** 数据集及其**全部** entries（需全量才能筛选+重排，再取前 N）。
  2. 加载 `overrides`，对每条 `classify_region(...)`。
  3. 筛 `== "cn"`，按原 rank 顺序重排 1..N（保留原 entry 的 score/rank 语义：有 score 才占名次，沿用 `derive_china_dataset` 现逻辑），取前 `limit`。
  4. meta：`scope="china"`、`captured_at`/`is_stale` 取自全球榜数据集、保留现有 `scope_note`。
  5. 无 cn → 返回 `([], meta)`；无已发布全球榜 → 返回 `([], None)`（同现状）。
- 其它 `dataset_key`（如 `language_global`）→ 照常读最新已发布该 key 的快照，但返回前对每条 entry **用 `classify_region` 现算 `creator_region`**（覆盖存量列），保证全站一致、实时。

`_serialize_entry` 使用现算后的 region。

### 3. 同步 `sync.py` 去掉中国榜物化

删除 `language_global` 同步分支里 `derive_china_dataset → store → publish language_china` 整段（含其 `observe_unknown_creators(china.entries)` 与 `completed.append("language_china")`）。全球榜的抓取、`load_creator_regions`、`parse_dataset`、`observe_unknown_creators`、store、publish 全部保留不变。

> 说明：`parse_dataset` 仍会给全球 entries 盖 `creator_region` 列，但读路径已不依赖该列（改为现算）。保留写入以降低改动面（YAGNI），该列退化为非权威信息。

### 4. 区块新鲜度映射 china → global

`blocks._published_aa_dataset_updated_at`：当请求的 keys 含 `language_china` 时，新鲜度查询用 `language_global` 的 `max(published_at)`（因为中国榜派生自全球榜，自身不再有发布记录）。实现为：把 keys 里的 `"language_china"` 替换成 `"language_global"` 后再查。

### 5. 后台「创作者」列表实时一致

`artificial_analysis_admin.list_creators`：返回每个创作者时，`region_code` 字段用实时判定 `classify_region(external_id, canonical_name, overrides)` 计算后返回，而非直接回存量 `region_code`。这样后台显示与榜单一致；`source` 仍如实返回（"manual"/"observed"）。`update_creator`（PUT override）逻辑不变——但现在 override 改完即在读路径生效，无需同步。

> `observe_unknown_creators` 继续在同步时把新创作者落入 `aa_creator_regions`（供后台列出可点选 override 的对象 + 覆盖率统计）；其 `region_code` 对读路径不再权威。

## 数据流（重构后）

```
改关键字 / 改 override
   └► 下一次中国榜区块读取
        └► get_published_ranking(session,"language_china",n)
             └► 取最新已发布 language_global 快照
                  └► 每条 classify_region(override else is_chinese_creator)  ← 实时
                       └► 筛 cn、重排、取前 N → 返回
== 立即生效，无需同步、无需按钮 ==

上游分数：language_global 仍照常抓取 → 快照 → 不可变发布（不受影响）
```

## 错误处理

- 无 cn 条目 → 空榜（非异常）。
- 无已发布全球榜 → `([], None)`（同现状）。
- `language_china` 历史存量行存在但不被读取——无害。

## 性能

读时投影 = 一次按 `dataset_id` 的索引查询（取全球榜 entries，约数百行）+ 纯 Python 子串匹配过滤。成本与原先「读已存中国榜」（同样一次索引查询）相当，不引入新缓存层。若未来公共页压力显现，可在 repository 层加一个按 `(最新 global 数据集 id, limit)` 为键的短 ttl 缓存，并在发布/override 编辑时 `cache_clear`——本期不做。

## 涉及文件（预估）

- `backend/app/services/artificial_analysis/repository.py`：新增 `classify_region`、`load_manual_overrides`、`_china_projection`；改 `get_published_ranking`。
- `backend/app/services/artificial_analysis/sync.py`：删除中国榜 derive/store/publish 段。
- `backend/app/services/blocks.py`：`_published_aa_dataset_updated_at` 的 china→global 映射。
- `backend/app/api/artificial_analysis_admin.py`：`list_creators` 实时 region。
- `backend/tests/`：`classify_region`、中国榜投影、global 实时 region、区块新鲜度映射、override 优先与改后即生效的测试。

## 测试

- `classify_region`：`"Z AI"` 自动判 cn；非中国创作者判 unknown；manual override 命中优先；override 把 cn 反转成非 cn（验证 override 高于自动）；id 与 name 双键命中。
- 中国榜投影：seed 一个已发布全球榜（含 cn/非 cn 混合），`get_published_ranking("language_china")` 正确筛选+重排+限量；**不跑任何 sync** 的前提下，新增关键字能命中（直接调函数验证实时性）；无 cn → 空。
- 其它榜实时 region：global entry 的存量 `creator_region` 列为旧值时，读路径返回实时值。
- 区块新鲜度：china 区块的 `_published_aa_dataset_updated_at` 取 `language_global` 的 `published_at`。
- 后台列表：`list_creators` 对 observed 行返回实时 region，对 manual 行返回 override 值。
- 全部走 SQLite 内存（后端）跑通。
