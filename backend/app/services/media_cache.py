from __future__ import annotations

import logging
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.models.entities import MediaAsset

logger = logging.getLogger("today_highlights.media")

DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "media"
ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def url_hash(url: str) -> str:
    return sha256(normalize_url(url).encode("utf-8")).hexdigest()


def is_safe_remote_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"}:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.startswith("10.") or host.startswith("192.168."):
        return False
    if host.startswith("172."):
        parts = host.split(".")
        if len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return False
    return True


def extension_for(content_type: str, url: str) -> str:
    ctype = content_type.split(";")[0].strip().lower()
    if ctype in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[ctype]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".bin"


class MediaCacheService:
    def __init__(
        self,
        session: Session,
        *,
        storage_root: Path | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.storage_root = storage_root or DEFAULT_STORAGE_ROOT
        self.http_client = http_client or httpx.Client(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1"},
            follow_redirects=True,
        )
        self._bind = session.get_bind()

    def _new_session(self) -> Session | None:
        try:
            from sqlalchemy.orm import sessionmaker
            return sessionmaker(bind=self._bind)()
        except Exception:
            return None

    def cache_remote_image(
        self,
        source_url: str,
        *,
        provider: str,
        entity_type: str,
        entity_name: str,
        source_entity_id: str = "",
        asset_type: str = "football_logo",
        metadata: dict | None = None,
    ) -> str:
        normalized = normalize_url(source_url)
        if not normalized or not is_safe_remote_url(normalized):
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cache.skipped",
                level=logging.WARNING,
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                reason="unsafe_url",
            )
            return ""

        digest = url_hash(normalized)
        sess = self._new_session()
        if sess is None:
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cache.failed",
                level=logging.ERROR,
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                url_hash=digest,
                reason="session_creation",
            )
            return ""
        local_file: Path | None = None
        started = time.perf_counter()
        try:
            existing = sess.scalar(select(MediaAsset).where(MediaAsset.url_hash == digest))
            now = datetime.utcnow()
            if existing and existing.status == "cached" and existing.local_path and Path(existing.local_path).exists():
                existing.last_used_at = now
                sess.commit()
                log_event(
                    logger,
                    channel="application",
                    category="media",
                    event="media.cache.hit",
                    provider=provider,
                    asset_type=asset_type,
                    entity_type=entity_type,
                    url_hash=digest,
                )
                return existing.public_path

            asset = existing or MediaAsset(
                source_url=source_url,
                normalized_url=normalized,
                url_hash=digest,
            )
            asset.provider = provider
            asset.asset_type = asset_type
            asset.entity_type = entity_type
            asset.entity_name = entity_name
            asset.source_entity_id = source_entity_id
            asset.last_used_at = now
            asset.fetch_count = (asset.fetch_count or 0) + 1
            asset.metadata_json = {**(asset.metadata_json or {}), **(metadata or {})}

            if existing is None:
                sess.add(asset)

            response = self.http_client.get(normalized)
            response.raise_for_status()
            body = response.content
            if not body:
                raise ValueError("empty image body")
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.download.completed",
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                url_hash=digest,
                status=getattr(response, "status_code", 200),
                bytes=len(body),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

            content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].lower()
            extension = extension_for(content_type, normalized)
            folder = self.storage_root / "football"
            folder.mkdir(parents=True, exist_ok=True)
            local_file = folder / f"{digest}{extension}"
            local_file.write_bytes(body)

            asset.original_filename = Path(urlparse(normalized).path).name
            asset.content_type = content_type
            asset.extension = extension
            asset.local_path = str(local_file)
            asset.public_path = f"/api/public/media/{digest}"
            asset.file_size = len(body)
            asset.status = "cached"
            asset.error_message = ""
            asset.last_fetched_at = now
            sess.commit()
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cache.completed",
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                url_hash=digest,
                bytes=len(body),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return asset.public_path
        except IntegrityError as exc:
            try:
                sess.rollback()
            except Exception:
                pass
            existing_path = self._return_existing_cached(sess, url_hash(normalized), datetime.utcnow())
            if existing_path:
                log_event(
                    logger,
                    channel="application",
                    category="media",
                    event="media.cache.race-reused",
                    provider=provider,
                    asset_type=asset_type,
                    entity_type=entity_type,
                    url_hash=digest,
                )
                return existing_path
            if local_file is not None:
                self._remove_file(local_file)
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cache.failed",
                level=logging.WARNING,
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                url_hash=digest,
                error_type=type(exc).__name__,
                reason="integrity",
            )
            return ""
        except Exception as exc:
            try:
                sess.rollback()
            except Exception:
                pass
            if local_file is not None:
                self._remove_file(local_file)
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cache.failed",
                level=logging.ERROR,
                provider=provider,
                asset_type=asset_type,
                entity_type=entity_type,
                url_hash=digest,
                error_type=type(exc).__name__,
                reason="download_or_persist",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return ""
        finally:
            sess.close()

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            log_event(
                logger,
                channel="application",
                category="media",
                event="media.cleanup.failed",
                level=logging.WARNING,
                error_type=type(exc).__name__,
            )

    def _return_existing_cached(self, sess: Session, digest: str, used_at: datetime) -> str:
        try:
            existing = sess.scalar(select(MediaAsset).where(MediaAsset.url_hash == digest))
            if existing and existing.status == "cached" and existing.local_path and Path(existing.local_path).exists():
                existing.last_used_at = used_at
                sess.commit()
                return existing.public_path
            sess.rollback()
        except Exception:
            try:
                sess.rollback()
            except Exception:
                pass
        return ""
