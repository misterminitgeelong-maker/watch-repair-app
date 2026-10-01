from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import frontend_assets as assets


class Bucket:
    def __init__(self):
        self.objects = {}

    def upload(self, name, content, file_options):
        if name in self.objects and file_options.get("upsert") != "true":
            raise RuntimeError("already exists")
        self.objects[name] = content

    def download(self, name):
        if name not in self.objects:
            raise RuntimeError("Object not found")
        return self.objects[name]


def test_archive_recovers_from_temporary_storage_failure(monkeypatch):
    bucket = Bucket()
    upload = bucket.upload
    attempts = []
    def unstable_upload(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("temporary storage outage")
        return upload(*args, **kwargs)
    monkeypatch.setattr(bucket, "upload", unstable_upload)
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    assets.save_asset(bucket, "Page-abcdefgh.js", b"export default 1")
    assert len(attempts) == 2
    assert bucket.download(assets.PREFIX + "Page-abcdefgh.js") == b"export default 1"


def test_private_archive_uses_authenticated_download_endpoint():
    bucket = assets.ArchiveBucket(Bucket(), "https://storage.example", "test-key", "attachments")
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, content=b"export default 1")
    bucket.reader.close()
    with httpx.Client(transport=httpx.MockTransport(respond), headers={"Authorization": "Bearer test-key"}) as reader:
        bucket.reader = reader
        assert bucket.download(assets.PREFIX + "Page-abcdefgh.js") == b"export default 1"
    assert requests[0].url.path == "/storage/v1/object/authenticated/attachments/_frontend-builds/v1/Page-abcdefgh.js"
    assert requests[0].headers["authorization"] == "Bearer test-key"


@pytest.fixture
def retained(tmp_path, monkeypatch):
    bucket = Bucket()
    monkeypatch.setattr(assets, "archive_bucket", lambda: bucket)
    monkeypatch.setattr(assets, "CACHE_DIR", tmp_path / "cache")
    root = tmp_path / "current"
    root.mkdir()
    (root / "Current-abcdefgh.js").write_bytes(b"export default 'current'")
    app = FastAPI()
    app.mount("/assets", assets.RetainedFrontendAssets(directory=root))
    return TestClient(app), bucket


def test_old_tab_loads_uncached_old_route_from_archive(retained):
    client, bucket = retained
    assets.save_asset(bucket, "OldPage-12345678.js", b"export default 'old'")
    response = client.get("/assets/OldPage-12345678.js")
    assert response.status_code == 200
    assert response.content == b"export default 'old'"
    assert "immutable" in response.headers["cache-control"]
    assert "javascript" in response.headers["content-type"]
    # A transient storage outage cannot affect a bundle already cached locally.
    bucket.objects.clear()
    assert client.get("/assets/OldPage-12345678.js").status_code == 200
    assert client.head("/assets/OldPage-12345678.js").content == b""


def test_current_build_uses_local_assets(retained):
    client, bucket = retained
    assert client.get("/assets/Current-abcdefgh.js").content == b"export default 'current'"
    assert bucket.objects == {}


@pytest.mark.parametrize("path", ["private.pdf", "credentials.json", "sub/OldPage-12345678.js", "Missing-abcdefgh.js"])
def test_asset_endpoint_never_proxies_arbitrary_storage(retained, path):
    client, _ = retained
    assert client.get("/assets/" + path).status_code == 404


def test_existing_hash_cannot_be_overwritten():
    bucket = Bucket()
    assets.save_asset(bucket, "Page-abcdefgh.js", b"original")
    assets.save_asset(bucket, "Page-abcdefgh.js", b"original")
    with pytest.raises(RuntimeError):
        assets.save_asset(bucket, "Page-abcdefgh.js", b"different")
    assert bucket.objects[assets.PREFIX + "Page-abcdefgh.js"] == b"original"


def test_storage_outage_returns_recoverable_503(retained, monkeypatch):
    client, bucket = retained
    def fail(_):
        raise RuntimeError("Storage unavailable")
    monkeypatch.setattr(bucket, "download", fail)
    assert client.get("/assets/OldPage-12345678.js").status_code == 503


@pytest.mark.parametrize("body", [
    {"statusCode": "404", "error": "not_found", "message": "Object not found"},
    {"code": "NoSuchKey", "message": "The resource does not exist"},
])
def test_legacy_storage_400_missing_object_is_404(retained, monkeypatch, body):
    client, bucket = retained
    def fail(_):
        response = httpx.Response(400, json=body, request=httpx.Request("GET", "https://storage.test/private"))
        response.raise_for_status()
    monkeypatch.setattr(bucket, "download", fail)
    assert client.get("/assets/OldPage-12345678.js").status_code == 404


