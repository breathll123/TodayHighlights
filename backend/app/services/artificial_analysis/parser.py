import json
import math
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256

from app.models.entities import AACreatorRegion


class DatasetParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedRankingEntry:
    model_external_id: str
    model_slug: str
    model_name: str
    creator_external_id: str
    creator_name: str
    creator_region: str
    rank: int | None
    score: Decimal | None
    score_type: str
    ci_95: Decimal | None
    release_date: date | None
    metrics: dict = field(default_factory=dict)
    pricing: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    source_url: str = ""


@dataclass(frozen=True)
class ParsedDataset:
    dataset_key: str
    scope: str
    score_type: str
    source_tier: str
    source_version: str
    entries: list[ParsedRankingEntry]
    warnings: list[str]
    data_sha256: str


def normalize_creator_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(normalized.split())


def _extract_score(item: dict, score_type: str) -> Decimal | None:
    if score_type == "intelligence_index":
        evals = item.get("evaluations") or {}
        val = evals.get("artificial_analysis_intelligence_index")
    elif score_type == "aa_wer_index":
        val = item.get("aa_wer_index")
    elif score_type == "elo":
        val = item.get("elo")
    else:
        return None

    if val is None:
        return None
    try:
        d = Decimal(str(val))
        if not math.isfinite(float(d)):
            return None
        return d
    except Exception:
        return None


def _extract_ci_95(item: dict, score_type: str) -> Decimal | None:
    if score_type in ("elo",):
        val = item.get("ci_95")
        if val is not None:
            try:
                return Decimal(str(val))
            except Exception:
                return None
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _make_fallback_model_id(dataset_key: str, model_name: str, creator_name: str) -> str:
    raw = f"{dataset_key}:{model_name}:{creator_name}"
    return sha256(raw.encode()).hexdigest()[:32]


def parse_dataset(
    dataset_key: str,
    payloads: list[dict],
    creator_regions: list[AACreatorRegion],
) -> ParsedDataset:
    """Parse one or more upstream response payloads into a validated ParsedDataset."""

    source_tier = ""
    source_version = ""
    all_entries: list[ParsedRankingEntry] = []
    total_rows = 0
    invalid_rows = 0
    warnings: list[str] = []
    seen_ids: set[str] = set()
    source_url = ""

    # Lower = better for WER; higher = better for everything else
    descending = dataset_key != "speech_to_text"

    # Build creator lookup maps
    region_by_id: dict[str, str] = {}
    region_by_name: dict[str, str] = {}
    for cr in creator_regions:
        if cr.creator_external_id:
            region_by_id[cr.creator_external_id] = cr.region_code
        if cr.normalized_name:
            region_by_name[cr.normalized_name] = cr.region_code

    for payload in payloads:
        if not isinstance(payload, dict):
            invalid_rows += 1
            continue

        source_tier = str(payload.get("tier") or source_tier or "")
        source_version = str(payload.get("intelligence_index_version") or source_version or "")
        rows = payload.get("data")
        if not isinstance(rows, list):
            continue

        for item in rows:
            if not isinstance(item, dict):
                invalid_rows += 1
                continue
            total_rows += 1

            model_id = str(item.get("id") or "")
            model_name = str(item.get("name") or "").strip()
            if not model_name:
                invalid_rows += 1
                continue

            model_slug = str(item.get("slug") or "")
            release_date = _parse_date(item.get("release_date"))

            # Creator resolution
            creator = item.get("model_creator")
            creator_id = ""
            creator_name = ""
            if isinstance(creator, dict):
                creator_id = str(creator.get("id") or "")
                creator_name = str(creator.get("name") or "").strip()

            # Region resolution
            region = "unknown"
            if creator_id and creator_id in region_by_id:
                region = region_by_id[creator_id]
            elif not creator_id:
                norm = normalize_creator_name(creator_name)
                if norm and norm in region_by_name:
                    region = region_by_name[norm]

            # 智能兜底判定：如果数据库未能匹配或标注为 unknown，但符合已知中国创作者关键词，则设为 cn
            if region == "unknown" and is_chinese_creator(creator_id, creator_name):
                region = "cn"

            # Fallback model ID when upstream ID is missing
            effective_id = model_id
            if not effective_id:
                effective_id = _make_fallback_model_id(dataset_key, model_name, creator_name)
                warnings.append(f"fallback_model_id for '{model_name}' ({creator_name})")

            # Duplicate check
            if effective_id in seen_ids:
                warnings.append(f"duplicate model_id '{effective_id}', keeping first occurrence")
                continue
            seen_ids.add(effective_id)

            # Score
            score_type = (
                "aa_wer_index" if dataset_key == "speech_to_text"
                else "intelligence_index" if "language" in dataset_key
                else "elo"
            )
            score = _extract_score(item, score_type)
            ci_95 = _extract_ci_95(item, score_type)

            # Metrics / pricing / performance
            metrics: dict = {}
            if dataset_key.startswith("language"):
                metrics = {
                    "coding_index": (item.get("evaluations") or {}).get("artificial_analysis_coding_index"),
                    "agentic_index": (item.get("evaluations") or {}).get("artificial_analysis_agentic_index"),
                    "total_cost": (item.get("artificial_analysis_intelligence_index_cost") or {}).get("total_cost"),
                }
                metrics = {k: v for k, v in metrics.items() if v is not None}

            pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
            performance = item.get("performance") if isinstance(item.get("performance"), dict) else {}

            entry = ParsedRankingEntry(
                model_external_id=effective_id,
                model_slug=model_slug,
                model_name=model_name,
                creator_external_id=creator_id,
                creator_name=creator_name,
                creator_region=region,
                rank=None,
                score=score,
                score_type=score_type,
                ci_95=ci_95,
                release_date=release_date,
                metrics=metrics,
                pricing=pricing,
                performance=performance,
                source_url=source_url,
            )
            all_entries.append(entry)

    # Validate invalid ratio
    if total_rows > 0 and invalid_rows / total_rows > 0.10:
        raise DatasetParseError(
            f"{invalid_rows}/{total_rows} rows failed validation (>10%)"
        )

    # Sort entries
    def sort_key(e: ParsedRankingEntry) -> tuple:
        if e.score is None:
            return (1, 0, "", "")
        return (0, -float(e.score) if descending else float(e.score), e.model_name.lower(), e.model_external_id)

    sorted_entries = sorted(all_entries, key=sort_key)

    # Assign ranks
    rank = 1
    for i, entry in enumerate(sorted_entries):
        if entry.score is not None:
            entry = ParsedRankingEntry(
                model_external_id=entry.model_external_id,
                model_slug=entry.model_slug,
                model_name=entry.model_name,
                creator_external_id=entry.creator_external_id,
                creator_name=entry.creator_name,
                creator_region=entry.creator_region,
                rank=rank,
                score=entry.score,
                score_type=entry.score_type,
                ci_95=entry.ci_95,
                release_date=entry.release_date,
                metrics=entry.metrics,
                pricing=entry.pricing,
                performance=entry.performance,
                source_url=entry.source_url,
            )
            sorted_entries[i] = entry
            rank += 1
        else:
            entry = ParsedRankingEntry(
                model_external_id=entry.model_external_id,
                model_slug=entry.model_slug,
                model_name=entry.model_name,
                creator_external_id=entry.creator_external_id,
                creator_name=entry.creator_name,
                creator_region=entry.creator_region,
                rank=None,
                score=entry.score,
                score_type=entry.score_type,
                ci_95=entry.ci_95,
                release_date=entry.release_date,
                metrics=entry.metrics,
                pricing=entry.pricing,
                performance=entry.performance,
                source_url=entry.source_url,
            )
            sorted_entries[i] = entry

    # Hash
    data_sha256 = canonical_dataset_hash(dataset_key, sorted_entries)

    return ParsedDataset(
        dataset_key=dataset_key,
        scope="global",
        score_type=sorted_entries[0].score_type if sorted_entries else "",
        source_tier=source_tier,
        source_version=source_version,
        entries=sorted_entries,
        warnings=warnings,
        data_sha256=data_sha256,
    )


