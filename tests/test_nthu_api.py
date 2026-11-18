"""Test cho nthu_api.py. Chạy:  pip install pytest   rồi   python -m pytest"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nthu_api import (  # noqa: E402
    SAMPLE_ANNOUNCEMENTS,
    category_counts,
    CATEGORY_NAMES,
    classify,
    filter_announcements,
    list_offices,
    normalize,
    paginate,
)

HERE = os.path.dirname(__file__)

ITEMS = [
    {"title": "Scholarship news", "link": "", "date": "2026-11-20",
     "office": "Student Affairs", "language": "en", "category": "Scholarship"},
    {"title": "宿舍申請", "link": "", "date": "2026-11-18",
     "office": "Housing", "language": "zh-tw", "category": "Dorm"},
    {"title": "Registration reminder", "link": "", "date": "2026-11-10",
     "office": "Registrar", "language": "en", "category": "Registration"},
]


def load_real_sample():
    """Mẫu JSON thật lấy từ NTHU Data API (3 đơn vị x 3 bài)."""
    with open(os.path.join(HERE, "api_sample.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------- normalize ----------

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


def test_normalize_adds_category_to_every_item():
    items = normalize(load_real_sample())
    assert all("category" in a for a in items)
    job = next(a for a in items if "徵才" in a["title"])
    assert job["category"] == "Careers"


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


# ---------- classify / category_counts ----------

def test_classify_english_and_chinese():
    assert classify("Scholarship application opens") == "Scholarship"
    assert classify("國科會 獎助學金 申請") == "Scholarship"
    assert classify("宿舍床位申請") == "Dorm"
    assert classify("115學年度第1學期 加退選 公告") == "Registration"
    assert classify("Spring concert tickets") == "Events"


def test_classify_is_case_insensitive_and_has_default():
    assert classify("DORM application") == "Dorm"
    assert classify("Three pruning notice on campus") == "Campus notices"
    assert classify("Faculty news and photos") == "Other"


def test_classify_order_matters_careers_before_registration():
    # "career fair registration" chứa cả "career" và "registration" -> Careers thắng
    assert classify("Campus career fair registration open") == "Careers"


def test_sample_announcements_have_categories():
    assert all(a["category"] for a in SAMPLE_ANNOUNCEMENTS)


def test_category_counts_fixed_order_and_skips_empty():
    items = ITEMS + [{"title": "x", "office": "O", "language": "en", "category": "Dorm"}]
    assert category_counts(items) == [("Scholarship", 1), ("Dorm", 2), ("Registration", 1)]


# ---------- filter / offices / paginate ----------

def test_filter_by_keyword_is_case_insensitive():
    result = filter_announcements(ITEMS, q="SCHOLAR")
    assert [a["title"] for a in result] == ["Scholarship news"]


def test_filter_by_office_language_and_keyword():
    assert filter_announcements(ITEMS, office="Housing") == [ITEMS[1]]
    assert filter_announcements(ITEMS, lang="en") == [ITEMS[0], ITEMS[2]]
    assert filter_announcements(ITEMS, office="Housing", q="scholar") == []


def test_filter_by_category():
    assert filter_announcements(ITEMS, category="Dorm") == [ITEMS[1]]
    assert filter_announcements(ITEMS, category="Dorm", lang="en") == []


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


# ---------- ngày đăng sai và bài trùng (lỗi thấy trên web thật) ----------
from nthu_api import clean_date, normalize  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("2026-11-18", "2026-11-18"), ("2026/11/18", "2026-11-18"), ("2026.1.5", "2026-01-05"), (" 2026-11-18 ", "2026-11-18"),
    ("8", ""), ("1", ""), ("", ""), (None, ""), ("2026-02-30", ""), ("2026-13-01", ""), ("18/11/2026", ""),
    ("2026-11-18 10:00", ""), (20261118, ""),
])
def test_clean_date(raw, expected):
    assert clean_date(raw) == expected


def test_normalize_drops_fake_dates_so_they_do_not_lead_the_list():
    data = [{"department": "人事室", "articles": [
        {"title": "old pinned", "date": "8"}, {"title": "real new", "date": "2026-11-18"},
        {"title": "older", "date": "2026/11/01"}]}]
    items = normalize(data)
    assert [i["title"] for i in items] == ["real new", "older", "old pinned"]
    assert items[1]["date"] == "2026-11-01" and items[2]["date"] == ""


def test_normalize_removes_duplicates_but_keeps_different_offices_or_dates():
    data = [{"department": "宿舍", "articles": [{"title": "修繕系統啟用", "date": "2026-11-18"},
                                              {"title": "修繕系統啟用 ", "date": "2026-11-18"},
                                              {"title": "修繕系統啟用", "date": "2026-11-17"}]},
            {"department": "學務處", "articles": [{"title": "修繕系統啟用", "date": "2026-11-18"}]}]
    items = normalize(data)
    assert len(items) == 3
    assert sorted((i["office"], i["date"]) for i in items) == [("學務處", "2026-11-18"), ("宿舍", "2026-11-17"), ("宿舍", "2026-11-18")]


# ---------- quy tắc phân loại mới (thử trên tiêu đề thật) ----------

@pytest.mark.parametrize("title,expected", [
    ("【誠徵】116科管院在職專班 招生「書審資料」工讀生", "Careers"),         # Careers đứng trước Admissions
    ("【HBA熱烈招生中】116健康政策與經營管理碩士在職專班", "Admissions"),
    ("校本部「第一高壓站改壓工程」停電施工公告", "Campus notices"),
    ("[POWER OUTAGE NOTICE] Main Campus First High-Voltage Substation", "Campus notices"),
    ("11/9(一)~12/26(六)校園公車時刻表", "Campus notices"),
    ("【公告】116年度台灣聯大交換學生計畫-申請公告", "Exchange"),
    ("Accepting applications for Credit Transfer for the 2025 Spring Semester", "Registration"),
    ("【公告】2027原相大專院校創新競賽（12/8 報名截止）", "Events"),
    ("2026/1/8(四) 新書發表會", "Events"),
    ("Launch of the New Student Dormitory Repair Service", "Dorm"),
    ("恭賀本所教授榮獲傑出貢獻獎", "Other"),
])
def test_classify_real_titles(title, expected):
    assert classify(title) == expected


def test_english_keywords_match_whole_words_only():
    assert classify("Summer camp on campus") == "Other"           # "camp"/"campus" không phải từ khóa nào
    assert classify("International students welcome") == "Other"  # "intern" không khớp "international"
    assert classify("Intern wanted") == "Careers"
    assert classify("Department of Power Mechanical Engineering news") == "Other"


def test_category_names_list():
    assert CATEGORY_NAMES[-1] == "Other" and "Campus notices" in CATEGORY_NAMES and len(set(CATEGORY_NAMES)) == len(CATEGORY_NAMES)


# ---------- gom đơn vị ----------
from nthu_api import GROUP_PREFIX, filter_announcements, group_offices, office_group  # noqa: E402


@pytest.mark.parametrize("office,group", [
    ("教務處註冊組", "教務處"), ("教務處", "教務處"), ("教務處英語教學精進中心", "教務處"),
    ("電機資訊學院光電工程研究所", "電機資訊學院"), ("清華學院住宿書院", "清華學院"),
    ("國際產學營運總中心NVIDIA-國立清華大學聯合創新中心", "國際產學營運總中心"),
    ("合校停招系所聯合辦事處（教務處支援）應用數學系", "合校停招系所聯合辦事處"),
    ("學務處衛生保健組(醫輔大樓1樓)", "學務處"), ("人事室", "人事室"), ("清華公佈欄", "清華公佈欄"),
    ("Office of Global Affairs", "Office of Global Affairs"),
])
def test_office_group(office, group):
    assert office_group(office) == group


def test_group_offices_and_group_filter():
    offices = ["教務處", "教務處註冊組", "人事室", "理學院物理學系"]
    groups = group_offices(offices)
    assert [g["name"] for g in groups] == sorted(["教務處", "人事室", "理學院"])
    assert next(g for g in groups if g["name"] == "教務處")["offices"] == ["教務處", "教務處註冊組"]
    items = [{"title": t, "office": o, "language": "zh-tw", "category": "Other", "date": ""}
             for t, o in [("a", "教務處註冊組"), ("b", "教務處"), ("c", "人事室")]]
    assert [i["title"] for i in filter_announcements(items, office=GROUP_PREFIX + "教務處")] == ["a", "b"]
    assert [i["title"] for i in filter_announcements(items, office="教務處")] == ["b"]       # chọn đúng một đơn vị
    assert filter_announcements(items, office=GROUP_PREFIX + "不存在") == []
