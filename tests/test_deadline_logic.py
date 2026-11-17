"""Test đọc ngày hạn / ngày diễn ra từ tiêu đề thông báo. Có dùng các tiêu đề thật trong api_sample.json."""
import pytest

import deadline_logic as d


@pytest.mark.parametrize("title,posted,expected", [
    # ---- tiêu đề thật của NTHU ----
    ("本室於115年10月08日(星期四)辦理經費報支說明講習", "2026-09-28", ["2026-10-08"]),                 # năm Dân Quốc 115 = 2026
    ("Outdoor disinfection operations on Nanda campus(115.03.21)", "2026-03-15", ["2026-03-21"]),
    ("Three pruning Notice on Nanda campus.(114/12/09-114/12/11)", "2025-12-05", ["2025-12-09", "2025-12-11"]),
    ("115年國科會專題研究計畫結案經費報支注意事項", "2026-10-01", []),                                 # chỉ có năm, không có ngày
    ("114學年度畢業生致詞代表甄選結果", "2026-10-01", []),                                              # năm học, không phải ngày
    ("【徵才】綜合教務組誠徵專案組員1名", "2026-10-01", []),
    # ---- các kiểu viết khác ----
    ("Deadline 2026-11-20", "2026-11-01", ["2026-11-20"]),
    ("Deadline 2026/11/20", "2026-11-01", ["2026-11-20"]),
    ("Deadline 2026.11.20", "2026-11-01", ["2026-11-20"]),
    ("截止日期2026年11月20日", "2026-11-01", ["2026-11-20"]),
    ("申請至11月20日止", "2026-11-01", ["2026-11-20"]),
    ("11月20號報到", "2026-11-01", ["2026-11-20"]),
    ("Application deadline: November 20, 2026", "2026-11-01", ["2026-11-20"]),
    ("Due Nov. 20", "2026-11-01", ["2026-11-20"]),
    ("Closes Nov 20th", "2026-11-01", ["2026-11-20"]),
    ("Event on 20 November 2026", "2026-11-01", ["2026-11-20"]),
    ("Event on 20th Nov", "2026-11-01", ["2026-11-20"]),
    ("Sept 5 orientation", "2026-08-30", ["2026-09-05"]),
    ("Applications open Nov 1 - Nov 20", "2026-10-28", ["2026-11-01", "2026-11-20"]),
])
def test_extract_dates(title, posted, expected):
    assert d.extract_dates(title, posted) == expected


def test_year_is_inferred_closest_to_posted_date():
    assert d.extract_dates("1月15日前繳交", "2026-12-20") == ["2027-01-15"]     # đăng cuối năm, hạn đầu năm sau
    assert d.extract_dates("12月20日講座", "2026-12-25") == ["2026-12-20"]      # vừa diễn ra 5 ngày trước: giữ
    assert d.extract_dates("12月20日講座", "2027-01-05") == []                  # 16 ngày trước: bỏ (có thể là ngày tham chiếu)
    assert d.extract_dates("11月20日", "2026-11-01") == ["2026-11-20"]


def test_ignores_things_that_are_not_event_dates():
    assert d.extract_dates("2月30日 活動", "2026-02-01") == []                  # ngày không có thật
    assert d.extract_dates("Feb 30 deadline", "2026-02-01") == []
    assert d.extract_dates("Version 1.2.3 released", "2026-11-18") == []         # số phiên bản
    assert d.extract_dates("依據2026/01/05公告辦理", "2026-11-18") == []          # ngày tham chiếu cũ
    assert d.extract_dates("活動 2099/01/01", "2026-11-18") == []                # quá xa
    assert d.extract_dates("Room 301, 12 students", "2026-11-18") == []


def test_grace_period_boundary():
    assert d.extract_dates("11月11日", "2026-11-18") == ["2026-11-11"]            # đúng 7 ngày trước: giữ
    assert d.extract_dates("11月10日", "2026-11-18") == []                        # 8 ngày trước: bỏ


def test_duplicate_dates_are_listed_once_and_order_follows_text():
    assert d.extract_dates("11月25日 or 2026-11-20 or 11月25日", "2026-11-01") == ["2026-11-25", "2026-11-20"]


def test_extract_dates_handles_bad_input():
    assert d.extract_dates("11月20日", "") == []
    assert d.extract_dates("11月20日", "not-a-date") == []
    assert d.extract_dates("11月20日", "2026-13-45") == []
    assert d.extract_dates(None, "2026-11-01") == []
    assert d.extract_dates(123, "2026-11-01") == []


# ---------- ngày nên lưu ----------

def test_suggest_falls_back_to_posted_date():
    assert d.suggest_date("Dormitory application", "2026-11-15") == {"date": "2026-11-15", "from_title": False}


def test_suggest_single_date_from_title():
    assert d.suggest_date("Deadline: Nov 20", "2026-11-01") == {"date": "2026-11-20", "from_title": True}


def test_suggest_range_picks_start_without_deadline_word_and_end_with_one():
    posted = "2025-12-05"
    assert d.suggest_date("Pruning notice (114/12/09-114/12/11)", posted)["date"] == "2025-12-09"
    assert d.suggest_date("申請(114/12/09-114/12/11)截止", posted)["date"] == "2025-12-11"
    assert d.suggest_date("Apply by deadline 114/12/09-114/12/11", posted)["date"] == "2025-12-11"
    assert d.suggest_date("Applications close 114/12/09-114/12/11", posted)["date"] == "2025-12-11"


def test_deadline_word_does_not_trigger_on_unrelated_words():
    # "due" nằm bên trong chữ khác (residue, overdue) không được coi là từ hạn chót -> lấy ngày đầu
    assert d.suggest_date("Residue testing 114/12/09-114/12/11", "2025-12-05")["date"] == "2025-12-09"
    assert d.suggest_date("Overdue items 114/12/09-114/12/11", "2025-12-05")["date"] == "2025-12-09"
    assert d.suggest_date("Items due 114/12/09-114/12/11", "2025-12-05")["date"] == "2025-12-11"   # "due" đứng riêng: có


def test_a_full_date_is_not_read_again_as_month_day():
    # Ngày đầy đủ đã bị loại (quá cũ) thì phần "12月28日" bên trong không được đọc lại như ngày không có năm
    assert d.extract_dates("2025年12月28日 notice", "2026-12-20") == []
    assert d.extract_dates("115年10月08日 notice", "2027-10-20") == []          # cũng đúng với năm Dân Quốc
    assert d.extract_dates("Nov 20, 2025 notice", "2026-11-20") == []             # và với ngày tiếng Anh có năm


def test_impossible_dates_are_dropped_whatever_the_posted_date():
    assert d.extract_dates("2月30日 活動", "2025-12-30") == []
    assert d.extract_dates("2026-02-30 deadline", "2025-12-30") == []
    assert d.extract_dates("115年02月30日", "2025-12-30") == []
    assert d.extract_dates("Feb 30 deadline", "2025-12-30") == []


def test_long_numbers_are_not_cut_into_dates():
    assert d.extract_dates("Code 2115.03.21", "2026-03-15") == []
    assert d.extract_dates("Ref 91115/03/21", "2026-03-15") == []


def test_suggest_keeps_posted_date_when_nothing_valid():
    assert d.suggest_date("依據2026/01/05公告辦理", "2026-11-18") == {"date": "2026-11-18", "from_title": False}
