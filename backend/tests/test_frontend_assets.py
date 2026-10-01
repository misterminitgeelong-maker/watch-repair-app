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
    with pytest.raises(httpx.HTTPStatusError):
        assets.bootstrap_live_assets(bucket, "https://app.test")
    assert not any("manifests/" in key for key in bucket.objects)
