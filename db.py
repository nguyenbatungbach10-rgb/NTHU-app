"""Lớp truy cập database SQLite (dùng module sqlite3 có sẵn của Python).

Quy tắc quan trọng:
  1. Luôn dùng dấu ? và truyền giá trị riêng (câu SQL "tham số hóa"),
     KHÔNG ghép chuỗi vào câu SQL -> chống SQL injection.
  2. Mọi hàm đụng tới sự kiện đều có `user_id` trong điều kiện WHERE,
     nên người dùng này không bao giờ đọc/sửa/xóa được sự kiện của người khác.
"""
import os
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    date        TEXT NOT NULL,              -- YYYY-MM-DD
    time        TEXT NOT NULL DEFAULT '',   -- HH:MM, rỗng = cả ngày
    description TEXT NOT NULL DEFAULT '',
    source_url  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_user_date ON events (user_id, date);

CREATE TABLE IF NOT EXISTS courses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    credits    INTEGER NOT NULL,
    semester   TEXT NOT NULL,                -- ví dụ 115-1
    grade      TEXT NOT NULL DEFAULT '',     -- rỗng = chưa có điểm (đang học / dự định)
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_courses_user_semester ON courses (user_id, semester);

-- Mỗi người dùng tối đa một dòng mục tiêu (user_id vừa là khóa chính vừa là khóa ngoại)
CREATE TABLE IF NOT EXISTS goals (
    user_id          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    target_gpa       REAL NOT NULL,
    credits_required INTEGER NOT NULL
);

-- Study planning
CREATE TABLE IF NOT EXISTS subjects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',     -- tài liệu: link, sách, ghi chú
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subjects_user ON subjects (user_id);

-- Xóa môn học thì việc và buổi học còn lại, chỉ mất liên kết (SET NULL).
-- Xóa việc cha thì các việc con bị xóa theo (CASCADE).
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    parent_id  INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    due_date   TEXT NOT NULL DEFAULT '',     -- YYYY-MM-DD, rỗng = không có hạn
    done       INTEGER NOT NULL DEFAULT 0,   -- 0 hoặc 1
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks (user_id);

CREATE TABLE IF NOT EXISTS study_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    date       TEXT NOT NULL,                -- YYYY-MM-DD
    minutes    INTEGER NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON study_sessions (user_id, date);

-- Thời khóa biểu tuần: mỗi dòng là một môn lặp lại vào một thứ cố định
CREATE TABLE IF NOT EXISTS classes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    weekday    INTEGER NOT NULL,             -- 0 = Thứ 2 ... 6 = Chủ nhật
    start      TEXT NOT NULL,                -- HH:MM
    "end"      TEXT NOT NULL,                -- HH:MM ("end" là từ khóa SQL nên phải đặt trong ngoặc kép)
    room       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_classes_user ON classes (user_id);

-- Link lịch bí mật (.ics) để Google / Apple Calendar tự đồng bộ; chọn đồng bộ những gì
CREATE TABLE IF NOT EXISTS calendar_feeds (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    token   TEXT NOT NULL UNIQUE,
    classes INTEGER NOT NULL DEFAULT 1,
    events  INTEGER NOT NULL DEFAULT 1,
    tasks   INTEGER NOT NULL DEFAULT 0
);

-- Lịch bên ngoài (Google Calendar...) hiện trong app: link .ics bí mật và trạng thái lần tải gần nhất
CREATE TABLE IF NOT EXISTS calendar_imports (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    url        TEXT NOT NULL DEFAULT '',     -- rỗng = sự kiện đến từ file .ics tải lên
    fetched_at REAL NOT NULL DEFAULT 0,      -- time.time() lần tải gần nhất
    error      TEXT NOT NULL DEFAULT ''      -- lỗi lần tải gần nhất (rỗng = thành công)
);

