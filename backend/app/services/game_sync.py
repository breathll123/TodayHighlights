# -*- coding: utf-8 -*-
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SH_TZ, settings
from app.core.logging import bind_log_context, log_event
from app.models.entities import CrawlJob, GameDeal, GameItem, GameRanking, GameRawSnapshot, Source
from app.services.adapters.game_steam import (
    build_steam_appdetails_url,
    build_steam_url,
    parse_steam_most_played_response,
    parse_steam_results_html,
)
from app.services.media_cache import MediaCacheService

logger = logging.getLogger("today_highlights.game_sync")


def _coerce_response_body(content: Any) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8", errors="replace")
    return b""


def map_entry_url_to_endpoint(entry_url: str) -> str:
    """
    将来源 Seed 中的伪协议 entry_url 转换为 Steam API 的 endpoint_key。
    """
    if entry_url == "steam://top_sellers":
        return "top_sellers"
    elif entry_url == "steam://specials":
        return "specials"
    elif entry_url == "steam://new_releases":
        return "new_releases"
    elif entry_url == "steam://most_played":
        return "most_played"
    else:
        raise ValueError(f"Unsupported Steam entry_url: {entry_url}")


def _fetch_steam_app_details(client: httpx.Client, appids: list[str], headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for appid in appids:
        try:
            detail_resp = client.get(build_steam_appdetails_url(appid), headers=headers)
            detail_resp.raise_for_status()
            payload = detail_resp.json()
            item = payload.get(str(appid)) if isinstance(payload, dict) else None
            if not isinstance(item, dict) or not item.get("success"):
                continue
            data = item.get("data")
            if isinstance(data, dict):
                details[str(appid)] = data
        except Exception as exc:
            log_event(
                logger,
                channel="application",
                category="crawler",
                event="game.sync.appdetails.failed",
                level=logging.WARNING,
                appid=appid,
                error=str(exc),
            )
    return details


def run_game_source_sync(session: Session, source: Source, job: CrawlJob) -> dict[str, int]:
    """
    运行游戏板块的数据采集和同步逻辑。由 run_crawl_job 调度触发。
    保存原始响应报文快照，解析游戏基础信息与排行/特惠状态入库，并联动本地媒体封面图缓存。
    """
    endpoint_key = map_entry_url_to_endpoint(source.entry_url)
    url = build_steam_url(endpoint_key)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    proxy = None
    if settings.steam_proxy_url:
        proxy = settings.steam_proxy_url

    # 1. 物理请求 Steam
    captured_at = datetime.now(SH_TZ)
    response_body = b""
    status_code = 0
    
    try:
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="game.sync.fetch.start",
            url=url,
            endpoint=endpoint_key,
        )
        
        # 发起 HTTP 请求
        with httpx.Client(proxy=proxy, timeout=settings.steam_timeout_seconds, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            status_code = resp.status_code
            response_body = _coerce_response_body(getattr(resp, "content", b""))
            resp.raise_for_status()

            resp_json = resp.json()
            if not response_body:
                response_body = json.dumps(resp_json, ensure_ascii=False, default=str).encode("utf-8")

            if endpoint_key == "most_played":
                ranks = (resp_json.get("response") or {}).get("ranks") if isinstance(resp_json, dict) else None
                appids = [
                    str(row.get("appid"))
                    for row in (ranks or [])[:50]
                    if isinstance(row, dict) and row.get("appid") is not None
                ]
                details_by_appid = _fetch_steam_app_details(client, appids, headers)
                items = parse_steam_most_played_response(resp_json, details_by_appid=details_by_appid, limit=50)
            else:
                if not resp_json or resp_json.get("success") != 1:
                    raise ValueError(f"Steam API success status not 1: {resp_json}")
                results_html = resp_json.get("results_html", "")
                items = parse_steam_results_html(results_html)
        
    except Exception as exc:
        # 记录抓取失败快照并抛出异常
        response_hash = hashlib.sha256(response_body).hexdigest() if response_body else "error"
        snapshot = GameRawSnapshot(
            provider="steam",
            endpoint_key=endpoint_key,
            request_url=url,
            status_code=status_code if status_code else 500,
            response_body=response_body if response_body else b"Error occurred",
            response_hash=response_hash,
            captured_at=captured_at.replace(tzinfo=None),
            parse_status="failed",
            error_message=str(exc)
        )
        session.add(snapshot)
        session.commit()
        
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="game.sync.fetch.failed",
            level=logging.ERROR,
            endpoint=endpoint_key,
            error=str(exc)
        )
        raise exc

    # 计算正常响应的 hash
    response_hash = hashlib.sha256(response_body).hexdigest()
    
    # 2. 创建并保存原始快照记录
    snapshot = GameRawSnapshot(
        provider="steam",
        endpoint_key=endpoint_key,
        request_url=url,
        status_code=status_code,
        response_body=response_body,
        response_hash=response_hash,
        captured_at=captured_at.replace(tzinfo=None),
        parse_status="pending",
        error_message=""
    )
    session.add(snapshot)
    session.flush() # 获得快照 id

    # 3. 同步解析后的条目列表
    try:
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="game.sync.parse.completed",
            endpoint=endpoint_key,
            parsed_count=len(items)
        )
        
        items_found = len(items)
        items_saved = 0
        
        media_cache = MediaCacheService(session)
        cached_count = 0
        
        # 开启内部事务性循环更新
        for parsed in items:
            # A. 查找或更新 GameItem 主表
            external_id = parsed["external_id"]
            
            # 使用 select 语句查询已有项目
            item_db = session.scalar(
                select(GameItem)
                .where(GameItem.provider == "steam", GameItem.external_id == external_id)
            )
            
            # 拼装基础字段
            now_dt = datetime.now(SH_TZ).replace(tzinfo=None)
            
            if item_db is None:
                item_db = GameItem(
                    provider="steam",
                    external_id=external_id,
                    name=parsed["name"],
                    cover_url=parsed["cover_url"],
                    source_url=parsed["source_url"],
                    release_date=parsed["release_date"],
                    metadata_json=parsed.get("metadata") or {},
                    last_seen_at=now_dt,
                    status="active"
                )
                session.add(item_db)
            else:
                item_db.name = parsed["name"]
                item_db.cover_url = parsed["cover_url"]
                item_db.source_url = parsed["source_url"]
                if parsed["release_date"]:
                    item_db.release_date = parsed["release_date"]
                if parsed.get("metadata"):
                    metadata = dict(item_db.metadata_json or {})
                    metadata.update(parsed["metadata"])
                    item_db.metadata_json = metadata
                item_db.last_seen_at = now_dt
                item_db.status = "active"
                
            session.flush() # 获得 item_db.id
            
            # B. 按照板块类型插入排行或打折特惠数据
            if endpoint_key in ["top_sellers", "new_releases", "most_played"]:
                # 排行数据入库
                ranking = GameRanking(
                    provider="steam",
                    ranking_type=endpoint_key,
                    game_item_id=item_db.id,
                    rank=parsed["rank"],
                    score=parsed.get("score"),
                    captured_at=captured_at.replace(tzinfo=None),
                    snapshot_id=snapshot.id
                )
                session.add(ranking)
                
            # 只要包含有效价格数据，无论是排行还是促销，一并往 game_deals 插入价格快照以供直读
            if parsed["current_price"] is not None:
                deal = GameDeal(
                    provider="steam",
                    game_item_id=item_db.id,
                    currency="CNY",
                    current_price=parsed["current_price"],
                    original_price=parsed["original_price"],
                    discount_percent=parsed["discount_percent"],
                    discount_label=parsed["discount_label"],
                    deal_url=parsed["source_url"],
                    captured_at=captured_at.replace(tzinfo=None),
                    snapshot_id=snapshot.id
                )
                session.add(deal)
            
            # C. 媒体封面图片本地缓存联动
            if parsed["cover_url"] and (not item_db.cover_local):
                # 检查缓存次数是否超出本轮配置上限
                if cached_count < settings.steam_media_cache_limit:
                    try:
                        # 尝试缓存图片到本地
                        local_path = media_cache.cache_remote_image(
                            source_url=parsed["cover_url"],
                            provider="steam",
                            entity_type="game",
                            entity_name=parsed["name"],
                            source_entity_id=external_id,
                            asset_type="game_cover",
                            metadata={"crawl_job_id": job.id, "endpoint": endpoint_key}
                        )
                        if local_path:
                            item_db.cover_local = local_path
                            cached_count += 1
                    except Exception as img_exc:
                        # 封面下载失败仅警告，不中断同步进程
                        log_event(
                            logger,
                            channel="application",
                            category="media",
                            event="game.cover.cache.failed",
                            level=logging.WARNING,
                            appid=external_id,
                            error=str(img_exc)
                        )
            
            items_saved += 1
            
        # 更新快照为已解析成功
        snapshot.parse_status = "parsed"
        session.commit()
        
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="game.sync.completed",
            endpoint=endpoint_key,
            found=items_found,
            saved=items_saved,
            cached_images=cached_count
        )
        
        return {"found": items_found, "saved": items_saved}
        
    except Exception as exc:
        # 解析发生致命错误
        session.rollback()
        snapshot.parse_status = "failed"
        snapshot.error_message = str(exc)
        session.commit()
        
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="game.sync.parse.failed",
            level=logging.ERROR,
            endpoint=endpoint_key,
            error=str(exc)
        )
        raise exc
