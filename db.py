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


def get_user(user_id):
    row = get_db().execute(
        "SELECT id, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


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