-- Sự kiện đọc từ lịch bên ngoài (chỉ để xem; mỗi lần tải lại thì thay toàn bộ)
CREATE TABLE IF NOT EXISTS imported_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date     TEXT NOT NULL,
    time     TEXT NOT NULL DEFAULT '',
    end_time TEXT NOT NULL DEFAULT '',
    title    TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_imported_user_date ON imported_events (user_id, date);

-- Các lần đăng nhập sai gần đây (login_guard.py quyết định có khóa hay không)
CREATE TABLE IF NOT EXISTS login_failures (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip    TEXT NOT NULL,
    at    REAL NOT NULL                    -- giây, time.time()
);

CREATE INDEX IF NOT EXISTS idx_login_failures_ip ON login_failures (ip, at);
"""

EVENT_COLUMNS = "id, title, date, time, description, source_url"

_ready = set()  # các file database đã tạo bảng trong lần chạy này


def get_db():
    """Mở kết nối cho request hiện tại (mỗi request một kết nối, lưu trong g)."""
    if "db" not in g:
        path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row            # truy cập cột theo tên
        conn.execute("PRAGMA foreign_keys = ON")  # bật ràng buộc khóa ngoại
        if path not in _ready:
            conn.executescript(SCHEMA)            # tạo bảng nếu chưa có
            _ready.add(path)
        g.db = conn
    return g.db


def close_db(exception=None):
    """Đóng kết nối khi request kết thúc (đăng ký bằng app.teardown_appcontext)."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------- users ----------

def create_user(email, password_hash):
    """Thêm người dùng, trả về id. Email trùng -> ném sqlite3.IntegrityError."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, password_hash),
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_email(email):
    row = get_db().execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    return dict(row) if row else None


# ---------- đăng nhập sai (chống đoán mật khẩu) ----------

def add_login_failure(email, ip, now, keep_seconds):
    """Ghi một lần đăng nhập sai và xóa luôn các bản ghi quá cũ cho bảng không phình ra."""
    conn = get_db()
    conn.execute("DELETE FROM login_failures WHERE at <= ?", (now - keep_seconds,))
    conn.execute("INSERT INTO login_failures (email, ip, at) VALUES (?, ?, ?)", (email, ip, now))
    conn.commit()


def login_failure_times(email, ip, since):
    """Trả về (các lần sai của email này từ ip này, các lần sai từ ip này) kể từ `since`."""
    conn = get_db()
    account = [row["at"] for row in conn.execute(
        "SELECT at FROM login_failures WHERE email = ? AND ip = ? AND at > ?", (email, ip, since))]
    by_ip = [row["at"] for row in conn.execute(
        "SELECT at FROM login_failures WHERE ip = ? AND at > ?", (ip, since))]
    return account, by_ip


def clear_login_failures(email, ip):
    """Đăng nhập đúng: xóa các lần sai của email này từ ip này."""
    conn = get_db()
    conn.execute("DELETE FROM login_failures WHERE email = ? AND ip = ?", (email, ip))
    conn.commit()


def get_user(user_id):
    """Người dùng KÈM bản băm mật khẩu (app.py dùng để kiểm tra phiên và mật khẩu cũ, không đưa ra template)."""
    row = get_db().execute(
        "SELECT id, email, password_hash, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def update_password(user_id, password_hash):
    """Đổi mật khẩu (lưu bản băm mới)."""
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()


def delete_user(user_id):
    """Xóa tài khoản. Mọi bảng khác có "REFERENCES users(id) ON DELETE CASCADE"
    (và PRAGMA foreign_keys = ON trong get_db), nên sự kiện, lớp học, môn, việc học... bị xóa theo."""
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


# ---------- events ----------

def add_event(user_id, event):
    """Thêm sự kiện cho user_id, trả về sự kiện vừa tạo (có id)."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO events (user_id, title, date, time, description, source_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, event["title"], event["date"], event["time"],
         event["description"], event["source_url"]),
    )
    conn.commit()
    return get_event(user_id, cursor.lastrowid)


