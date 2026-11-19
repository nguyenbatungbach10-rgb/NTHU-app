"""Campus & Daily Life Assistant for NTHU students - Flask app.

Chạy:  python app.py   rồi mở http://127.0.0.1:5000

File này chỉ chứa route và phần bảo mật. Logic nằm ở các file khác:
    nthu_api.py       announcements từ NTHU Data API
    calendar_logic.py kiểm tra dữ liệu sự kiện, dựng lưới lịch tháng
    db.py             câu lệnh SQL (users, events)
"""
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta
from functools import lru_cache, wraps
from urllib.parse import quote

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
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import account_logic
from deadline_logic import DEADLINE_WORDS
import db
import home_logic
import i18n
import ics_export
import login_guard
import map_logic
import pwa
import timetable_import
from calendar_logic import (
    MAX_YEAR,
    MIN_YEAR,
    TAIWAN_TZ,
    agenda_summary,
    day_agenda,
    parse_day,
    week_start,
    week_strip,
    WEEKDAYS,
    build_month,
    mark_saved,
    today_tw,
    month_bounds,
    month_label,
    parse_month,
    parse_year,
    shift_month,
    validate_event,
    build_year,
    year_bounds,
)
from gpa_logic import (
    credits_by_year,
    goal_status as gpa_goal_status,
    grades_needed,
    DEFAULT_CREDITS_REQUIRED,
    DEFAULT_TARGET_GPA,
    GRADE_POINTS,
    LETTERS,
    current_semester,
    overview,
    semester_summary,
    validate_course,
    validate_goals,
)
from schedule_logic import (
    PERIODS,
    break_minutes,
    build_timetable,
    class_states,
    classes_on,
    validate_class,
    visible_days,
    weekly_minutes,
)
from study_logic import (
    analytics as study_analytics,
    build_task_tree,
    due_today,
    minutes_by_subject,
    overview as study_overview,
    validate_session,
    validate_subject,
    validate_task,
    week_bounds,
)
from nthu_api import (
    highlight,
    is_stale,
    category_counts,
    GROUP_PREFIX,
    group_offices,
    upcoming_dates,
    fetch_announcements,
    is_sample,
    filter_announcements,
    list_offices,
    paginate,
)

app = Flask(__name__)
# SECRET_KEY dùng để ký cookie session. Khi deploy PHẢI đặt biến môi trường SECRET_KEY.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE"] = os.path.join(app.instance_path, "app.db")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # cookie không gửi kèm request từ trang web khác
# "Remember me": phiên "permanent" sống 30 ngày (Flask gia hạn mỗi lần mở web); không chọn thì hết khi đóng trình duyệt
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=account_logic.REMEMBER_DAYS)

# Trên server thật (PythonAnywhere) đặt biến môi trường PRODUCTION=1 trong file WSGI. Khi đó:
#   - cookie chỉ gửi qua HTTPS (Secure), kẻ nghe lén Wi-Fi không lấy được phiên đăng nhập
#   - đọc IP thật của người dùng từ header X-Forwarded-For do proxy của PythonAnywhere thêm vào
#     (máy mình chạy python app.py thì không có proxy, nên KHÔNG bật để người dùng không giả được IP)
PRODUCTION = os.environ.get("PRODUCTION") == "1"
app.config["SESSION_COOKIE_SECURE"] = PRODUCTION
if PRODUCTION:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.teardown_appcontext(db.close_db)

LATEST_ON_HOME = 5
DEADLINE_DAYS = 60          # trang Announcements > Upcoming deadlines: 60 ngày tới
HOME_EVENT_DAYS = 14        # trang chủ: buổi nói chuyện / hoạt động trong 14 ngày tới
# ?view=... của trang Announcements -> loại ngày cần lấy (xem nthu_api.upcoming_dates)
ANNOUNCEMENT_VIEWS = {"all": None, "deadlines": "deadline", "events": "event"}
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
    """Chạy trước MỖI request: chọn ngôn ngữ/giao diện, nạp người dùng đang đăng nhập và kiểm tra CSRF."""
    g.lang = i18n.detect_lang(request.cookies.get("lang"), request.headers.get("Accept-Language", ""))
    g.theme = i18n.normalize_theme(request.cookies.get("theme"))
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.get_user(user_id)
        # Phiên phải mang đúng "dấu" của mật khẩu hiện tại: đổi mật khẩu hoặc xóa tài khoản
        # thì các phiên cũ (trên máy khác) không còn khớp -> bị đăng xuất
        if user is None or not account_logic.same_tag(session.get("auth"), auth_tag(user)):
            session.clear()
        else:
            g.password_hash = user.pop("password_hash")   # template chỉ thấy id, email, created_at
            g.user = user

    # Request làm thay đổi dữ liệu phải mang đúng token (form: trường csrf_token;
    # fetch: header X-CSRF-Token). Trang web lạ không biết token nên không giả mạo được.
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        expected = session.get("csrf")
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
            return fail("Invalid or missing CSRF token", 400)


def current_notifications():
    """Thông báo cho người đang đăng nhập (tính một lần mỗi request, dùng cho chuông và trang /notifications)."""
    if g.user is None:
        return []
    if "notifications" not in g:
        today = today_tw()
        now = datetime.now(TAIWAN_TZ)
        day_after = (today + timedelta(days=2)).isoformat()
        uid = g.user["id"]
        g.notifications = home_logic.notifications(
            today, now.hour * 60 + now.minute,
            db.list_tasks_due(uid, "0000-01-01", day_after),
            db.list_events(uid, today.isoformat(), day_after),
            classes_on(db.list_classes(uid), today.weekday()))
    return g.notifications


