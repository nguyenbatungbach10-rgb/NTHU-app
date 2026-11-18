"""Luật về mật khẩu và phiên đăng nhập (Python thuần, dễ test). app.py gọi các hàm này.

- password_error(): một luật mật khẩu duy nhất cho cả Đăng ký và Đổi mật khẩu.
- auth_tag(): "dấu" của mật khẩu hiện tại, lưu trong phiên đăng nhập. Đổi mật khẩu thì dấu đổi,
  nên mọi phiên cũ trên máy khác không còn khớp và bị đăng xuất (app.py kiểm tra ở mỗi request).
"""
import hashlib
import hmac

MIN_PASSWORD = 8
MAX_PASSWORD = 128
REMEMBER_DAYS = 30   # "Remember me": giữ đăng nhập 30 ngày kể từ lần mở web gần nhất


def password_error(password, confirm):
    """Trả về câu báo lỗi (tiếng Anh, dịch lúc hiển thị) hoặc None nếu mật khẩu dùng được."""
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        return "Password must be 8 to 128 characters."
    if password != confirm:
        return "Passwords do not match."
    return None


def auth_tag(secret_key, password_hash):
    """16 ký tự HMAC của bản băm mật khẩu.

    Không lưu chính bản băm vào phiên: cookie phiên của Flask được KÝ (không sửa được) nhưng
    KHÔNG mã hóa (ai cầm cookie cũng đọc được), nên chỉ lưu một dấu không thể đoán ngược.
    """
    digest = hmac.new(secret_key.encode(), password_hash.encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def same_tag(session_tag, expected):
    """So hai dấu theo thời gian cố định (không lộ thông tin qua tốc độ so sánh)."""
    return isinstance(session_tag, str) and hmac.compare_digest(session_tag, expected)
