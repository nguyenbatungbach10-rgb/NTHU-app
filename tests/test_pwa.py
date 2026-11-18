"""Test cài web như app (PWA): manifest, service worker, trang offline, icon."""
import json
from pathlib import Path

import pwa

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_manifest_is_installable(make_browser):
    response = make_browser().client.get("/manifest.webmanifest")
    assert response.status_code == 200 and response.mimetype == "application/manifest+json"
    data = json.loads(response.data)
    assert data["display"] == "standalone" and data["start_url"].startswith("/") and data["name"]
    sizes = {i["sizes"] for i in data["icons"]}
    assert {"192x192", "512x512"} <= sizes and any(i["purpose"] == "maskable" for i in data["icons"])
    for icon in data["icons"]:
        assert (STATIC / icon["src"].removeprefix("/static/")).is_file()


def test_manifest_is_translated(make_browser):
    client = make_browser().client
    data = json.loads(client.get("/manifest.webmanifest", headers={"Accept-Language": "zh-TW"}).data)
    assert data["lang"] == "zh-TW" and data["short_name"] == "清大助理"


def test_service_worker_served_from_root(make_browser):
    response = make_browser().client.get("/sw.js")
    body = response.get_data(as_text=True)
    assert response.status_code == 200 and response.mimetype == "text/javascript"
    assert response.headers["Cache-Control"] == "no-cache"
    assert f'const CACHE_VERSION = "{pwa.CACHE_VERSION}"' in body and '"/offline"' in body
    assert "addEventListener(\"fetch\"" in body


def test_offline_page_and_head_tags(make_browser):
    client = make_browser().client
    assert "You are offline" in client.get("/offline").get_data(as_text=True)
    html = client.get("/").get_data(as_text=True)
    assert 'rel="manifest"' in html and 'name="theme-color"' in html and "apple-touch-icon" in html


def test_offline_files_exist(make_browser):
    client = make_browser().client
    for path in pwa.OFFLINE_FILES:
        assert client.get(path).status_code == 200, path