def test_archive_read_retries_transient_failure_without_logging_credentials(monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("temporary outage", request=request)
        return httpx.Response(200, content=b"old bundle")
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    bucket = assets.ArchiveBucket(Bucket(), "https://storage.test", "private-key", "attachments")
    bucket.reader.close()
    with httpx.Client(transport=httpx.MockTransport(respond)) as reader:
        bucket.reader = reader
        assert bucket.download(assets.PREFIX + "Page-abcdefgh.js") == b"old bundle"
    assert len(requests) == 2


def test_duplicate_final_upload_verifies_concurrent_publisher(monkeypatch):
    bucket = Bucket()
    uploads = []
    def race(name, content, file_options):
        uploads.append(name)
        if len(uploads) == 4:
            bucket.objects[name] = content
        raise RuntimeError("already exists")
    monkeypatch.setattr(bucket, "upload", race)
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    assets.save_asset(bucket, "Page-abcdefgh.js", b"same content")
    assert len(uploads) == 4


def test_archive_outage_does_not_attempt_duplicate_upload(monkeypatch):
    bucket = Bucket()
    def unavailable(_):
        raise RuntimeError("temporary storage outage")
    monkeypatch.setattr(bucket, "download", unavailable)
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="Page-abcdefgh.js"):
        assets.save_asset(bucket, "Page-abcdefgh.js", b"new content")
    assert not bucket.objects


def test_first_deployment_archives_lazy_graph_and_only_marks_complete_after_success(monkeypatch):
    bucket = Bucket()
    original_client = httpx.Client
    requests = []
    def handle(request):
        requests.append(request.url.path)
        bodies = {
            "/index.html": '<script src="/assets/index-abcdefgh.js"></script>',
            "/assets/index-abcdefgh.js": 'import("./LazyPage-12345678.js"); "assets/LazyPage-12345678.css"',
            "/assets/LazyPage-12345678.js": "export default 'old lazy page'",
            "/assets/LazyPage-12345678.css": "body { color: red; }",
        }
        return httpx.Response(200, text=bodies[request.url.path])
    monkeypatch.setattr(assets.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    assert assets.bootstrap_live_assets(bucket, "https://app.test") == 3
    assert assets.PREFIX + "LazyPage-12345678.js" in bucket.objects
    assert assets.bootstrap_live_assets(bucket, "https://app.test") == 0
    assert requests[-1] == "/index.html"


def test_incomplete_archive_aborts_rollout(monkeypatch):
    bucket = Bucket()
    original_client = httpx.Client
    def handle(request):
        if request.url.path == "/index.html":
            return httpx.Response(200, text='<script src="/assets/index-abcdefgh.js"></script>')
        return httpx.Response(503)
    monkeypatch.setattr(assets.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="index-abcdefgh.js"):
        assets.bootstrap_live_assets(bucket, "https://app.test")
    assert not any("manifests/" in key for key in bucket.objects)


def test_legacy_live_fetch_retries_timeout_then_uses_archived_dependencies(monkeypatch):
    bucket = Bucket()
    bucket.objects[assets.PREFIX + "LazyPage-12345678.js"] = b"export default 'retained'"
    original_client = httpx.Client
    requests = []
    def handle(request):
        requests.append(request.url.path)
        if request.url.path == "/index.html":
            return httpx.Response(200, text='<script src="/assets/index-abcdefgh.js"></script>')
        assert request.url.path == "/assets/index-abcdefgh.js"
        if requests.count(request.url.path) == 1:
            raise httpx.ReadTimeout("network timeout", request=request)
        return httpx.Response(200, text='import("./LazyPage-12345678.js")')
    monkeypatch.setattr(assets.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setattr(assets.time, "sleep", lambda _: None)
    assert assets.bootstrap_live_assets(bucket, "https://app.test") == 2
    assert requests == ["/index.html", "/assets/index-abcdefgh.js", "/assets/index-abcdefgh.js"]


def test_legacy_missing_asset_fails_once_without_complete_marker(monkeypatch):
    bucket = Bucket()
    original_client = httpx.Client
    requests = []
    def handle(request):
        requests.append(request.url.path)
        if request.url.path == "/index.html":
            return httpx.Response(200, text='<script src="/assets/index-abcdefgh.js"></script>')
        return httpx.Response(404)
    monkeypatch.setattr(assets.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(RuntimeError, match="index-abcdefgh.js"):
        assets.bootstrap_live_assets(bucket, "https://app.test")
    assert len(requests) == 2
    assert not any("manifests/" in key for key in bucket.objects)


def test_publish_build_verifies_bytes_without_contacting_live_site(tmp_path, monkeypatch):
    bucket = Bucket()
    root = tmp_path / "assets"
    root.mkdir()
    (root / "Page-abcdefgh.js").write_bytes(b"export default 1")
    monkeypatch.setattr(assets.settings, "static_dir", str(tmp_path))
    monkeypatch.setattr(assets, "archive_bucket", lambda: bucket)
    def forbidden(*args, **kwargs):
        raise AssertionError("Routine publishing must not crawl the live site")
    monkeypatch.setattr(assets.httpx, "Client", forbidden)
    assert assets.publish_build() == 1
    manifests = [value for key, value in bucket.objects.items() if "releases/" in key]
    assert len(manifests) == 1
    assert b"Page-abcdefgh.js" in manifests[0]


def test_publish_build_does_not_mark_unreadable_archive_complete(tmp_path, monkeypatch):
    bucket = Bucket()
    root = tmp_path / "assets"
    root.mkdir()
    (root / "Page-abcdefgh.js").write_bytes(b"export default 1")
    monkeypatch.setattr(assets.settings, "static_dir", str(tmp_path))
    monkeypatch.setattr(assets, "archive_bucket", lambda: bucket)
    # Reads remain missing even after the uploader reports success.
    monkeypatch.setattr(bucket, "upload", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="not found"):
        assets.publish_build()
    assert not any("releases/" in key for key in bucket.objects)
