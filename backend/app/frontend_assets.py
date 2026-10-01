"""Keep immutable frontend bundles available to tabs spanning deployments.

Only hashed, flat build filenames are served; this is not a general-purpose
storage proxy. The existing private bucket and backend credentials stay private.
Run in the Railway pre-deploy container, before switching traffic.
"""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import tempfile
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from urllib.parse import urljoin

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


@lru_cache(maxsize=1)
def archive_bucket():
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    from supabase import create_client, ClientOptions
    client = create_client(settings.supabase_url, settings.supabase_service_role_key,
                           options=ClientOptions(storage_client_timeout=10))
    return client.storage.from_(settings.supabase_storage_bucket)


def save_asset(bucket, name: str, content: bytes) -> None:
    if not NAME.fullmatch(name):
        raise ValueError("Not an immutable frontend asset")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Frontend asset exceeds size limit")
    try:
        bucket.upload(PREFIX + name, content, file_options={
            "content-type": "application/octet-stream", "upsert": "false",
        })
    except Exception:
        # A hash is immutable: an existing name must have identical content.
        # Never overwrite a different build accidentally.
        if bucket.download(PREFIX + name) != content:
            raise


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
        if str(getattr(exc, "status", "")) == "404" or str(getattr(exc, "status_code", "")) == "404":
            return None
        # Unknown missing keys are also reported as 400 by some Storage versions.
        if "not found" in str(exc).lower():
            return None
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


def bootstrap_live_assets(bucket, base_url: str) -> int:
    """Archive the live build before its first replacement, including lazy chunks.

    Follow only flat hashed filenames at this app's /assets/ endpoint, never
    external URLs or arbitrary paths found in scripts.
    """
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        index = client.get(urljoin(base_url, "/index.html"))
        index.raise_for_status()
        marker = PREFIX + "manifests/" + hashlib.sha256(index.content).hexdigest() + ".txt"
        try:
            if bucket.download(marker) == b"complete":
                return 0
        except Exception:
            pass
        pending = set(REFERENCES.findall(index.text))
        if not pending:
            raise RuntimeError("Live frontend has no hashed bundles; refusing incomplete archive")
        seen = set()
        def archive_one(name):
            response = client.get(urljoin(base_url, "/assets/" + name))
            response.raise_for_status()
            save_asset(bucket, name, response.content)
            return set(REFERENCES.findall(response.text)) if name.endswith((".js", ".css")) else set()
        with ThreadPoolExecutor(max_workers=4) as workers:
            while pending:
                batch = pending - seen
                pending = set()
                seen.update(batch)
                if len(seen) > 500:
                    raise RuntimeError("Live frontend archive exceeds asset limit")
                for references in workers.map(archive_one, batch):
                    pending.update(references - seen)
        bucket.upload(marker, b"complete", file_options={"content-type": "text/plain", "upsert": "true"})
        return len(seen)


def publish_build(*, bootstrap_url: str | None = None) -> int:
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
    if bootstrap_url:
        bootstrap_live_assets(bucket, bootstrap_url)
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-live", action="store_true")
    args = parser.parse_args()
    count = publish_build(bootstrap_url=settings.public_base_url if args.bootstrap_live else None)
    print(f"Frontend retention ready: {count} current assets archived")
