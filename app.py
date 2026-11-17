"""Campus & Daily Life Assistant for NTHU students - Flask app.

Chạy:  python app.py   rồi mở http://127.0.0.1:5000

File này chỉ chứa route và phần bảo mật. Logic nằm ở các file khác:
    nthu_api.py       announcements từ NTHU Data API
    calendar_logic.py kiểm tra dữ liệu sự kiện, dựng lưới lịch tháng
    db.py             câu lệnh SQL (users, events)
"""
import hmac
import os
import re
import secrets
import sqlite3
from datetime import date
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db
from calendar_logic import (
    WEEKDAYS,
    build_month,
    mark_saved,
    month_bounds,
    month_label,
    parse_month,
    shift_month,
    validate_event,
)
from nthu_api import (
    category_counts,
    fetch_announcements,
    filter_announcements,
    list_offices,
    paginate,
)

app = Flask(__name__)
# SECRET_KEY dùng để ký cookie session. Khi deploy PHẢI đặt biến môi trường SECRET_KEY.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE"] = os.path.join(app.instance_path, "app.db")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # cookie không gửi kèm request từ trang web khác
app.teardown_appcontext(db.close_db)

LATEST_ON_HOME = 5
UPCOMING_ON_HOME = 5
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ======================= bảo mật: CSRF, người dùng, chuyển hướng =======================

def csrf_token():
    """Token chống CSRF của phiên hiện tại (tạo khi cần, lưu trong session)."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token  # dùng được trong template: {{ csrf_token() }}


def fail(message, status):
    """Trả lỗi: JSON cho /api/..., chữ thường cho trang web."""
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), status
    return message, status


@app.before_request
def load_user_and_check_csrf():
    """Chạy trước MỖI request: nạp người dùng đang đăng nhập và kiểm tra CSRF."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = db.get_user(user_id)

    # Request làm thay đổi dữ liệu phải mang đúng token (form: trường csrf_token;
    # fetch: header X-CSRF-Token). Trang web lạ không biết token nên không giả mạo được.
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        expected = session.get("csrf")
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
            return fail("Invalid or missing CSRF token", 400)


@app.context_processor
def inject_user():
    """Đưa current_user vào mọi template."""
    return {"current_user": g.user}


def login_required(view):
    """Chặn người chưa đăng nhập: trang web -> chuyển tới /login, API -> trả 401."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "login required"}), 401
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Chỉ cho chuyển hướng tới đường dẫn nội bộ của site (chống open redirect)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("home")


# ======================= trang chính =======================

@app.route("/")
def home():
    """Trang chủ: sự kiện sắp tới của bạn (nếu đã đăng nhập) + thông báo mới nhất."""
    items, error = fetch_announcements()
    # Khi API lỗi, items là dữ liệu mẫu -> không hiện trên trang chủ cho khỏi nhầm
    latest = [] if error else items[:LATEST_ON_HOME]

    upcoming = []
    if g.user:
        upcoming = db.upcoming_events(g.user["id"], date.today().isoformat(), UPCOMING_ON_HOME)
    return render_template("home.html", latest=latest, upcoming=upcoming)


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

    # Đánh dấu thông báo nào người dùng đã lưu vào Calendar (mỗi người một kết quả riêng)
    saved = db.saved_keys(g.user["id"]) if g.user else set()
    page_items = mark_saved(page_items, saved)

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
    """Bản JSON của danh sách đã lọc (dữ liệu công khai, không cần đăng nhập).

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


# ======================= tài khoản =======================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Đăng ký: kiểm tra dữ liệu, băm mật khẩu, lưu user, đăng nhập luôn."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        user_id = None
        if not EMAIL_RE.match(email) or len(email) > 254:
            error = "Please enter a valid email address."
        elif not 8 <= len(password) <= 128:
            error = "Password must be 8 to 128 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            try:
                # Chỉ lưu bản BĂM của mật khẩu, không bao giờ lưu mật khẩu gốc
                user_id = db.create_user(email, generate_password_hash(password))
            except sqlite3.IntegrityError:  # cột email là UNIQUE
                error = "That email is already registered."

        if error is None:
            session.clear()                # phiên mới sau khi đăng nhập (chống session fixation)
            session["user_id"] = user_id
            flash("Welcome! Your account is ready.")
            return redirect(url_for("home"))

        flash(error, "error")
        return render_template("signup.html", email=email), 400
    return render_template("signup.html", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Đăng nhập: so mật khẩu với bản băm, lưu user_id vào session."""
    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            # Cùng một thông báo cho "sai email" và "sai mật khẩu" để không lộ email nào đã đăng ký
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email, next_url=next_url), 401
        session.clear()
        session["user_id"] = user["id"]
        return redirect(safe_next(next_url))
    return render_template("login.html", email="", next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    """Đăng xuất (dùng POST để trang lạ không tự đăng xuất bạn được)."""
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


# ======================= Calendar: trang web =======================

@app.route("/calendar")
@login_required
def calendar_page():
    """Lịch tháng của người dùng. ?month=YYYY-MM để chọn tháng."""
    today = date.today()
    year, month = parse_month(request.args.get("month")) or (today.year, today.month)
    start, end = month_bounds(year, month)
    events = db.list_events(g.user["id"], start, end)

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)
    in_this_month = (year, month) == (today.year, today.month)

    return render_template(
        "calendar.html",
        weeks=build_month(year, month, events, today),
        weekdays=WEEKDAYS,
        label=month_label(year, month),
        prev_month=f"{prev_year:04d}-{prev_month:02d}",
        next_month=f"{next_year:04d}-{next_month:02d}",
        default_date=today.isoformat() if in_this_month else start,
        in_this_month=in_this_month,
    )


# ======================= Calendar API (hợp đồng: CALENDAR_API.md) =======================

@app.route("/api/events", methods=["GET", "POST"])
@login_required
def api_events():
    """POST: tạo sự kiện. GET: danh sách sự kiện của bạn (?month=YYYY-MM để lọc tháng)."""
    if request.method == "POST":
        event, error = validate_event(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        return jsonify(db.add_event(g.user["id"], event)), 201

    start = end = None
    month_text = request.args.get("month")
    if month_text:
        parsed = parse_month(month_text)
        if parsed is None:
            return jsonify({"error": "month must be in YYYY-MM format"}), 400
        start, end = month_bounds(*parsed)
    return jsonify(db.list_events(g.user["id"], start, end))


@app.route("/api/events/<int:event_id>", methods=["PUT", "DELETE"])
@login_required
def api_event(event_id):
    """PUT: sửa sự kiện. DELETE: xóa. Sự kiện của người khác -> 404 như thể không tồn tại."""
    if request.method == "DELETE":
        if not db.delete_event(g.user["id"], event_id):
            return jsonify({"error": "event not found"}), 404
        return "", 204

    event, error = validate_event(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    updated = db.update_event(g.user["id"], event_id, event)
    if updated is None:
        return jsonify({"error": "event not found"}), 404
    return jsonify(updated)


if __name__ == "__main__":
    app.run(debug=True)
