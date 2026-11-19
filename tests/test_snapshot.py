"""Test bản lưu thông báo (dùng khi server không gọi được NTHU Data API)."""
import json
import os
import sys
from datetime import datetime

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module  # noqa: E402
import nthu_api  # noqa: E402

API_DATA = [{"department": "教務處", "language": "zh-tw", "articles": [
    {"title": "獎學金申請公告", "link": "https://example.com/a", "date": "2026-11-15"},
    {"title": "Course registration reminder", "link": "https://example.com/b", "date": "2026-11-17"}]}]


class FakeResponse:
    def __init__(self, data=None, fail=False):
        self.data, self.fail = data, fail

    def raise_for_status(self):
        if self.fail:
            raise requests.HTTPError("500")

    def json(self):
        return self.data


@pytest.fixture
def fresh(monkeypatch, tmp_path):
    """Xóa bộ nhớ tạm và trỏ bản lưu vào thư mục tạm của test."""
    monkeypatch.setattr(nthu_api, "_cache", {"time": 0.0, "items": [], "notice": None})
    path = tmp_path / "snapshot.json"
    monkeypatch.setattr(nthu_api, "SNAPSHOT_FILE", path)
    monkeypatch.setattr(nthu_api, "LATEST_SNAPSHOT_FILE", tmp_path / "latest.json")
    return path


def api_fails(*args, **kwargs):
    raise requests.ConnectionError("blocked by proxy")


def write_snapshot(path, data=API_DATA):
    path.write_text(json.dumps(nthu_api.make_snapshot(data, datetime(2026, 11, 18, 11, 40)), ensure_ascii=False),
                    encoding="utf-8")


def test_make_and_load_snapshot(fresh):
    write_snapshot(fresh)
    items, saved_at = nthu_api.load_snapshot()
    assert saved_at == "2026-11-18 11:40"
    assert [i["title"] for i in items] == ["Course registration reminder", "獎學金申請公告"]   # mới nhất trước
    assert items[1]["category"] == "Scholarship"                                                # vẫn tự phân loại


@pytest.mark.parametrize("content", [None, "not json", "[1, 2]", '{"saved_at": "x", "data": []}', '{"data": "oops"}'])
def test_load_snapshot_missing_or_broken(fresh, content):
    if content is not None:
        fresh.write_text(content, encoding="utf-8")
    assert nthu_api.load_snapshot() == (None, None)


def test_live_api_wins(fresh, monkeypatch):
    write_snapshot(fresh, [{"department": "X", "articles": [{"title": "old", "date": "2026-01-01"}]}])
    monkeypatch.setattr(nthu_api.requests, "get", lambda *a, **k: FakeResponse(API_DATA))
    items, notice = nthu_api.fetch_announcements()
    assert notice is None and len(items) == 2


def test_snapshot_used_when_api_fails(fresh, monkeypatch):
    write_snapshot(fresh)
    monkeypatch.setattr(nthu_api.requests, "get", api_fails)
    items, notice = nthu_api.fetch_announcements()
    assert notice == {"kind": "snapshot", "saved_at": "2026-11-18 11:40", "reason": "Could not reach the NTHU Data API."}
    assert len(items) == 2 and not nthu_api.is_sample(notice)


def test_snapshot_used_when_api_returns_nothing(fresh, monkeypatch):
    write_snapshot(fresh)
    monkeypatch.setattr(nthu_api.requests, "get", lambda *a, **k: FakeResponse([]))
    items, notice = nthu_api.fetch_announcements()
    assert notice["kind"] == "snapshot" and notice["reason"] == "The NTHU Data API returned no usable data."


def test_sample_when_api_fails_and_no_snapshot(fresh, monkeypatch):
    monkeypatch.setattr(nthu_api.requests, "get", api_fails)
    items, notice = nthu_api.fetch_announcements()
    assert items is nthu_api.SAMPLE_ANNOUNCEMENTS and nthu_api.is_sample(notice)


def test_failure_result_is_cached(fresh, monkeypatch):
    calls = []

    def counting_fail(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError("blocked")
    write_snapshot(fresh)
    monkeypatch.setattr(nthu_api.requests, "get", counting_fail)
    nthu_api.fetch_announcements()
    nthu_api.fetch_announcements()
    assert len(calls) == 1                                    # lần hai lấy từ bộ nhớ tạm, không gọi lại API


def test_is_sample():
    assert nthu_api.is_sample({"kind": "sample"}) and not nthu_api.is_sample({"kind": "snapshot"})
    assert not nthu_api.is_sample(None) and not nthu_api.is_sample("error")


# ---------- trang web ----------

SNAP_NOTICE = {"kind": "snapshot", "saved_at": "2026-11-18 11:40", "reason": "Could not reach the NTHU Data API."}


def set_stale(monkeypatch, stale):
    """Cố định "bản lưu cũ hay mới" để test không phụ thuộc ngày giờ lúc chạy."""
    monkeypatch.setattr(app_module, "is_stale", lambda saved_at, now: stale)


def test_home_shows_snapshot_items_with_date(app, monkeypatch):
    items = nthu_api.normalize(API_DATA)
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, SNAP_NOTICE))
    set_stale(monkeypatch, False)
    html = app.test_client().get("/").get_data(as_text=True)
    assert "獎學金申請公告" in html and "Updated 2026-11-18 11:40" in html and "saved-note stale" not in html
    assert "unavailable right now" not in html
    set_stale(monkeypatch, True)
    assert "saved-note stale" in app.test_client().get("/").get_data(as_text=True)