@app.context_processor
def inject_user():
    """Đưa current_user, ngôn ngữ và giao diện vào mọi template."""
    lang = getattr(g, "lang", i18n.DEFAULT_LANG)
    return {"current_user": g.user, "ui_lang": lang, "theme": getattr(g, "theme", i18n.DEFAULT_THEME),
            "js_i18n": i18n.js_strings(lang), "tabs": home_logic.TABS,
            "current_tab": home_logic.current_tab(request.endpoint),
            "notification_count": len(current_notifications()) if g.get("user") else 0}


# ======================= đa ngôn ngữ =======================

def current_lang():
    """Ngôn ngữ của request hiện tại (tiếng Anh nếu chưa chọn được, ví dụ khi lỗi rất sớm)."""
    return getattr(g, "lang", i18n.DEFAULT_LANG)


def _(text, **values):
    """Dịch một câu theo ngôn ngữ hiện tại. Dùng trong template: {{ _('Calendar') }}."""
    return i18n.translate(text, current_lang(), **values)


# Hàm dùng chung trong mọi template (kể cả macro được import, vì đây là "globals")
app.jinja_env.globals.update(
    _=_,
    languages=i18n.LANGUAGES,
    month_label=lambda year, month: i18n.month_label(year, month, current_lang()),
    month_long=lambda month: i18n.month_long(month, current_lang()),
    month_short=lambda month: i18n.month_short(month, current_lang()),
    weekday_long=lambda index: i18n.weekday_long(index, current_lang()),
    weekday_short=lambda: i18n.weekday_short(current_lang()),
    weekday_initials=lambda: i18n.weekday_initials(current_lang()),
    fmt_minutes=lambda minutes: i18n.format_minutes(minutes, current_lang()),
)


@app.after_request
def translate_api_errors(response):
    """Lỗi JSON {"error": "..."} được dịch sang ngôn ngữ người dùng đã chọn (Python dịch, JS chỉ hiện)."""
    if response.status_code >= 400 and response.is_json and current_lang() != i18n.DEFAULT_LANG:
        data = response.get_json(silent=True)
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            data["error"] = i18n.translate_error(data["error"], current_lang())
            response.set_data(json.dumps(data, ensure_ascii=False))
    return response


# ======================= Tốc độ: cho trình duyệt nhớ file tĩnh (CSS, JS, icon) =======================
# Mỗi link tới /static/ được gắn thêm ?v=<thời điểm sửa file>, ví dụ /static/style.css?v=1795026600.
# Vì link đổi mỗi khi file đổi, trình duyệt được phép nhớ file 1 năm mà không hỏi lại server
# (trước đây mỗi trang đều hỏi lại style.css và app.js: thêm một lượt đi về ~230 ms trước khi trang hiện).
STATIC_MAX_AGE = 365 * 24 * 3600


@lru_cache(maxsize=256)
def static_version(filename):
    """Số phiên bản của một file tĩnh = thời điểm sửa file (đổi khi deploy bản mới)."""
    try:
        return str(int(os.path.getmtime(os.path.join(app.static_folder, filename))))
    except OSError:
        return "0"


@app.url_defaults
def add_static_version(endpoint, values):
    """url_for('static', filename=...) tự thêm ?v=... (template không cần sửa)."""
    if endpoint == "static" and "filename" in values and "v" not in values:
        values["v"] = static_version(values["filename"])


def cache_static(response):
    """File tĩnh có ?v=...: cho nhớ 1 năm, "immutable" = không cần hỏi lại kể cả khi bấm tải lại trang."""
    if request.endpoint == "static" and request.args.get("v") and response.status_code in (200, 304):
        response.cache_control.no_cache = None
        response.cache_control.public = True
        response.cache_control.max_age = STATIC_MAX_AGE
        response.cache_control.immutable = True
    return response


# Header bảo mật gắn vào MỌI trang:
#   X-Frame-Options / frame-ancestors: trang lạ không được nhúng web mình vào <iframe> (chống clickjacking:
#       nhúng ẩn rồi lừa người dùng bấm nút "Delete" của mình)
#   X-Content-Type-Options: trình duyệt không được tự đoán loại file (chống chạy file tải lên như script)
#   Referrer-Policy: khi bấm link sang trang khác, chỉ gửi tên miền, không gửi đường dẫn đầy đủ (có thể chứa ?q=...)
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@app.after_request
def add_security_headers(response):
    """Gắn SECURITY_HEADERS; trên server thật (HTTPS) thêm HSTS: trình duyệt nhớ luôn dùng HTTPS 1 năm."""
    cache_static(response)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if PRODUCTION and request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.route("/settings", methods=["POST"])
def settings():
    """Lưu ngôn ngữ và/hoặc giao diện vào cookie (1 năm), rồi quay lại trang cũ. Cần CSRF như mọi POST."""
    response = redirect(safe_next(request.form.get("next", "")))
    one_year = 365 * 24 * 3600
    lang, theme = request.form.get("lang"), request.form.get("theme")
    if lang in i18n.LANGUAGES:
        response.set_cookie("lang", lang, max_age=one_year, samesite="Lax", httponly=True,
                            secure=app.config["SESSION_COOKIE_SECURE"])
    if theme in i18n.THEMES:
        response.set_cookie("theme", theme, max_age=one_year, samesite="Lax", httponly=True,
                            secure=app.config["SESSION_COOKIE_SECURE"])
    return response


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


