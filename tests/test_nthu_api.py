"""Test cho nthu_api.py. Chạy:  pip install pytest   rồi   python -m pytest"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nthu_api import (  # noqa: E402
    filter_announcements,
    list_offices,
    normalize,
    paginate,
)

HERE = os.path.dirname(__file__)

ITEMS = [
    {"title": "Scholarship news", "link": "", "date": "2026-11-20",
     "office": "Student Affairs", "language": "en"},
    {"title": "宿舍申請", "link": "", "date": "2026-11-18",
     "office": "Housing", "language": "zh-tw"},
    {"title": "Registration reminder", "link": "", "date": "2026-11-10",
     "office": "Registrar", "language": "en"},
]


def load_real_sample():
    """Mẫu JSON thật lấy từ NTHU Data API (3 đơn vị x 3 bài)."""
    with open(os.path.join(HERE, "api_sample.json"), encoding="utf-8") as f:
        return json.load(f)


def test_normalize_flattens_real_api_sample():
    items = normalize(load_real_sample())
    assert len(items) == 9                      # 3 đơn vị x 3 bài
    first = items[0]                            # mới nhất trước
    assert first["date"] == "2026-10-30"
    assert first["office"] == "教務處"
    assert first["language"] == "zh-tw"
    assert first["link"].startswith("https://academic.site.nthu.edu.tw/")
    assert [a["date"] for a in items] == sorted((a["date"] for a in items), reverse=True)


def test_normalize_keeps_language_per_department():
    items = normalize(load_real_sample())
    english = [a for a in items if a["language"] == "en"]
    assert len(english) == 3
    assert all(a["office"].startswith("總務處") for a in english)


def test_normalize_skips_bad_entries():
    data = [
        {"department": "A", "language": "en", "articles": [
            {"title": "ok", "link": "http://x", "date": "2026-01-01"},
            {"link": "no title"},   # không có tiêu đề -> bỏ qua
            "not a dict",           # không phải dict -> bỏ qua
        ]},
        {"department": "B", "language": "en", "articles": None},  # không có bài
        "not a dict",
    ]
    items = normalize(data)
    assert [a["title"] for a in items] == ["ok"]


def test_normalize_accepts_dict_wrapper():
    data = {"data": [{"department": "A", "articles": [{"title": "t", "date": "2026-01-01"}]}]}
    assert normalize(data)[0]["office"] == "A"


def test_filter_by_keyword_is_case_insensitive():
    result = filter_announcements(ITEMS, q="SCHOLAR")
    assert [a["title"] for a in result] == ["Scholarship news"]


def test_filter_by_office_language_and_keyword():
    assert filter_announcements(ITEMS, office="Housing") == [ITEMS[1]]
    assert filter_announcements(ITEMS, lang="en") == [ITEMS[0], ITEMS[2]]
    assert filter_announcements(ITEMS, office="Housing", q="scholar") == []


def test_list_offices_unique_sorted():
    assert list_offices(ITEMS + ITEMS) == ["Housing", "Registrar", "Student Affairs"]


def test_paginate_splits_and_clamps_page_numbers():
    items = list(range(45))
    page_items, page, total_pages = paginate(items, 1, per_page=20)
    assert (len(page_items), page, total_pages) == (20, 1, 3)
    page_items, page, _ = paginate(items, 3, per_page=20)
    assert (len(page_items), page) == (5, 3)
    _, page, _ = paginate(items, 99, per_page=20)   # quá lớn -> trang cuối
    assert page == 3
    _, page, _ = paginate(items, -4, per_page=20)   # âm -> trang 1
    assert page == 1
    assert paginate([], 1) == ([], 1, 1)            # rỗng vẫn có 1 trang