def test_fresh_snapshot_shows_quiet_note_not_alert(app, monkeypatch):
    items = nthu_api.normalize(API_DATA)
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, SNAP_NOTICE))
    set_stale(monkeypatch, False)
    html = app.test_client().get("/announcements").get_data(as_text=True)
    assert "Updated 2026-11-18 11:40" in html and 'class="alert"' not in html


def test_announcements_page_snapshot_and_sample_messages(app, monkeypatch):
    items = nthu_api.normalize(API_DATA)
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, SNAP_NOTICE))
    set_stale(monkeypatch, True)                         # cũ hơn 2 ngày -> cảnh báo vàng
    html = app.test_client().get("/announcements").get_data(as_text=True)
    assert "Showing announcements saved on 2026-11-18 11:40" in html and "sample data" not in html
    monkeypatch.setattr(app_module, "fetch_announcements",
                        lambda: (nthu_api.SAMPLE_ANNOUNCEMENTS, {"kind": "sample", "reason": "Could not reach the NTHU Data API."}))
    html = app.test_client().get("/announcements").get_data(as_text=True)
    assert "Showing sample data." in html and "Could not reach the NTHU Data API." in html


def test_snapshot_message_in_chinese(app, monkeypatch):
    items = nthu_api.normalize(API_DATA)
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, SNAP_NOTICE))
    set_stale(monkeypatch, True)
    client = app.test_client()
    html = client.get("/announcements", headers={"Accept-Language": "zh-TW"}).get_data(as_text=True)
    assert "顯示 2026-11-18 11:40 儲存的公告" in html
    set_stale(monkeypatch, False)
    assert "更新於 2026-11-18 11:40" in client.get("/announcements", headers={"Accept-Language": "zh-TW"}).get_data(as_text=True)


def test_is_stale():
    from datetime import datetime as dt
    now = dt(2026, 11, 20, 12, 0)
    assert not nthu_api.is_stale("2026-11-19 06:17", now)        # 30 tiếng
    assert nthu_api.is_stale("2026-11-18 11:00", now)            # hơn 48 tiếng
    assert nthu_api.is_stale("", now) and nthu_api.is_stale(None, now) and nthu_api.is_stale("hôm qua", now)


def test_save_script_writes_valid_snapshot(fresh, monkeypatch):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))
    import save_announcements
    monkeypatch.setattr(save_announcements.requests, "get", lambda *a, **k: FakeResponse(API_DATA))
    assert save_announcements.main() == 0
    items, saved_at = nthu_api.load_snapshot()
    assert len(items) == 2 and saved_at


def test_save_script_keeps_old_file_on_error(fresh, monkeypatch):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))
    import save_announcements
    write_snapshot(fresh)
    before = fresh.read_text(encoding="utf-8")
    monkeypatch.setattr(save_announcements.requests, "get", api_fails)
    assert save_announcements.main() == 1
    monkeypatch.setattr(save_announcements.requests, "get", lambda *a, **k: FakeResponse([]))
    assert save_announcements.main() == 1
    assert fresh.read_text(encoding="utf-8") == before


def test_failed_api_is_not_retried_for_an_hour(fresh, monkeypatch):
    calls = []

    def counting_fail(*args, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise requests.ConnectionError("blocked")
    write_snapshot(fresh)
    monkeypatch.setattr(nthu_api.requests, "get", counting_fail)
    clock = [1_000_000.0]
    monkeypatch.setattr(nthu_api.time, "time", lambda: clock[0])
    nthu_api.fetch_announcements()
    assert calls == [nthu_api.API_TIMEOUT]                    # chờ ngắn (3 s kết nối), không phải 15 s
    clock[0] += nthu_api.CACHE_SECONDS + 1                    # bộ nhớ tạm hết hạn...
    items, notice = nthu_api.fetch_announcements()
    assert len(calls) == 1 and notice["kind"] == "snapshot"   # ...nhưng chưa tới 1 tiếng: không gọi API lại
    clock[0] += nthu_api.API_RETRY_SECONDS
    nthu_api.fetch_announcements()
    assert len(calls) == 2                                    # sau 1 tiếng mới thử lại


def test_snapshot_file_is_parsed_once_until_it_changes(fresh, monkeypatch):
    write_snapshot(fresh)
    parsed = []
    original = nthu_api._parse_snapshot
    monkeypatch.setattr(nthu_api, "_parse_snapshot", lambda path: parsed.append(path) or original(path))
    first, _ = nthu_api.load_snapshot(fresh)
    second, _ = nthu_api.load_snapshot(fresh)
    assert len(parsed) == 1 and first is second               # cùng một danh sách -> kết quả tính sẵn vẫn dùng được
    write_snapshot(fresh, [{"department": "X", "language": "en",
                            "articles": [{"title": "Brand new notice", "link": "x", "date": "2026-11-19"}]}])
    import os
    os.utime(fresh, ns=(fresh.stat().st_atime_ns, fresh.stat().st_mtime_ns + 1_000_000))
    third, _ = nthu_api.load_snapshot(fresh)
    assert len(parsed) == 2 and third[0]["title"] == "Brand new notice"
