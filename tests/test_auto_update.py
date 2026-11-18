"""Test tự cập nhật thông báo: chọn bản lưu mới hơn, lưu ra file khác, gửi file lên PythonAnywhere."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import nthu_api  # noqa: E402
import save_announcements  # noqa: E402
import upload_snapshot  # noqa: E402

API_DATA = [{"department": "教務處", "language": "zh-tw",
             "articles": [{"title": "講座 12月1日", "link": "https://example.com/a", "date": "2026-11-15"}]}]


def write(path, saved, title="講座 12月1日"):
    data = [{"department": "教務處", "language": "zh-tw", "articles": [{"title": title, "link": "x", "date": "2026-11-15"}]}]
    path.write_text(json.dumps(nthu_api.make_snapshot(data, saved), ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def files(monkeypatch, tmp_path):
    old, latest = tmp_path / "data.json", tmp_path / "instance.json"
    monkeypatch.setattr(nthu_api, "SNAPSHOT_FILE", old)
    monkeypatch.setattr(nthu_api, "LATEST_SNAPSHOT_FILE", latest)
    return old, latest


# ---------- chọn bản lưu mới hơn ----------

def test_newest_snapshot_picks_latest_saved_at():
    assert nthu_api.newest_snapshot([(["a"], "2026-11-18 11:40"), (["b"], "2026-11-19 06:17")]) == (["b"], "2026-11-19 06:17")
    assert nthu_api.newest_snapshot([(None, None), (["a"], "")]) == (["a"], "")
    assert nthu_api.newest_snapshot([(None, None), (None, None)]) == (None, None)


def test_load_snapshot_uses_the_daily_upload_when_newer(files):
    old, latest = files
    write(old, datetime(2026, 11, 18, 11, 40), "old title")
    assert nthu_api.load_snapshot()[1] == "2026-11-18 11:40"           # chỉ có bản trong git
    write(latest, datetime(2026, 11, 19, 6, 17), "new title")
    items, saved_at = nthu_api.load_snapshot()
    assert saved_at == "2026-11-19 06:17" and items[0]["title"] == "new title"


def test_load_snapshot_ignores_broken_upload(files):
    old, latest = files
    write(old, datetime(2026, 11, 18, 11, 40))
    latest.write_text("{broken", encoding="utf-8")
    assert nthu_api.load_snapshot()[1] == "2026-11-18 11:40"


# ---------- tools/save_announcements.py --output ----------

class FakeResponse:
    status_code = 200

    def __init__(self, data=None):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_output_from_args():
    assert save_announcements.output_from_args(["--output", "x.json"]) == "x.json"
    assert save_announcements.output_from_args([]) is None
    assert save_announcements.output_from_args(["--output"]) is None


def test_save_to_other_file_in_taiwan_time(files, monkeypatch, tmp_path):
    monkeypatch.setattr(save_announcements.requests, "get", lambda *a, **k: FakeResponse(API_DATA))
    out = tmp_path / "out" / "snapshot.json"
    assert save_announcements.main(str(out)) == 0
    assert not files[0].exists()                                       # không đụng bản trong data/
    saved_at = json.loads(out.read_text(encoding="utf-8"))["saved_at"]
    now_tw = datetime.now(nthu_api_tz()).strftime("%Y-%m-%d %H")
    assert saved_at.startswith(now_tw)                                 # giờ Đài Loan, không phải UTC


def nthu_api_tz():
    from calendar_logic import TAIWAN_TZ
    return TAIWAN_TZ


# ---------- tools/upload_snapshot.py ----------

ENV = {"PA_USERNAME": "nthuapp", "PA_TOKEN": "secret-token"}


def test_target_and_url():
    assert upload_snapshot.target_path("nthuapp") == "/home/nthuapp/NTHU-app/instance/announcements_snapshot.json"
    assert upload_snapshot.target_path("u", "/home/u/app/") == "/home/u/app/instance/announcements_snapshot.json"
    assert upload_snapshot.upload_url("www.pythonanywhere.com", "nthuapp", "/home/nthuapp/x.json") == \
        "https://www.pythonanywhere.com/api/v0/user/nthuapp/files/path/home/nthuapp/x.json"


def test_read_settings():
    assert upload_snapshot.read_settings({}) is None
    assert upload_snapshot.read_settings({"PA_USERNAME": "u"}) is None
    settings = upload_snapshot.read_settings(ENV)
    assert settings["host"] == "www.pythonanywhere.com" and settings["project_dir"] == ""


def test_upload_sends_file_with_token(monkeypatch, tmp_path, capsys):
    snap = tmp_path / "snapshot.json"
    snap.write_text("{}", encoding="utf-8")
    sent = {}

    def fake_post(url, files, headers, timeout):
        sent.update(url=url, content=files["content"].read(), auth=headers["Authorization"])
        response = FakeResponse()
        response.status_code = 201
        return response

    monkeypatch.setattr(upload_snapshot.requests, "post", fake_post)
    assert upload_snapshot.main([str(snap)], ENV) == 0
    assert sent["url"].endswith("/files/path/home/nthuapp/NTHU-app/instance/announcements_snapshot.json")
    assert sent["content"] == b"{}" and sent["auth"] == "Token secret-token"
    assert "secret-token" not in capsys.readouterr().out                # không bao giờ in token ra log


def test_upload_errors(monkeypatch, tmp_path, capsys):
    snap = tmp_path / "snapshot.json"
    snap.write_text("{}", encoding="utf-8")
    assert upload_snapshot.main([], ENV) == 1                           # thiếu tên file
    assert upload_snapshot.main([str(tmp_path / "nope.json")], ENV) == 1
    assert upload_snapshot.main([str(snap)], {}) == 1                   # thiếu secret
    bad = FakeResponse()
    bad.status_code = 401
    monkeypatch.setattr(upload_snapshot.requests, "post", lambda *a, **k: bad)
    assert upload_snapshot.main([str(snap)], ENV) == 1                  # token sai

    def down(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(upload_snapshot.requests, "post", down)
    assert upload_snapshot.main([str(snap)], ENV) == 1
    assert "secret-token" not in capsys.readouterr().out
