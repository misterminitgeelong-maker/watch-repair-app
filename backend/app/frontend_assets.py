"""Keep immutable frontend bundles available to tabs spanning deployments.

Only hashed, flat build filenames are served; this is not a general-purpose
storage proxy. The existing private bucket and backend credentials stay private.
Run in the Railway pre-deploy container, before switching traffic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import re
import tempfile
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from urllib.parse import urljoin, quote

import httpx
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import settings

PREFIX = "_frontend-builds/v1/"
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
EXTENSIONS = r"(?:js|css|woff2?|ttf|otf|png|jpe?g|svg|webp|gif|ico)"
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,180}-[A-Za-z0-9_-]{8}\." + EXTENSIONS)
REFERENCES = re.compile(r"(?:/assets/|assets/|\./)(" + NAME.pattern + r")(?![A-Za-z0-9_.-])")
CACHE_DIR = Path(tempfile.gettempdir()) / "mainspring-frontend-assets-v1"
logger = logging.getLogger(__name__)
RETRYABLE = {408, 429, 500, 502, 503, 504}


def storage_error(exc) -> tuple[int | None, str]:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    code = type(exc).__name__
    if response is not None:
        try:
            body = response.json()
            if isinstance(body, dict):
                code = str(body.get("code") or body.get("error") or code)
                if body.get("statusCode") is not None:
                    status = int(body["statusCode"])
        except (ValueError, TypeError):
            pass
    # Log only an identifier, never a provider message, credential or URL.
    return status, re.sub(r"[^A-Za-z0-9_]", "", code)[:64]


def missing_object(exc) -> bool:
    status, code = storage_error(exc)
    return (isinstance(exc, FileNotFoundError) or status == 404
            or code.lower() in {"nosuchkey", "notfound", "objectnotfound", "not_found"}
            or (not isinstance(exc, httpx.HTTPError) and "not found" in str(exc).lower()))


def get_with_retry(client, url: str):
    for attempt in range(3):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status, _ = storage_error(exc)
            if attempt == 2 or (isinstance(exc, httpx.HTTPStatusError) and status not in RETRYABLE):
                raise
            time.sleep(0.5 * (2 ** attempt))


def save_manifest(bucket, path: str, body: bytes, content_type: str):
    # Metadata is content addressed and safe to retry after a lost response.
    for attempt in range(3):
        try:
            bucket.upload(path, body, file_options={"content-type": content_type, "upsert": "true"})
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2 ** attempt))


class ArchiveBucket:
    """Use the documented authenticated endpoint for private object reads."""
    def __init__(self, bucket, url: str, key: str, bucket_name: str):
        self.bucket = bucket
        self.base_url = url.rstrip("/") + "/storage/v1/object/authenticated/" + quote(bucket_name, safe="") + "/"
        self.reader = httpx.Client(timeout=20, headers={"apikey": key, "Authorization": "Bearer " + key})

    def upload(self, *args, **kwargs):
        return self.bucket.upload(*args, **kwargs)

    def download(self, path: str) -> bytes:
        response = get_with_retry(self.reader, self.base_url + quote(path, safe="/"))
        return response.content


@lru_cache(maxsize=1)
def archive_bucket():
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    from supabase import create_client, ClientOptions
    client = create_client(settings.supabase_url, settings.supabase_service_role_key,
                           options=ClientOptions(storage_client_timeout=10))
    return ArchiveBucket(client.storage.from_(settings.supabase_storage_bucket),
                         settings.supabase_url, settings.supabase_service_role_key,
                         settings.supabase_storage_bucket)


def save_asset(bucket, name: str, content: bytes) -> None:
    if not NAME.fullmatch(name):
        raise ValueError("Not an immutable frontend asset")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Frontend asset exceeds size limit")
    # Check first: most bundles are unchanged between builds. Avoid duplicate
    # uploads and tolerate brief Storage/proxy failures without publishing an
    # incomplete archive. Names are never overwritten.
    last_error = None
    for attempt in range(4):
        try:
            existing = bucket.download(PREFIX + name)
        except Exception as exc:
            # An unavailable archive is not evidence that the object is absent.
            if not missing_object(exc):
                last_error = exc
                if attempt < 3:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
        else:
            if existing != content:
                raise RuntimeError("Existing immutable frontend asset differs")
            return
        try:
            bucket.upload(PREFIX + name, content, file_options={
                "content-type": "application/octet-stream", "upsert": "false",
            })
            return
        except Exception as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(0.5 * (2 ** attempt))
    # A concurrent publisher may have completed our final duplicate upload.
    try:
        if bucket.download(PREFIX + name) == content:
            return
    except Exception:
        pass
    status, code = storage_error(last_error)
    raise RuntimeError(f"Frontend archive failed for {name}: status={status} code={code}") from last_error


def cached_asset(name: str) -> Path | None:
    if not NAME.fullmatch(name):
        return None
    cached = CACHE_DIR / name
    if cached.is_file():
        return cached
    bucket = archive_bucket()
    if bucket is None:
        return None
    try:
        content = bucket.download(PREFIX + name)
    except Exception as exc:
        if missing_object(exc):
            return None
        status, code = storage_error(exc)
        logger.warning("Archived frontend asset unavailable: name=%s status=%s code=%s release=%s",
                       name, status, code, os.environ.get("APP_BUILD_ID", "unknown"))
        raise HTTPException(503, "Frontend asset temporarily unavailable") from exc
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(503, "Frontend asset exceeds size limit")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = cached.with_name(name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(cached)
    finally:
        temporary.unlink(missing_ok=True)
    return cached


class RetainedFrontendAssets(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            if scope["method"] not in {"GET", "HEAD"} or not NAME.fullmatch(path):
                raise
            cached = await run_in_threadpool(cached_asset, path)
            if cached is None:
                raise exc
            response = FileResponse(cached, media_type=mimetypes.guess_type(path)[0], headers=IMMUTABLE)
        if NAME.fullmatch(path) and response.status_code == 200:
            response.headers.update(IMMUTABLE)
        return response


def bootstrap_live_assets(bucket, base_url: str, extra_entries: tuple[str, ...] = ()) -> int:
    """Archive the live build before its first replacement, including lazy chunks.

    Follow only flat hashed filenames at this app's /assets/ endpoint, never
    external URLs or arbitrary paths found in scripts.
    """
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        index = get_with_retry(client, urljoin(base_url, "/index.html"))
        if any(not NAME.fullmatch(name) for name in extra_entries):
            raise ValueError("Invalid bootstrap frontend entry")
        marker = PREFIX + "manifests/" + hashlib.sha256(index.content + repr(extra_entries).encode()).hexdigest() + ".txt"
        try:
            if bucket.download(marker) == b"complete":
                return 0
        except Exception:
            pass
        pending = set(REFERENCES.findall(index.text))
        pending.update(extra_entries)
        if not pending:
            raise RuntimeError("Live frontend has no hashed bundles; refusing incomplete archive")
        seen = set()
        def archive_one(name):
            try:
                content = bucket.download(PREFIX + name)
            except Exception as exc:
                if not missing_object(exc):
                    raise RuntimeError(f"Cannot read legacy archive asset {name}") from exc
                try:
                    content = get_with_retry(client, urljoin(base_url, "/assets/" + name)).content
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Cannot backfill legacy asset {name}: {type(exc).__name__}") from exc
                save_asset(bucket, name, content)
            return set(REFERENCES.findall(content.decode("utf-8"))) if name.endswith((".js", ".css")) else set()
        with ThreadPoolExecutor(max_workers=4) as workers:
            while pending:
                batch = pending - seen
                pending = set()
                seen.update(batch)
                if len(seen) > 500:
                    raise RuntimeError("Live frontend archive exceeds asset limit")
                for references in workers.map(archive_one, batch):
                    pending.update(references - seen)
        save_manifest(bucket, marker, b"complete", "text/plain")
        return len(seen)


def publish_build(*, bootstrap_url: str | None = None, extra_entries: tuple[str, ...] = ()) -> int:
    bucket = archive_bucket()
    if bucket is None:
        # Local development doesn't need an object-storage dependency. Production
        # must fail the pre-deploy step rather than remove assets from open tabs.
        if settings.app_env == "production":
            raise RuntimeError("Production frontend retention requires Supabase storage")
        return 0
    root = Path(settings.static_dir) / "assets"
    files = [p for p in root.iterdir() if p.is_file() and NAME.fullmatch(p.name)]
    if not files:
        raise RuntimeError("No built frontend assets found")
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda asset: save_asset(bucket, asset.name, asset.read_bytes()), files))
    # Verify read access and exact bytes before marking this release complete.
    def verify(asset):
        content = asset.read_bytes()
        if bucket.download(PREFIX + asset.name) != content:
            raise RuntimeError(f"Frontend archive verification failed for {asset.name}")
        return asset.name, hashlib.sha256(content).hexdigest()
    with ThreadPoolExecutor(max_workers=4) as workers:
        manifest = dict(workers.map(verify, files))
    body = json.dumps(manifest, sort_keys=True).encode()
    release = hashlib.sha256(body).hexdigest()
    save_manifest(bucket, PREFIX + "releases/" + release + ".json", body, "application/json")
    if bootstrap_url:
        bootstrap_live_assets(bucket, bootstrap_url, extra_entries)
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-live", action="store_true")
    parser.add_argument("--bootstrap-entry", action="append", default=[])
    args = parser.parse_args()
    count = publish_build(bootstrap_url=settings.public_base_url if args.bootstrap_live else None,
                          extra_entries=tuple(args.bootstrap_entry))
    print(f"Frontend retention ready: {count} current assets archived")
