from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AIPromptTemplate

SOURCE_TYPE_TO_CLASS: dict[str, str] = {
    "tonghuashun_news": "news",
    "eastmoney_announcements": "news",
    "aihot_news": "news",
    "hot_stocks": "rank",
    "hot_events": "rank",
    "xueqiu_hot_cn": "rank",
    "xueqiu_hot_hk": "rank",
    "xueqiu_hot_us": "rank",
    "screener": "rank",
    "eastmoney_sectors": "rank",
    "eastmoney_industry": "rank",
    "eastmoney_indices": "rank",
    "eastmoney_capital_flow": "rank",
    "eastmoney_longhu": "rank",
    "qiumiwu_standings": "rank",
    "datalearner_leaderboard": "rank",
    "datalearner_aa_index": "rank",
    "qiumiwu_matches": "event",
    "qiumiwu_fixtures": "event",
    "qiumiwu_schedule": "event",
}

_FRAMEWORK_NEWS = (
    "【分析流程】\n"
    "1. 识别增量信息，排除重复和常规内容。\n"
    "2. 判断事件可能影响的对象、范围和路径。\n"
    "3. 将多个相关内容合并成更高层级看点。\n"
    "4. 指出信息不足、来源单一或前提不明确的地方。\n"
)

_FRAMEWORK_RANK = (
    "【分析流程】\n"
    "1. 识别数值、排名、资金、涨跌幅、积分等异常项。\n"
    "2. 判断异动是分散还是集中，集中在哪些方向。\n"
    "3. 总结当前结构反映的偏好、压力或变化。\n"
    "4. 指出延续或反转需要观察的后续信号。\n"
)

_FRAMEWORK_EVENT = (
    "【分析流程】\n"
    "1. 提取关键事实、时间、状态和结果。\n"
    "2. 判断事件对后续节奏、排名、赛程或相关主体的影响。\n"
    "3. 识别超预期、异常或值得关注的变化。\n"
    "4. 说明下一步值得关注的关键节点。\n"
)

_FRAMEWORKS = {
    "news": _FRAMEWORK_NEWS,
    "rank": _FRAMEWORK_RANK,
    "event": _FRAMEWORK_EVENT,
}

_OUTPUT_SPEC = (
    "【输出字段】\n"
    "- summary_points: 字符串数组，1-4 条，每条不超过 160 字。\n"
    "- key_changes: 字符串数组，0-3 条，每条不超过 140 字。\n"
    "- risk_points: 字符串数组，0-2 条，每条不超过 140 字。\n"
    "- related_entities: 字符串数组，0-8 个，每个不超过 40 字。\n"
    "- confidence: 0 到 1 的数字。\n"
)

_FORBIDDEN_BASE = (
    "【禁止】\n"
    "- 不得把输入标题直接复制成 summary_points。\n"
    "- 不得使用「值得关注」「持续观察」「市场活跃」等无信息量套话收尾。\n"
    "- 只能基于提供内容分析，不得补充外部事实。\n"
    "- 不得编造来源、数据、比分、公司、股票或事件。\n"
    "- 只输出合法 JSON，不输出 Markdown，不输出代码块，不输出额外解释。\n"
)


def get_content_class(source_type: str) -> str:
    return SOURCE_TYPE_TO_CLASS.get(source_type, "news")


def infer_topic_slug(page_route: str) -> str:
    parts = [part for part in page_route.strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] == "topics":
        return parts[1]
    return "summary"


def get_enabled_prompt_template(session: Session, topic_slug: str, content_class: str) -> AIPromptTemplate | None:
    return session.scalar(
        select(AIPromptTemplate)
        .where(
            AIPromptTemplate.topic_slug == topic_slug,
            AIPromptTemplate.content_class == content_class,
            AIPromptTemplate.enabled.is_(True),
        )
        .limit(1)
    )


def build_block_system_prompt(
    topic_slug: str,
    content_class: str,
    template: AIPromptTemplate | None,
) -> str:
    framework = _FRAMEWORKS.get(content_class, _FRAMEWORK_NEWS)
    sections = [
        f"你是今日看点的内容分析助手，当前分析领域：{topic_slug}。",
    ]
    if template is not None and template.topic_context.strip():
        sections.append(f"【领域背景】\n{template.topic_context.strip()}")
    sections.extend([framework.strip(), _OUTPUT_SPEC.strip(), _FORBIDDEN_BASE.strip()])
    if template is not None and template.extra_forbidden.strip():
        sections.append(f"【额外禁止】\n{template.extra_forbidden.strip()}")
    return "\n\n".join(sections)
