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
from datetime import date, timedelta
from functools import lru_cache, wraps

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
import map_logic
from calendar_logic import (
    MAX_YEAR,
    MIN_YEAR,
    WEEKDAYS,
    build_month,
    mark_saved,
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
    build_timetable,
    classes_on,
    validate_class,
    visible_days,
    weekly_minutes,
)
from study_logic import (
    build_task_tree,
    due_today,
    format_minutes,
    minutes_by_subject,
    overview as study_overview,
    validate_session,
    validate_subject,
    validate_task,
    week_bounds,
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

    upcoming, today_classes, due = [], [], []
    today = date.today()
    if g.user:
        upcoming = db.upcoming_events(g.user["id"], today.isoformat(), UPCOMING_ON_HOME)
        today_classes = map_logic.class_stops(classes_on(db.list_classes(g.user["id"]), today.weekday()),
                                              campus_places()[0])
        tomorrow = (today + timedelta(days=1)).isoformat()
        due = due_today(db.list_tasks_due(g.user["id"], "0000-01-01", tomorrow), today.isoformat())
    return render_template("home.html", latest=latest, upcoming=upcoming,
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
    tasks = db.list_tasks_due(g.user["id"], start, end)

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
    )


@app.route("/calendar/year")
@login_required
def calendar_year_page():
    """Lịch cả năm: 12 tháng thu nhỏ, bấm vào một tháng để mở lịch tháng. ?year=YYYY để chọn năm."""
    today = date.today()
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
    return render_template(
        "gpa.html",
        overview=overview(courses, goals["target_gpa"], goals["credits_required"]),
        semesters=list(reversed(semester_summary(courses))),  # học kỳ mới nhất trước
        goals=goals,
        letters=LETTERS,
        grade_points=GRADE_POINTS,
        default_semester=current_semester(date.today()),
        has_courses=bool(courses),
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
    today = date.today()
    return render_template(
        "schedule.html",
        days=visible_days(days),
        today_weekday=today.weekday(),
        today_classes=[c for c in days[today.weekday()]["classes"]],
        has_classes=bool(classes),
        conflict_count=len({c["id"] for d in days for c in d["classes"] if c["conflict"]}),
        total_hours=format_minutes(weekly_minutes(classes)),
        class_count=len(classes),
        weekday_names=[d["name"] for d in days],
        periods=PERIODS,
    )


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
    today = date.today()
    subjects = db.list_subjects(uid)
    names = {subject["id"]: subject["name"] for subject in subjects}
    tasks = db.list_tasks(uid)
    sessions = db.list_sessions(uid)
    week_start, week_end = week_bounds(today)

    week_by_subject = {row["subject_id"]: row["minutes"]
                       for row in minutes_by_subject(sessions, names, week_start, week_end)}
    recent = [dict(s, subject_name=names.get(s["subject_id"], "")) for s in sessions[:15]]
    return render_template(
        "study.html",
        stats=study_overview(tasks, sessions, today),
        task_tree=build_task_tree(tasks, today.isoformat(), names),
        subjects=[dict(s, week_minutes=week_by_subject.get(s["id"], 0)) for s in subjects],
        week_rows=minutes_by_subject(sessions, names, week_start, week_end),
        sessions=recent,
        today=today.isoformat(),
        fmt_minutes=format_minutes,
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
        classes = classes_on(db.list_classes(g.user["id"]), date.today().weekday())
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
    return jsonify(map_logic.details(place, campus_places()[0]))


if __name__ == "__main__":
    app.run(debug=True)
