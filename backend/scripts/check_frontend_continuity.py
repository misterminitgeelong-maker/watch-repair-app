"""Snapshot a live asset graph, then verify its exact bytes after a release.

python scripts/check_frontend_continuity.py snapshot https://mainspring.au old-build.json
python scripts/check_frontend_continuity.py verify https://mainspring.au old-build.json
Only public hashed build assets are fetched; no sessions or API data are collected.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.frontend_assets import NAME, REFERENCES, get_with_retry


def fetch_asset(client, base_url, name):
    if not NAME.fullmatch(name):
        raise ValueError("Invalid hashed asset name")
    response = get_with_retry(client, base_url.rstrip("/") + "/assets/" + name)
    content_type = response.headers.get("content-type", "").split(";")[0]
    if name.endswith(".js") and "javascript" not in content_type:
        raise RuntimeError(f"Incorrect JavaScript MIME type for {name}")
    if name.endswith(".css") and content_type != "text/css":
        raise RuntimeError(f"Incorrect CSS MIME type for {name}")
    return response.content


def snapshot(client, base_url):
    index = get_with_retry(client, base_url.rstrip("/") + "/index.html")
    pending = set(REFERENCES.findall(index.text))
    manifest = {}
    if not pending:
        raise RuntimeError("Live index has no hashed assets")
    def read(name):
        content = fetch_asset(client, base_url, name)
        refs = set(REFERENCES.findall(content.decode("utf-8"))) if name.endswith((".js", ".css")) else set()
        return name, hashlib.sha256(content).hexdigest(), refs
    with ThreadPoolExecutor(max_workers=4) as workers:
        while pending:
            if len(manifest) + len(pending) > 500:
                raise RuntimeError("Asset graph exceeds limit")
            results = list(workers.map(read, pending))
            for name, digest, _ in results:
                manifest[name] = digest
            pending = set().union(*(refs for _, _, refs in results)) - manifest.keys()
    return manifest


def verify(client, base_url, manifest):
    if not manifest or len(manifest) > 500:
        raise ValueError("Invalid release manifest")
    def check(item):
        name, expected = item
        if hashlib.sha256(fetch_asset(client, base_url, name)).hexdigest() != expected:
            raise RuntimeError(f"Previous release asset changed: {name}")
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(check, manifest.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["snapshot", "verify"])
    parser.add_argument("base_url")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        if args.mode == "snapshot":
            manifest = snapshot(client, args.base_url)
            args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            verify(client, args.base_url, manifest)
    print(f"Frontend continuity {args.mode}: {len(manifest)} assets verified")