def auth_tag(user):
    """Dấu của mật khẩu hiện tại của user (xem account_logic.auth_tag)."""
    return account_logic.auth_tag(app.config["SECRET_KEY"], user["password_hash"])


def start_session(user, remember):
    """Đăng nhập: phiên mới (chống session fixation), lưu user_id và dấu mật khẩu."""
    session.clear()
    session["user_id"] = user["id"]
    session["auth"] = auth_tag(user)
    session.permanent = bool(remember)   # True = giữ đăng nhập REMEMBER_DAYS ngày


def notice_is_stale(notice):
    """True nếu đang dùng bản lưu đã cũ quá nthu_api.STALE_HOURS giờ (lúc đó mới hiện cảnh báo vàng)."""
    if not notice or notice.get("kind") != "snapshot":
        return False
    return is_stale(notice.get("saved_at"), datetime.now(TAIWAN_TZ).replace(tzinfo=None))


def safe_next(target):
    """Chỉ cho chuyển hướng tới đường dẫn nội bộ của site (chống open redirect)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("home")


# ======================= trang chính =======================

def today_route(classes):
    """Các môn hôm nay kèm tòa nhà, đường đi tới môn kế tiếp (leg) và trạng thái so với bây giờ (state)."""
    route = map_logic.day_route(map_logic.class_stops(classes, campus_places()[0]), break_minutes)
    now = datetime.now(TAIWAN_TZ)
    for stop, state in zip(route, class_states(classes, now.hour * 60 + now.minute)):
        stop.update(state)
    return route


@app.route("/")
def home():
    """Trang chủ: sự kiện sắp tới của bạn (nếu đã đăng nhập) + thông báo mới nhất."""
    items, notice = fetch_announcements()
    # Dữ liệu mẫu thì không hiện trên trang chủ cho khỏi nhầm; bản lưu là thông báo thật nên vẫn hiện
    latest = [] if is_sample(notice) else items[:LATEST_ON_HOME]
    # Trang chủ hiện các SỰ KIỆN sắp diễn ra (buổi nói chuyện, hội thảo, hoạt động), không hiện hạn chót;
    # hạn chót xem ở trang Announcements > Deadlines
    soon = [] if is_sample(notice) else upcoming_dates(items, today_tw(), HOME_EVENT_DAYS, "event")[:LATEST_ON_HOME]

    upcoming, today_classes, due = [], [], []
    today = today_tw()
    if g.user:
        upcoming = db.upcoming_events(g.user["id"], today.isoformat(), UPCOMING_ON_HOME)
        today_classes = today_route(classes_on(db.list_classes(g.user["id"]), today.weekday()))
        tomorrow = (today + timedelta(days=1)).isoformat()
        due = due_today(db.list_tasks_due(g.user["id"], "0000-01-01", tomorrow), today.isoformat())
    steps = None
    if g.user:
        hidden = request.cookies.get("onboarding") == "hidden"   # người dùng đã bấm "Hide"
        steps = home_logic.onboarding(db.user_counts(g.user["id"]), hidden)
        targets = {"schedule": url_for("schedule_page"), "gpa": url_for("gpa_page"),
                   "deadlines": url_for("announcements", view="deadlines"), "study": url_for("study_page")}
        for step in steps["steps"]:
            step["url"] = targets[step["target"]]
    return render_template("home.html", latest=latest, upcoming=upcoming, notice=notice, soon=soon, onboarding=steps,
                           stale=notice_is_stale(notice),
                           today=today, today_classes=today_classes, due_tasks=due)


@app.route("/announcements")
def announcements():
    """Trang Announcements.

    Tham số trên URL: ?office=...&q=...&lang=...&cat=...&page=...
    """
    q = request.args.get("q", "").strip()
    office = request.args.get("office", "").strip()
    lang = request.args.get("lang", "").strip()
    cat = request.args.get("cat", "").strip()
    view = request.args.get("view")
    view = view if view in ANNOUNCEMENT_VIEWS else "all"   # giá trị lạ -> xem tất cả
    page = request.args.get("page", 1, type=int)  # không phải số -> dùng 1

    items, notice = fetch_announcements()
    # "Deadlines" / "Events": chỉ các thông báo có ngày trong tiêu đề, 60 ngày tới, gần nhất trước
    source = items if view == "all" else upcoming_dates(items, today_tw(), DEADLINE_DAYS, ANNOUNCEMENT_VIEWS[view])
    filtered = filter_announcements(source, office=office, q=q, lang=lang, category=cat)
    page_items, page, total_pages = paginate(filtered, page)

    # Đánh dấu thông báo nào người dùng đã lưu vào Calendar (mỗi người một kết quả riêng)
    saved = db.saved_keys(g.user["id"]) if g.user else set()
    page_items = mark_saved(page_items, saved, today_tw())
    # Tô vàng từ khóa trong tiêu đề (mark_saved đã trả về bản sao nên sửa được)
    for item in page_items:
        item["title_parts"] = highlight(item["title"], q)
        item.setdefault("is_deadline", bool(DEADLINE_WORDS.search(item["title"])))   # cho chữ của toast "Deadline added"

    return render_template(
        "announcements.html",
        items=page_items,
        count=len(filtered),   # số mục sau khi lọc
        total=len(items),      # tổng số mục
        page=page,
        total_pages=total_pages,
        office_groups=group_offices(list_offices(items)),
        group_prefix=GROUP_PREFIX,
        categories=category_counts(items),
        q=q,
        office=office,
        lang=lang,
        cat=cat,
        view=view,
        deadline_days=DEADLINE_DAYS,
        notice=notice,
        stale=notice_is_stale(notice),
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
        elif account_logic.password_error(password, confirm):
            error = account_logic.password_error(password, confirm)
        else:
            try:
                # Chỉ lưu bản BĂM của mật khẩu, không bao giờ lưu mật khẩu gốc
                user_id = db.create_user(email, generate_password_hash(password))
            except sqlite3.IntegrityError:  # cột email là UNIQUE
                error = "That email is already registered."

        if error is None:
            start_session(db.get_user(user_id), request.form.get("remember") == "1")
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
        ip = request.remote_addr or ""
        now = time.time()
        # Sai quá nhiều lần gần đây -> không kiểm tra mật khẩu nữa, bảo chờ (login_guard.py quyết định)
        account_times, ip_times = db.login_failure_times(email, ip, now - login_guard.WINDOW_SECONDS)
        wait = login_guard.lockout_minutes(account_times, ip_times, now)
        if wait:
            return render_template("login.html", email=email, next_url=next_url, locked_minutes=wait), 429
        user = db.get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            db.add_login_failure(email, ip, now, login_guard.WINDOW_SECONDS)
            # Cùng một thông báo cho "sai email" và "sai mật khẩu" để không lộ email nào đã đăng ký
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email, next_url=next_url), 401
        db.clear_login_failures(email, ip)
        start_session(user, request.form.get("remember") == "1")
        return redirect(safe_next(next_url))
    return render_template("login.html", email="", next_url=next_url)


@app.route("/onboarding/hide", methods=["POST"])
@login_required
def hide_onboarding():
    """Ẩn khung "Get started" trên trang chủ (lưu trong cookie 1 năm, cho trình duyệt này)."""
    response = redirect(url_for("home"))
    response.set_cookie("onboarding", "hidden", max_age=365 * 24 * 3600, samesite="Lax", httponly=True,
                        secure=app.config["SESSION_COOKIE_SECURE"])
    return response


# ======================= Tài khoản: đổi mật khẩu, xóa tài khoản =======================

@app.route("/account")
@login_required
def account_page():
    """Trang Account: thông tin, đồng bộ lịch, đổi mật khẩu, xóa tài khoản."""
    feed = db.get_feed(g.user["id"])
    return render_template("account.html", feed=feed, links=feed_links(feed["token"]) if feed else None)


def current_password_ok():
    """Mật khẩu hiện tại gửi trong form có đúng không (bắt buộc trước khi đổi mật khẩu / xóa tài khoản)."""
    return check_password_hash(g.password_hash, request.form.get("current_password", ""))


@app.route("/account/password", methods=["POST"])
@login_required
def change_password():
    """Đổi mật khẩu. Máy này vẫn đăng nhập; các máy khác bị đăng xuất (dấu mật khẩu đổi)."""
    new, confirm = request.form.get("new_password", ""), request.form.get("confirm", "")
    error = None if current_password_ok() else "Your current password is wrong."
    error = error or account_logic.password_error(new, confirm)
    if error:
        flash(error, "error")
        return render_template("account.html"), 400
    new_hash = generate_password_hash(new)
    db.update_password(g.user["id"], new_hash)
    remember = session.permanent
    start_session({"id": g.user["id"], "password_hash": new_hash}, remember)
    flash("Your password has been changed. Other devices have been logged out.")
    return redirect(url_for("account_page"))


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    """Xóa tài khoản và TOÀN BỘ dữ liệu (ON DELETE CASCADE). Cần mật khẩu và ô xác nhận."""
    if not current_password_ok():
        flash("Your current password is wrong.", "error")
        return render_template("account.html"), 400
    if request.form.get("confirm_delete") != "1":
        flash("Tick the box to confirm that you want to delete your account.", "error")
        return render_template("account.html"), 400
    db.delete_user(g.user["id"])
    session.clear()
    flash("Your account and all your data have been deleted.")
    return redirect(url_for("home"))


# ======================= Đồng bộ lịch (.ics) sang Google / Apple Calendar =======================

def feed_links(token):
    """Các link của file lịch: https (dán vào Google), webcal (bấm trên iPhone/Mac), link mở Google Calendar."""
    url = url_for("calendar_feed", token=token, _external=True)
    webcal = "webcal://" + url.split("://", 1)[1]
    return {"url": url, "webcal": webcal,
            "google": "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe="")}


@app.route("/account/calendar-sync", methods=["POST"])
@login_required
def calendar_sync():
    """Bật / lưu lựa chọn (action=save), đổi link mới (action=reset) hoặc tắt (action=off)."""
    action = request.form.get("action")
    current = db.get_feed(g.user["id"])
    if action == "off":
        db.delete_feed(g.user["id"])
        flash("Calendar sync is off. The old link no longer works.")
    else:
        token = secrets.token_urlsafe(24) if action == "reset" or not current else current["token"]
        db.save_feed(g.user["id"], token, request.form.get("classes") == "1",
                     request.form.get("events") == "1", request.form.get("tasks") == "1")
        flash("You have a new calendar link. Add it again in your calendar app." if action == "reset" and current
              else "Calendar sync settings saved.")
    return redirect(url_for("account_page") + "#calendar-sync")


@app.route("/calendar/feed/<token>.ics")
def calendar_feed(token):
    """File lịch cho Google / Apple Calendar. Không cần đăng nhập: link bí mật chính là chìa khóa."""
    feed = db.get_feed_by_token(token)
    if feed is None:
        return error_page(404)
    uid = feed["user_id"]
    body = ics_export.build_calendar(
        _("NTHU Campus Assistant"), today_tw(), datetime.now(TAIWAN_TZ) - timedelta(hours=8),
        classes=db.list_classes(uid) if feed["classes"] else (),
        events=db.list_events(uid) if feed["events"] else (),
        tasks=db.list_open_tasks_with_due(uid) if feed["tasks"] else (),
        task_label=_("Due: {title}", title="{title}"),
    )
    response = app.response_class(body, mimetype="text/calendar")
    response.headers["Content-Disposition"] = 'inline; filename="nthu-calendar.ics"'
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


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
    """Lịch tháng của người dùng. ?month=YYYY-MM để chọn tháng, ?day=YYYY-MM-DD để chọn ngày.

    Máy tính: lưới tháng. Điện thoại: dải 7 ngày + mọi thứ của ngày đã chọn (lớp, sự kiện, hạn chót).
    """
    today = today_tw()
    day = parse_day(request.args.get("day"))
    if day:
        year, month = day.year, day.month
    else:
        year, month = parse_month(request.args.get("month")) or (today.year, today.month)
        day = today if (year, month) == (today.year, today.month) else date(year, month, 1)
    start, end = month_bounds(year, month)
    events = db.list_events(g.user["id"], start, end)
    tasks = db.list_tasks_due(g.user["id"], start, end)

    # Tuần chứa ngày đã chọn (có thể tràn sang tháng trước/sau nên lấy riêng)
    first = week_start(day)
    week_from, week_to = first.isoformat(), (first + timedelta(days=7)).isoformat()
    week_events = db.list_events(g.user["id"], week_from, week_to)
    week_tasks = db.list_tasks_due(g.user["id"], week_from, week_to)
    classes = db.list_classes(g.user["id"])
    agenda = day_agenda(day, classes, week_events, week_tasks)

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)
    in_this_month = (year, month) == (today.year, today.month)

    return render_template(
        "calendar.html",
        weeks=build_month(year, month, events, today, tasks),
        weekdays=WEEKDAYS,
        label=month_label(year, month),
        prev_month=f"{prev_year:04d}-{prev_month:02d}",
        next_month=f"{next_year:04d}-{next_month:02d}",
        default_date=today.isoformat() if in_this_month else start,
        in_this_month=in_this_month,
        year=year,
        month=month,
        prev_year_month=f"{year - 1:04d}-{month:02d}",
        next_year_month=f"{year + 1:04d}-{month:02d}",
        month_names=[date(year, m, 1).strftime("%b") for m in range(1, 13)],
        today_month=f"{today.year:04d}-{today.month:02d}",
        day=day,
        is_today=day == today,
        week=week_strip(day, today, classes, week_events, week_tasks),
        agenda=agenda,
        summary=agenda_summary(agenda),
        prev_week=(day - timedelta(days=7)).isoformat(),
        next_week=(day + timedelta(days=7)).isoformat(),
    )


@app.route("/calendar/year")
@login_required
def calendar_year_page():
    """Lịch cả năm: 12 tháng thu nhỏ, bấm vào một tháng để mở lịch tháng. ?year=YYYY để chọn năm."""
    today = today_tw()
    year = parse_year(request.args.get("year", "")) or today.year
    start, end = year_bounds(year)
    events = db.list_events(g.user["id"], start, end)
    tasks = db.list_tasks_due(g.user["id"], start, end)
    months = build_year(year, events, today, tasks)
    return render_template(
        "calendar_year.html",
        year=year,
        months=months,
        weekdays=WEEKDAYS,
        prev_year=year - 1 if year > MIN_YEAR else None,
        next_year=year + 1 if year < MAX_YEAR else None,
        is_this_year=year == today.year,
        total=sum(m["count"] for m in months),
        min_year=MIN_YEAR,
        max_year=MAX_YEAR,
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


# ======================= Credit & GPA: trang web =======================

def load_goals(user_id):
    """Mục tiêu đã lưu của người dùng, hoặc giá trị mặc định nếu chưa đặt."""
    goals = db.get_goals(user_id)
    if goals is None:
        return {"target_gpa": DEFAULT_TARGET_GPA,
                "credits_required": DEFAULT_CREDITS_REQUIRED, "is_default": True}
    return dict(goals, is_default=False)


@app.route("/gpa")
@login_required
def gpa_page():
    """Trang Credit & GPA: GPA tích lũy, tiến độ tín chỉ, cần điểm bao nhiêu, từng học kỳ."""
    courses = db.list_courses(g.user["id"])
    goals = load_goals(g.user["id"])
    # Gợi ý tên môn khi gõ: môn trong thời khóa biểu, môn học, môn đã nhập GPA
    suggestions = home_logic.name_suggestions([c["name"] for c in db.list_classes(g.user["id"])],
                                              [s["name"] for s in db.list_subjects(g.user["id"])],
                                              [c["name"] for c in courses])
    return render_template(
        "gpa.html",
        overview=overview(courses, goals["target_gpa"], goals["credits_required"]),
        goal=gpa_goal_status(courses, goals["target_gpa"]),
        needed=grades_needed(courses, goals["target_gpa"]),
        by_year=credits_by_year(courses, goals["credits_required"], current_semester(today_tw())),
        semesters=list(reversed(semester_summary(courses))),  # học kỳ mới nhất trước
        goals=goals,
        letters=LETTERS,
        grade_points=GRADE_POINTS,
        default_semester=current_semester(today_tw()),
        has_courses=bool(courses),
        name_suggestions=suggestions,
    )


# ======================= Credit & GPA: API =======================

@app.route("/api/courses", methods=["GET", "POST"])
@login_required
def api_courses():
    """POST: thêm môn học. GET: danh sách môn học của bạn."""
    if request.method == "POST":
        course, error = validate_course(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        return jsonify(db.add_course(g.user["id"], course)), 201
    return jsonify(db.list_courses(g.user["id"]))


@app.route("/api/courses/<int:course_id>", methods=["PUT", "DELETE"])
@login_required
def api_course(course_id):
    """PUT: sửa môn học. DELETE: xóa. Môn của người khác -> 404."""
    if request.method == "DELETE":
        if not db.delete_course(g.user["id"], course_id):
            return jsonify({"error": "course not found"}), 404
        return "", 204

    course, error = validate_course(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    updated = db.update_course(g.user["id"], course_id, course)
    if updated is None:
        return jsonify({"error": "course not found"}), 404
    return jsonify(updated)


@app.route("/api/goals", methods=["GET", "PUT"])
@login_required
def api_goals():
    """GET: mục tiêu hiện tại. PUT: đặt mục tiêu GPA và số tín chỉ tốt nghiệp."""
    if request.method == "PUT":
        goals, error = validate_goals(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        return jsonify(db.set_goals(g.user["id"], goals))
    goals = load_goals(g.user["id"])
    return jsonify({"target_gpa": goals["target_gpa"], "credits_required": goals["credits_required"]})


# ======================= Thời khóa biểu tuần: trang web =======================

@app.route("/schedule")
@login_required
def schedule_page():
    """Thời khóa biểu tuần: mỗi thứ một cột, các môn xếp theo giờ, môn trùng giờ được tô cảnh báo."""
    classes = db.list_classes(g.user["id"])
    days = build_timetable(classes)
    today = today_tw()
    return render_template(
        "schedule.html",
        days=visible_days(days),
        today_weekday=today.weekday(),
        today_classes=[c for c in days[today.weekday()]["classes"]],
        has_classes=bool(classes),
        conflict_count=len({c["id"] for d in days for c in d["classes"] if c["conflict"]}),
        total_minutes=weekly_minutes(classes),
        class_count=len(classes),
        weekday_names=[d["name"] for d in days],
        periods=PERIODS,
    )


# ======================= Nhập thời khóa biểu từ 校務資訊系統 =======================

def import_plan(text, names, existing):
    """Đọc chữ đã dán -> (classes mới hợp lệ, số môn trùng, các môn bỏ qua). Python quyết định hết."""
    found, skipped = timetable_import.parse_timetable(text, names)
    fresh, duplicates = [], 0
    for item in found:
        clean, error = validate_class(item)
        if error:
            skipped.append(dict(item, status=error))
        elif timetable_import.is_duplicate(clean, existing + fresh):
            duplicates += 1
        else:
            fresh.append(dict(clean, code=item["code"], status=item["status"]))
    return fresh, duplicates, skipped


@app.route("/schedule/import", methods=["GET", "POST"])
@login_required
def schedule_import():
    """Bước 1: dán chữ -> xem trước (action=preview). Bước 2: bấm Import (action=import) -> lưu."""
    if request.method == "GET":
        return render_template("schedule_import.html", text="", names="zh", replace=False, preview=None)
    text = request.form.get("text", "")[:timetable_import.MAX_TEXT]
    names = "en" if request.form.get("names") == "en" else "zh"
    replace = request.form.get("replace") == "1"
    existing = [] if replace else db.list_classes(g.user["id"])
    fresh, duplicates, skipped = import_plan(text, names, existing)

    if request.form.get("action") == "import" and fresh:
        if replace:
            db.delete_all_classes(g.user["id"])
        db.add_classes(g.user["id"], fresh)
        flash(_("Imported {n} classes.", n=len(fresh)))
        return redirect(url_for("schedule_page"))

    preview = {"classes": fresh, "duplicates": duplicates, "skipped": skipped,
               "weekday_names": [i18n.weekday_long(d, current_lang()) for d in range(7)]}
    status = 200 if fresh or duplicates else 400
    return render_template("schedule_import.html", text=text, names=names, replace=replace,
                           preview=preview), status


# ======================= Thời khóa biểu tuần: API =======================

@app.route("/api/classes", methods=["GET", "POST"])
@login_required
def api_classes():
    """POST: thêm môn vào thời khóa biểu. GET: danh sách môn của bạn."""
    if request.method == "POST":
        item, error = validate_class(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        return jsonify(db.add_class(g.user["id"], item)), 201
    return jsonify(db.list_classes(g.user["id"]))


@app.route("/api/classes/<int:class_id>", methods=["PUT", "DELETE"])
@login_required
def api_class(class_id):
    """PUT: sửa môn. DELETE: xóa. Môn của người khác -> 404."""
    if request.method == "DELETE":
        if not db.delete_class(g.user["id"], class_id):
            return jsonify({"error": "class not found"}), 404
        return "", 204
    item, error = validate_class(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    updated = db.update_class(g.user["id"], class_id, item)
    if updated is None:
        return jsonify({"error": "class not found"}), 404
    return jsonify(updated)


# ======================= Study planning: trang web =======================

@app.route("/study")
@login_required
def study_page():
    """Trang Study: việc cần làm (có việc con), môn học + tài liệu, thời gian học."""
    uid = g.user["id"]
    today = today_tw()
    subjects = db.list_subjects(uid)
    names = {subject["id"]: subject["name"] for subject in subjects}
    tasks = db.list_tasks(uid)
    sessions = db.list_sessions(uid)
    week_start, week_end = week_bounds(today)

    week_by_subject = {row["subject_id"]: row["minutes"]
                       for row in minutes_by_subject(sessions, names, week_start, week_end)}
    recent = [dict(s, subject_name=names.get(s["subject_id"], "")) for s in sessions[:15]]
    period = request.args.get("period", "week")
    return render_template(
        "study.html",
        stats_chart=study_analytics(sessions, names, today, period),
        stats=study_overview(tasks, sessions, today),
        task_tree=build_task_tree(tasks, today.isoformat(), names),
        subjects=[dict(s, week_minutes=week_by_subject.get(s["id"], 0)) for s in subjects],
        week_rows=minutes_by_subject(sessions, names, week_start, week_end),
        sessions=recent,
        today=today.isoformat(),
        name_suggestions=home_logic.name_suggestions([c["name"] for c in db.list_classes(uid)],
                                                     [c["name"] for c in db.list_courses(uid)]),
    )


# ======================= Study planning: API =======================

def subject_exists(subject_id):
    """True nếu subject_id trống, hoặc là môn của người dùng hiện tại.

    Quan trọng: không có bước này, người dùng A có thể gắn việc của mình vào môn của B.
    """
    return subject_id is None or db.get_subject(g.user["id"], subject_id) is not None


@app.route("/api/subjects", methods=["GET", "POST"])
@login_required
def api_subjects():
    """POST: thêm môn học. GET: danh sách môn học của bạn."""
    if request.method == "POST":
        subject, error = validate_subject(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        return jsonify(db.add_subject(g.user["id"], subject)), 201
    return jsonify(db.list_subjects(g.user["id"]))


@app.route("/api/subjects/<int:subject_id>", methods=["PUT", "DELETE"])
@login_required
def api_subject(subject_id):
    """PUT: sửa môn. DELETE: xóa môn (việc và buổi học của môn đó được giữ lại)."""
    if request.method == "DELETE":
        if not db.delete_subject(g.user["id"], subject_id):
            return jsonify({"error": "subject not found"}), 404
        return "", 204
    subject, error = validate_subject(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    updated = db.update_subject(g.user["id"], subject_id, subject)
    if updated is None:
        return jsonify({"error": "subject not found"}), 404
    return jsonify(updated)


@app.route("/api/tasks", methods=["GET", "POST"])
@login_required
def api_tasks():
    """POST: thêm việc (có parent_id = thêm việc con). GET: danh sách việc của bạn."""
    if request.method == "GET":
        return jsonify(db.list_tasks(g.user["id"]))

    task, error = validate_task(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if task["parent_id"] is not None:
        parent = db.get_task(g.user["id"], task["parent_id"])
        if parent is None:
            return jsonify({"error": "parent task not found"}), 400
        if parent["parent_id"] is not None:
            return jsonify({"error": "a subtask cannot have its own subtasks"}), 400
        task["subject_id"] = None            # việc con dùng môn của việc cha
    elif not subject_exists(task["subject_id"]):
        return jsonify({"error": "subject not found"}), 400
    return jsonify(db.add_task(g.user["id"], task)), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT", "DELETE"])
@login_required
def api_task(task_id):
    """PUT: sửa việc / tick xong. DELETE: xóa (việc con bị xóa theo)."""
    if request.method == "DELETE":
        if not db.delete_task(g.user["id"], task_id):
            return jsonify({"error": "task not found"}), 404
        return "", 204

    existing = db.get_task(g.user["id"], task_id)
    if existing is None:
        return jsonify({"error": "task not found"}), 404
    task, error = validate_task(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if existing["parent_id"] is not None:
        task["subject_id"] = None            # việc con không có môn riêng
    elif not subject_exists(task["subject_id"]):
        return jsonify({"error": "subject not found"}), 400
    return jsonify(db.update_task(g.user["id"], task_id, task))


@app.route("/api/sessions", methods=["GET", "POST"])
@login_required
def api_sessions():
    """POST: ghi một buổi học. GET: các buổi học của bạn (mới nhất trước)."""
    if request.method == "GET":
        return jsonify(db.list_sessions(g.user["id"]))
    session_data, error = validate_session(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if not subject_exists(session_data["subject_id"]):
        return jsonify({"error": "subject not found"}), 400
    return jsonify(db.add_session(g.user["id"], session_data)), 201


@app.route("/api/sessions/<int:session_id>", methods=["PUT", "DELETE"])
@login_required
def api_session(session_id):
    """PUT: sửa buổi học. DELETE: xóa."""
    if request.method == "DELETE":
        if not db.delete_session(g.user["id"], session_id):
            return jsonify({"error": "session not found"}), 404
        return "", 204
    if db.get_session(g.user["id"], session_id) is None:
        return jsonify({"error": "session not found"}), 404
    session_data, error = validate_session(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    if not subject_exists(session_data["subject_id"]):
        return jsonify({"error": "subject not found"}), 400
    return jsonify(db.update_session(g.user["id"], session_id, session_data))


# ======================= Bản đồ NTHU =======================

@lru_cache(maxsize=1)
def campus_places():
    """Đọc dữ liệu bản đồ một lần rồi giữ trong bộ nhớ (file không đổi khi web đang chạy)."""
    return map_logic.load_places()


def find_place(place_id):
    """Địa điểm theo id (ví dụ "r3815072"), hoặc None."""
    return next((p for p in campus_places()[0] if p["id"] == place_id), None)


@app.route("/map")
def map_page():
    """Bản đồ 2D/3D. ?place=<id> để mở sẵn một địa điểm, ?q=Delta 205 để tìm theo tên hoặc phòng học."""
    places, campuses = campus_places()
    q = request.args.get("q", "").strip()[:100]
    focus = find_place(request.args.get("place", ""))
    if focus is None and q:
        found = map_logic.search(q, places, limit=1)
        focus = found[0] if found else None
    stops = []
    if g.user:
        classes = classes_on(db.list_classes(g.user["id"]), today_tw().weekday())
        stops = map_logic.class_stops(classes, places)
    return render_template(
        "map.html",
        categories=map_logic.category_summary(places),
        campuses=campuses,
        focus=focus,
        q=q,
        results=map_logic.search(q, places) if q else [],
        stops=stops,
        place_count=len(places),
    )


@app.route("/api/places")
def api_places():
    """Mọi địa điểm dạng GeoJSON để vẽ lên bản đồ (dữ liệu công khai, không cần đăng nhập)."""
    return jsonify(map_logic.to_geojson(campus_places()[0]))


@app.route("/api/places/search")
def api_places_search():
    """Tìm địa điểm: ?q=delta, ?q=台達, ?q=綜三 B101."""
    q = request.args.get("q", "")[:100]
    return jsonify(map_logic.search(q, campus_places()[0]))


@app.route("/api/places/<place_id>")
def api_place(place_id):
    """Chi tiết một địa điểm, kèm chỗ ăn / trạm xe / cửa hàng gần nhất."""
    place = find_place(place_id)
    if place is None:
        return jsonify({"error": "place not found"}), 404
    d = map_logic.details(place, campus_places()[0])
    d["category_label"] = _(d["category_label"])
    for near in d["nearby"].values():
        near["label"] = _(near["label"])
        near["text"] = _("{label}: {name}, {meters} m (about {minutes} min walk)", label=near["label"],
                         name=near["name"], meters=near["meters"], minutes=near["minutes"])
    d["floors_text"] = _("{n} floors", n=d["levels"]) if d["levels"] else ""
    d["directions_label"] = _("Walking directions in Google Maps")
    return jsonify(d)


# ======================= trang lỗi và favicon =======================

ERROR_TEXT = {
    404: ("Page not found", "This page does not exist or has moved. Check the address or start from the home page."),
    500: ("Something went wrong", "The server hit an error. Please try again in a moment."),
}


def error_page(code):
    """Trang lỗi theo giao diện của web; đường dẫn /api/ thì trả JSON {"error": ...} như các API khác."""
    heading, message = ERROR_TEXT[code]
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found" if code == 404 else "server error"}), code
    return render_template("error.html", code=code, heading=heading, message=message), code


@app.errorhandler(404)
def not_found(error):
    """Trang 404."""
    return error_page(404)


@app.errorhandler(500)
def server_error(error):
    """Trang 500 (chi tiết lỗi vẫn ghi trong error log của server)."""
    return error_page(500)


@app.route("/favicon.ico")
def favicon():
    """Trình duyệt luôn hỏi /favicon.ico: chuyển sang biểu tượng SVG để không còn lỗi 404 trong console."""
    return redirect(url_for("static", filename="favicon.svg"), code=301)


# ======================= Cài như app (PWA) =======================

@app.route("/manifest.webmanifest")
def web_manifest():
    """Thông tin app cho trình duyệt (tên, icon, màu...), dịch theo ngôn ngữ đang chọn."""
    response = jsonify(pwa.manifest(_, current_lang()))
    response.mimetype = "application/manifest+json"
    return response


@app.route("/sw.js")
def service_worker():
    """Service worker phải nằm ở gốc trang (/sw.js) thì mới lo được mọi trang của web.
    Python ghi phiên bản và danh sách file cần lưu (pwa.py) vào đầu file static/sw.js."""
    script = os.path.join(app.static_folder, "sw.js")
    with open(script, encoding="utf-8") as file:
        body = file.read()
    header = (f"const CACHE_VERSION = {json.dumps(pwa.CACHE_VERSION)};\n"
              f"const OFFLINE_FILES = {json.dumps(pwa.OFFLINE_FILES)};\n")
    response = app.response_class(header + body, mimetype="text/javascript")
    response.headers["Cache-Control"] = "no-cache"   # trình duyệt luôn kiểm tra bản mới
    return response


@app.route("/notifications")
@login_required
def notifications_page():
    """Danh sách việc cần chú ý: trễ hạn, sắp tới hạn, lớp sắp bắt đầu, sự kiện hôm nay / ngày mai."""
    return render_template("notifications.html", items=current_notifications())


@app.route("/offline")
def offline_page():
    """Trang hiện khi mất mạng (service worker lưu sẵn trang này)."""
    return render_template("offline.html")


# ======================= Làm nóng khi khởi động =======================

def warm_caches():
    """Chuẩn bị sẵn những thứ tốn thời gian để NGƯỜI ĐẦU TIÊN vào web không phải chờ:
    đọc bản lưu thông báo, tính ngày trong tiêu đề, đọc dữ liệu bản đồ, dịch sẵn các template Jinja.
    Lỗi ở đây chỉ in ra log, không bao giờ làm web không chạy được."""
    try:
        items, _notice = fetch_announcements()
        upcoming_dates(items, today_tw(), DEADLINE_DAYS)
        campus_places()
        for name in app.jinja_env.list_templates(extensions=["html"]):
            app.jinja_env.get_template(name)
    except Exception as error:                          # noqa: BLE001 - làm nóng không được thì thôi
        print("[warm_caches]", error)


if PRODUCTION:          # chỉ trên server thật; khi chạy test hay chạy thử trên máy thì không cần
    warm_caches()


if __name__ == "__main__":
    app.run(debug=True)
