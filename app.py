"""Campus & Daily Life Assistant for NTHU students - Flask app.

Chạy:  python app.py   rồi mở http://127.0.0.1:5000
"""
from flask import Flask, jsonify, render_template, request

from nthu_api import (
    category_counts,
    fetch_announcements,
    filter_announcements,
    list_offices,
    paginate,
)

app = Flask(__name__)

LATEST_ON_HOME = 5  # số thông báo mới nhất hiện ở trang chủ


@app.route("/")
def home():
    """Trang chủ: giới thiệu + vài thông báo mới nhất."""
    items, error = fetch_announcements()
    # Khi API lỗi, items là dữ liệu mẫu -> không hiện trên trang chủ cho khỏi nhầm
    latest = [] if error else items[:LATEST_ON_HOME]
    return render_template("home.html", latest=latest)


@app.route("/announcements")
def announcements():
    """Trang Announcements.

    Tham số trên URL: ?office=...&q=...&lang=...&cat=...&page=...
    """
    q = request.args.get("q", "").strip()
    office = request.args.get("office", "").strip()
    lang = request.args.get("lang", "").strip()
    cat = request.args.get("cat", "").strip()
    page = request.args.get("page", 1, type=int)  # không phải số -> dùng 1

    items, error = fetch_announcements()
    filtered = filter_announcements(items, office=office, q=q, lang=lang, category=cat)
    page_items, page, total_pages = paginate(filtered, page)

    return render_template(
        "announcements.html",
        items=page_items,
        count=len(filtered),   # số mục sau khi lọc
        total=len(items),      # tổng số mục
        page=page,
        total_pages=total_pages,
        offices=list_offices(items),
        categories=category_counts(items),
        q=q,
        office=office,
        lang=lang,
        cat=cat,
        error=error,
    )


@app.route("/api/announcements")
def api_announcements():
    """Bản JSON của danh sách đã lọc (để frontend/Calendar dùng sau này).

    Nhận cùng tham số lọc như trang web, thêm ?limit=N (mặc định 50).
    """
    items, _ = fetch_announcements()
    filtered = filter_announcements(
        items,
        office=request.args.get("office", "").strip(),
        q=request.args.get("q", "").strip(),
        lang=request.args.get("lang", "").strip(),
        category=request.args.get("cat", "").strip(),
    )
    limit = request.args.get("limit", 50, type=int)
    return jsonify(filtered[:limit])


if __name__ == "__main__":
    app.run(debug=True)
