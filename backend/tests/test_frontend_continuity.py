import hashlib
import httpx
import pytest
from scripts.check_frontend_continuity import snapshot, verify


def test_snapshot_includes_lazy_assets_and_rejects_changed_previous_bytes():
    bodies = {
        "/index.html": ('<script src="/assets/index-abcdefgh.js"></script>', "text/html"),
        "/assets/index-abcdefgh.js": ('import("./LazyPage-12345678.js")', "text/javascript"),
        "/assets/LazyPage-12345678.js": ("original lazy page", "text/javascript"),
    }
    def respond(request):
        body, mime = bodies[request.url.path]
        return httpx.Response(200, content=body.encode(), headers={"content-type": mime})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        manifest = snapshot(client, "https://app.test")
        assert set(manifest) == {"index-abcdefgh.js", "LazyPage-12345678.js"}
        verify(client, "https://app.test", manifest)
        bodies["/assets/LazyPage-12345678.js"] = ("different release", "text/javascript")
        with pytest.raises(RuntimeError, match="LazyPage-12345678.js"):
            verify(client, "https://app.test", manifest)


def test_html_fallback_cannot_pass_as_javascript():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
            200, text="SPA fallback", headers={"content-type": "text/html"}))) as client:
        with pytest.raises(RuntimeError, match="MIME type"):
            verify(client, "https://app.test", {"index-abcdefgh.js": hashlib.sha256(b"SPA fallback").hexdigest()})
