from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSpec:
    description: str
    field_order: tuple[str, ...]
    expanded_fields: tuple[str, ...] = ()


_COMMON_FIELD_ORDER = (
    "source_name",
    "site",
    "job_name",
    "dataset_name",
    "dataset_key",
    "block_name",
    "name",
    "provider",
    "backend",
    "operation",
    "model_name",
    "model",
    "source_type",
    "entity_type",
    "asset_type",
    "trigger_type",
    "route",
    "host",
    "method",
    "path",
    "endpoint",
    "query_keys",
    "client_ip",
    "url_hash",
    "status",
    "retry_after_seconds",
    "reason",
    "stage",
    "fallback",
    "slow",
    "page",
    "tier",
    "quota_remaining",
    "items_found",
    "items_received",
    "items_saved",
    "items_deduplicated",
    "dataset_count",
    "entry_count",
    "total_entries_count",
    "snapshot_count",
    "input_count",
    "fetch_count",
    "request_count",
    "success_count",
    "response_bytes",
    "body_bytes",
    "completed_count",
    "failed_count",
    "display_count",
    "summary_points",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "usage_estimated",
    "output_chars",
    "output_keys",
    "bytes",
    "duration_ms",
    "exception_type",
    "message",
    "source_id",
    "crawl_job_id",
    "ai_job_id",
    "job_id",
    "dataset_id",
    "snapshot_id",
    "active_run_id",
    "model_config_id",
    "enrichment_id",
    "block_id",
    "topic_id",
    "raw_item_id",
    "token_usage_id",
    "user_id",
    "request_id",
)

_EVENT_DESCRIPTIONS = {
    # Canonical events
    "app.started": "应用启动",
    "app.stopping": "应用停止中",
    "http.completed": "HTTP请求完成",
    "http.unhandled": "HTTP请求未处理异常",
    "crawl.started": "抓取任务开始",
    "crawl.fetch.completed": "抓取获取完成",
    "crawl.persist.completed": "抓取持久化完成",
    "crawl.completed": "抓取任务完成",
    "crawl.failed": "抓取任务失败",
    "upstream.completed": "上游请求完成",
    "upstream.failed": "上游请求失败",
    "ai.request.completed": "AI请求完成",
    "ai.request.failed": "AI请求失败",
    "ai.enrichment.completed": "AI增强完成",
    "ai.block.completed": "AI区块分析完成",
    "scheduler.job.completed": "调度任务完成",
    "scheduler.job.failed": "调度任务失败",
    "admin.changed": "管理配置已变更",
    # Legacy events retained until the event-name migration is complete.
    "aa_dataset_failed": "分析数据集处理失败",
    "aa_dataset_finished": "分析数据集处理完成",
    "aa_dataset_started": "分析数据集处理开始",
    "aa_page_collected": "分析页面采集完成",
    "aa_request_failed": "分析服务请求失败",
    "aa_request_started": "分析服务请求开始",
    "aa_sync_failed": "分析同步失败",
    "aa_sync_finished": "分析同步完成",
    "aa_sync_requested": "分析同步已请求",
    "aa_sync_skipped": "分析同步已跳过",
    "aa_sync_started": "分析同步开始",
    "aa_sync_status_persist_failed": "分析同步状态保存失败",
    "adapter_operation_failed": "数据适配操作失败",
    "ai_enrichment_failed": "AI增强失败",
    "ai_enrichment_finished": "AI增强完成",
    "ai_enrichment_started": "AI增强开始",
    "ai_request_failed": "AI请求失败",
    "ai_request_finished": "AI请求完成",
    "ai_request_started": "AI请求开始",
    "application_started": "应用启动",
    "application_stopping": "应用停止中",
    "block_analysis_failed": "区块分析失败",
    "block_analysis_finished": "区块分析完成",
    "block_analysis_started": "区块分析开始",
    "block_cookie_unavailable": "区块凭据不可用",
    "block_resolve_failed": "区块解析失败",
    "cache_backend_fallback": "缓存后端已降级",
    "cache_backend_ready": "缓存后端就绪",
    "cache_backend_recovered": "缓存后端已恢复",
    "cache_operation_failed": "缓存操作失败",
    "crawl_enrichment_failed": "抓取增强失败",
    "crawl_fetch_finished": "抓取获取完成",
    "crawl_job_failed": "抓取任务失败",
    "crawl_job_finished": "抓取任务完成",
    "crawl_job_started": "抓取任务开始",
    "crawl_persist_finished": "抓取持久化完成",
    "external_request_failed": "外部请求失败",
    "external_request_finished": "外部请求完成",
    "http_request_completed": "HTTP请求完成",
    "logging_queue_full": "日志队列已满",
    "media_cache_failed": "媒体缓存失败",
    "media_cache_finished": "媒体缓存完成",
    "media_cache_hit": "媒体缓存命中",
    "media_cache_init_failed": "媒体缓存初始化失败",
    "media_cache_race_reused": "媒体缓存复用并发结果",
    "media_cache_skipped": "媒体缓存已跳过",
    "media_cleanup_failed": "媒体清理失败",
    "media_download_finished": "媒体下载完成",
    "scheduled_job_failed": "调度任务失败",
    "scheduled_job_finished": "调度任务完成",
    "scheduled_job_missed": "调度任务错过执行",
    "scheduled_job_skipped": "调度任务已跳过",
    "scheduler_started": "调度器启动",
    "swr_refresh_failed": "后台缓存刷新失败",
    "unhandled_http_exception": "HTTP请求未处理异常",
    "log": "日志消息",
}

_EXPANDED_FAILURE_FIELDS = ("url", "response_preview")
_FAILURE_EVENTS = {
    event
    for event in _EVENT_DESCRIPTIONS
    if event.endswith(("failed", ".failed")) or "unhandled" in event
}

EVENT_SPECS = {
    event: EventSpec(
        description=description,
        field_order=_COMMON_FIELD_ORDER,
        expanded_fields=_EXPANDED_FAILURE_FIELDS if event in _FAILURE_EVENTS else (),
    )
    for event, description in _EVENT_DESCRIPTIONS.items()
}

_FALLBACK_SPEC = EventSpec(description="业务事件", field_order=())


def event_spec(event: str) -> EventSpec:
    return EVENT_SPECS.get(event, _FALLBACK_SPEC)