def derive_china_dataset(global_dataset: ParsedDataset) -> ParsedDataset:
    """Create a China-only derived dataset from a global language dataset."""
    cn_entries = [
        e for e in global_dataset.entries
        if e.creator_region == "cn"
    ]

    if not cn_entries:
        raise DatasetParseError("empty derived China dataset")

    # Rerank
    ranked: list[ParsedRankingEntry] = []
    rank = 1
    for entry in cn_entries:
        ranked.append(ParsedRankingEntry(
            model_external_id=entry.model_external_id,
            model_slug=entry.model_slug,
            model_name=entry.model_name,
            creator_external_id=entry.creator_external_id,
            creator_name=entry.creator_name,
            creator_region=entry.creator_region,
            rank=rank if entry.score is not None else None,
            score=entry.score,
            score_type=entry.score_type,
            ci_95=entry.ci_95,
            release_date=entry.release_date,
            metrics=entry.metrics,
            pricing=entry.pricing,
            performance=entry.performance,
            source_url=entry.source_url,
        ))
        if entry.score is not None:
            rank += 1

    data_sha256 = canonical_dataset_hash("language_china", ranked)

    return ParsedDataset(
        dataset_key="language_china",
        scope="china",
        score_type=global_dataset.score_type,
        source_tier=global_dataset.source_tier,
        source_version=global_dataset.source_version,
        entries=ranked,
        warnings=global_dataset.warnings,
        data_sha256=data_sha256,
    )


def canonical_dataset_hash(dataset_key: str, entries: list[ParsedRankingEntry]) -> str:
    payload = {
        "dataset_key": dataset_key,
        "entries": [
            {
                "model_external_id": e.model_external_id,
                "model_name": e.model_name,
                "creator_external_id": e.creator_external_id,
                "creator_name": e.creator_name,
                "creator_region": e.creator_region,
                "rank": e.rank,
                "score": str(e.score) if e.score is not None else None,
                "score_type": e.score_type,
            }
            for e in entries
        ],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode()).hexdigest()


def is_chinese_creator(creator_id: str | None, creator_name: str | None) -> bool:
    """
    智能识别中国的大模型厂商（创作者）。
    支持包括智谱、阿里通义、百川、深度求索、月之暗面、腾讯混元、百度文心等常见厂商及其变体。
    """
    cn_keywords = {
        "zhipu", "zhipuai", "zhipu-ai", "qwen", "alibaba", "deepseek", "baichuan", 
        "moonshot", "kimi", "01.ai", "lingyiwanwu", "tencent", "baidu", "sensetime", 
        "minimax", "internlm", "xverse", "shanghai-ai", "shanghai artificial intelligence laboratory",
        "yayi", "xiaomi", "huawei", "spark", "xfyun", "iflytek", "sensenova", "stepfun", "jieyue"
    }
    id_lower = creator_id.lower().strip() if creator_id else ""
    name_lower = creator_name.lower().strip() if creator_name else ""
    
    # 检查 ID 或名称中是否包含任何中国厂商的关键字
    for kw in cn_keywords:
        if kw in id_lower or kw in name_lower:
            return True
    return False