def get_event(user_id, event_id):
    """Lấy một sự kiện. Không tồn tại HOẶC không thuộc user_id -> None."""
    row = get_db().execute(
        f"SELECT {EVENT_COLUMNS} FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def list_events(user_id, start=None, end=None):
    """Sự kiện của user_id, xếp theo ngày rồi giờ.

    start/end (YYYY-MM-DD, tùy chọn): lấy các ngày từ start đến TRƯỚC end.
    """
    sql = f"SELECT {EVENT_COLUMNS} FROM events WHERE user_id = ?"
    params = [user_id]
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date < ?"
        params.append(end)
    sql += " ORDER BY date, time, id"
    return [dict(row) for row in get_db().execute(sql, params).fetchall()]


def upcoming_events(user_id, from_date, limit=5):
    """Các sự kiện từ ngày from_date trở đi (gần nhất trước)."""
    rows = get_db().execute(
        f"SELECT {EVENT_COLUMNS} FROM events WHERE user_id = ? AND date >= ? "
        "ORDER BY date, time, id LIMIT ?",
        (user_id, from_date, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def update_event(user_id, event_id, event):
    """Sửa sự kiện. Trả về sự kiện mới, hoặc None nếu không có/không thuộc user."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE events SET title = ?, date = ?, time = ?, description = ?, source_url = ? "
        "WHERE id = ? AND user_id = ?",
        (event["title"], event["date"], event["time"], event["description"],
         event["source_url"], event_id, user_id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return None
    return get_event(user_id, event_id)


def delete_event(user_id, event_id):
    """Xóa sự kiện. True nếu xóa được, False nếu không có/không thuộc user."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM events WHERE id = ? AND user_id = ?", (event_id, user_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def saved_keys(user_id):
    """Tập các cặp (title, date) mà user đã có, để đánh dấu "Saved" trên trang Announcements."""
    rows = get_db().execute(
        "SELECT title, date FROM events WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {(row["title"], row["date"]) for row in rows}


# ---------- courses (Credit & GPA) ----------

COURSE_COLUMNS = "id, name, credits, semester, grade"


def add_course(user_id, course):
    """Thêm môn học cho user_id, trả về môn vừa tạo (có id)."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO courses (user_id, name, credits, semester, grade) VALUES (?, ?, ?, ?, ?)",
        (user_id, course["name"], course["credits"], course["semester"], course["grade"]),
    )
    conn.commit()
    return get_course(user_id, cursor.lastrowid)


def get_course(user_id, course_id):
    """Một môn học. Không tồn tại HOẶC không thuộc user_id -> None."""
    row = get_db().execute(
        f"SELECT {COURSE_COLUMNS} FROM courses WHERE id = ? AND user_id = ?",
        (course_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def list_courses(user_id):
    """Tất cả môn học của user_id, xếp theo học kỳ rồi tên."""
    rows = get_db().execute(
        f"SELECT {COURSE_COLUMNS} FROM courses WHERE user_id = ? ORDER BY semester, name, id",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_course(user_id, course_id, course):
    """Sửa môn học. Trả về môn mới, hoặc None nếu không có/không thuộc user."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE courses SET name = ?, credits = ?, semester = ?, grade = ? "
        "WHERE id = ? AND user_id = ?",
        (course["name"], course["credits"], course["semester"], course["grade"],
         course_id, user_id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return None
    return get_course(user_id, course_id)


def delete_course(user_id, course_id):
    """Xóa môn học. True nếu xóa được, False nếu không có/không thuộc user."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM courses WHERE id = ? AND user_id = ?", (course_id, user_id)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- goals ----------

def get_goals(user_id):
    """Mục tiêu của user_id, hoặc None nếu chưa đặt."""
    row = get_db().execute(
        "SELECT target_gpa, credits_required FROM goals WHERE user_id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def set_goals(user_id, goals):
    """Đặt mục tiêu. "Upsert": chưa có dòng thì thêm, có rồi thì cập nhật."""
    conn = get_db()
    conn.execute(
        "INSERT INTO goals (user_id, target_gpa, credits_required) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "target_gpa = excluded.target_gpa, credits_required = excluded.credits_required",
        (user_id, goals["target_gpa"], goals["credits_required"]),
    )
    conn.commit()
    return get_goals(user_id)


# ---------- subjects (Study planning) ----------

SUBJECT_COLUMNS = "id, name, notes"


def add_subject(user_id, subject):
    """Thêm môn học, trả về môn vừa tạo."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO subjects (user_id, name, notes) VALUES (?, ?, ?)",
        (user_id, subject["name"], subject["notes"]),
    )
    conn.commit()
    return get_subject(user_id, cursor.lastrowid)


def get_subject(user_id, subject_id):
    """Không tồn tại HOẶC không thuộc user_id -> None."""
    row = get_db().execute(
        f"SELECT {SUBJECT_COLUMNS} FROM subjects WHERE id = ? AND user_id = ?",
        (subject_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def list_subjects(user_id):
    rows = get_db().execute(
        f"SELECT {SUBJECT_COLUMNS} FROM subjects WHERE user_id = ? ORDER BY name COLLATE NOCASE, id",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_subject(user_id, subject_id, subject):
    conn = get_db()
    cursor = conn.execute(
        "UPDATE subjects SET name = ?, notes = ? WHERE id = ? AND user_id = ?",
        (subject["name"], subject["notes"], subject_id, user_id),
    )
    conn.commit()
    return get_subject(user_id, subject_id) if cursor.rowcount else None


def delete_subject(user_id, subject_id):
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM subjects WHERE id = ? AND user_id = ?", (subject_id, user_id)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- tasks ----------

TASK_COLUMNS = "id, subject_id, parent_id, title, due_date, done"


def _task_row(row):
    """Dòng database -> dict; cột done (0/1) đổi thành True/False."""
    task = dict(row)
    task["done"] = bool(task["done"])
    return task


def add_task(user_id, task):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tasks (user_id, subject_id, parent_id, title, due_date, done) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, task["subject_id"], task["parent_id"], task["title"],
         task["due_date"], int(task["done"])),
    )
    conn.commit()
    return get_task(user_id, cursor.lastrowid)


def get_task(user_id, task_id):
    row = get_db().execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
    ).fetchone()
    return _task_row(row) if row else None


def list_tasks(user_id):
    rows = get_db().execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [_task_row(row) for row in rows]


def list_tasks_due(user_id, start, end):
    """Việc CHƯA XONG của user_id có hạn nộp từ start đến TRƯỚC end (để hiện trên Calendar)."""
    rows = get_db().execute(
        f"SELECT {TASK_COLUMNS} FROM tasks "
        "WHERE user_id = ? AND done = 0 AND due_date != '' AND due_date >= ? AND due_date < ? "
        "ORDER BY due_date, id",
        (user_id, start, end),
    ).fetchall()
    return [_task_row(row) for row in rows]


def update_task(user_id, task_id, task):
    """Sửa tiêu đề, hạn, trạng thái, môn. parent_id KHÔNG đổi được sau khi tạo."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE tasks SET subject_id = ?, title = ?, due_date = ?, done = ? "
        "WHERE id = ? AND user_id = ?",
        (task["subject_id"], task["title"], task["due_date"], int(task["done"]), task_id, user_id),
    )
    conn.commit()
    return get_task(user_id, task_id) if cursor.rowcount else None


def delete_task(user_id, task_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    return cursor.rowcount > 0


# ---------- study sessions ----------

SESSION_COLUMNS = "id, subject_id, date, minutes, note"


def add_session(user_id, session):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO study_sessions (user_id, subject_id, date, minutes, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, session["subject_id"], session["date"], session["minutes"], session["note"]),
    )
    conn.commit()
    return get_session(user_id, cursor.lastrowid)


def get_session(user_id, session_id):
    row = get_db().execute(
        f"SELECT {SESSION_COLUMNS} FROM study_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def list_sessions(user_id):
    """Buổi học mới nhất trước."""
    rows = get_db().execute(
        f"SELECT {SESSION_COLUMNS} FROM study_sessions WHERE user_id = ? ORDER BY date DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_session(user_id, session_id, session):
    conn = get_db()
    cursor = conn.execute(
        "UPDATE study_sessions SET subject_id = ?, date = ?, minutes = ?, note = ? "
        "WHERE id = ? AND user_id = ?",
        (session["subject_id"], session["date"], session["minutes"], session["note"],
         session_id, user_id),
    )
    conn.commit()
    return get_session(user_id, session_id) if cursor.rowcount else None


def delete_session(user_id, session_id):
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM study_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- classes (thời khóa biểu tuần) ----------

CLASS_COLUMNS = 'id, name, weekday, start, "end" AS end, room'


def add_class(user_id, item):
    """Thêm một môn vào thời khóa biểu, trả về môn vừa tạo."""
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO classes (user_id, name, weekday, start, "end", room) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, item["name"], item["weekday"], item["start"], item["end"], item["room"]),
    )
    conn.commit()
    return get_class(user_id, cursor.lastrowid)


def get_class(user_id, class_id):
    """Không tồn tại HOẶC không thuộc user_id -> None."""
    row = get_db().execute(
        f"SELECT {CLASS_COLUMNS} FROM classes WHERE id = ? AND user_id = ?", (class_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def list_classes(user_id):
    rows = get_db().execute(
        f"SELECT {CLASS_COLUMNS} FROM classes WHERE user_id = ? ORDER BY weekday, start, id", (user_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def update_class(user_id, class_id, item):
    conn = get_db()
    cursor = conn.execute(
        'UPDATE classes SET name = ?, weekday = ?, start = ?, "end" = ?, room = ? '
        "WHERE id = ? AND user_id = ?",
        (item["name"], item["weekday"], item["start"], item["end"], item["room"], class_id, user_id),
    )
    conn.commit()
    return get_class(user_id, class_id) if cursor.rowcount else None


def delete_all_classes(user_id):
    """Xóa cả thời khóa biểu của một người (dùng khi nhập lại thời khóa biểu học kỳ mới)."""
    conn = get_db()
    cursor = conn.execute("DELETE FROM classes WHERE user_id = ?", (user_id,))
    conn.commit()
    return cursor.rowcount


def add_classes(user_id, items):
    """Thêm nhiều môn trong một lần commit (nhập thời khóa biểu). Trả về số môn đã thêm."""
    conn = get_db()
    conn.executemany(
        'INSERT INTO classes (user_id, name, weekday, start, "end", room) VALUES (?, ?, ?, ?, ?, ?)',
        [(user_id, i["name"], i["weekday"], i["start"], i["end"], i["room"]) for i in items],
    )
    conn.commit()
    return len(items)


def delete_class(user_id, class_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM classes WHERE id = ? AND user_id = ?", (class_id, user_id))
    conn.commit()
    return cursor.rowcount > 0


# ======================= link lịch .ics =======================

def _feed_row(row):
    return {"user_id": row["user_id"], "token": row["token"], "classes": bool(row["classes"]),
            "events": bool(row["events"]), "tasks": bool(row["tasks"])} if row else None


def get_feed(user_id):
    """Cài đặt đồng bộ lịch của user_id, chưa bật -> None."""
    return _feed_row(get_db().execute("SELECT * FROM calendar_feeds WHERE user_id = ?", (user_id,)).fetchone())


def get_feed_by_token(token):
    """Tìm cài đặt theo link bí mật (route /calendar/feed/<token>.ics không cần đăng nhập)."""
    return _feed_row(get_db().execute("SELECT * FROM calendar_feeds WHERE token = ?", (token,)).fetchone())


def save_feed(user_id, token, classes, events, tasks):
    """Bật / cập nhật đồng bộ lịch (một dòng mỗi người)."""
    conn = get_db()
    conn.execute(
        "INSERT INTO calendar_feeds (user_id, token, classes, events, tasks) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET token = excluded.token, classes = excluded.classes, "
        "events = excluded.events, tasks = excluded.tasks",
        (user_id, token, int(classes), int(events), int(tasks)),
    )
    conn.commit()


def delete_feed(user_id):
    """Tắt đồng bộ: link cũ hết dùng được."""
    conn = get_db()
    conn.execute("DELETE FROM calendar_feeds WHERE user_id = ?", (user_id,))
    conn.commit()


def list_open_tasks_with_due(user_id):
    """Mọi việc CHƯA XONG có hạn nộp (cho file lịch)."""
    return list_tasks_due(user_id, "0000-01-01", "9999-12-31")


# ======================= lịch bên ngoài hiện trong app =======================

def get_import(user_id):
    """Cài đặt lịch bên ngoài của user_id (url, fetched_at, error) hoặc None nếu chưa kết nối."""
    row = get_db().execute("SELECT url, fetched_at, error FROM calendar_imports WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def save_import(user_id, url):
    """Kết nối (hoặc đổi) link lịch; fetched_at = 0 để lần mở Calendar tới sẽ tải ngay."""
    conn = get_db()
    conn.execute("INSERT INTO calendar_imports (user_id, url, fetched_at, error) VALUES (?, ?, 0, '') "
                 "ON CONFLICT(user_id) DO UPDATE SET url = excluded.url, fetched_at = 0, error = ''", (user_id, url))
    conn.commit()


def set_import_status(user_id, fetched_at, error):
    """Ghi kết quả lần tải gần nhất."""
    conn = get_db()
    conn.execute("UPDATE calendar_imports SET fetched_at = ?, error = ? WHERE user_id = ?", (fetched_at, error, user_id))
    conn.commit()


def replace_imported_events(user_id, events):
    """Thay TOÀN BỘ sự kiện đã đọc của user_id bằng danh sách mới (trong một lần commit)."""
    conn = get_db()
    conn.execute("DELETE FROM imported_events WHERE user_id = ?", (user_id,))
    conn.executemany(
        "INSERT INTO imported_events (user_id, date, time, end_time, title, location) VALUES (?, ?, ?, ?, ?, ?)",
        [(user_id, e["date"], e["time"], e["end_time"], e["title"], e["location"]) for e in events])
    conn.commit()


def list_imported_events(user_id, start, end):
    """Sự kiện đã đọc từ lịch bên ngoài, ngày từ start đến TRƯỚC end, theo ngày rồi giờ."""
    rows = get_db().execute(
        "SELECT id, date, time, end_time, title, location FROM imported_events "
        "WHERE user_id = ? AND date >= ? AND date < ? ORDER BY date, time, id", (user_id, start, end)).fetchall()
    return [dict(row) for row in rows]


def count_imported_events(user_id):
    return get_db().execute("SELECT COUNT(*) FROM imported_events WHERE user_id = ?", (user_id,)).fetchone()[0]


def delete_import(user_id):
    """Ngắt kết nối: xóa link và mọi sự kiện đã đọc."""
    conn = get_db()
    conn.execute("DELETE FROM imported_events WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM calendar_imports WHERE user_id = ?", (user_id,))
    conn.commit()


# ======================= số liệu cho trang chủ =======================

COUNTED_TABLES = ("classes", "events", "tasks", "courses", "goals")


def user_counts(user_id):
    """Số dòng của người dùng trong từng bảng, ví dụ {"classes": 3, "events": 0, ...}.

    Tên bảng ghép vào câu SQL chỉ lấy từ COUNTED_TABLES (do code viết sẵn, không phải dữ liệu người dùng),
    còn user_id vẫn truyền bằng dấu ? như mọi câu SQL khác.
    """
    db = get_db()
    return {table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)).fetchone()[0]
            for table in COUNTED_TABLES}
