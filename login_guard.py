"""Chặn đoán mật khẩu: khóa đăng nhập tạm thời sau nhiều lần nhập sai (Python thuần, dễ test).

Cách làm:
  - Mỗi lần đăng nhập sai, app.py lưu (email, ip, thời điểm) vào bảng login_failures (db.py).
  - Trước khi kiểm tra mật khẩu, lấy các lần sai gần đây rồi hỏi lockout_minutes().
  - Có 2 giới hạn:
      MAX_PER_ACCOUNT lần sai cho CÙNG email từ CÙNG một IP  -> chặn đoán mật khẩu 1 tài khoản
      MAX_PER_IP      lần sai từ một IP cho BẤT KỲ email nào -> chặn thử lần lượt nhiều tài khoản
    Đếm theo (email + IP) chứ không chỉ theo email, để người lạ không thể cố tình
    nhập sai để khóa tài khoản của bạn khi bạn đăng nhập từ máy khác.
  - Đăng nhập đúng thì xóa các lần sai của email đó (clear trong db.py).
"""
import math

WINDOW_SECONDS = 15 * 60   # chỉ tính các lần sai trong 15 phút gần nhất
MAX_PER_ACCOUNT = 5
MAX_PER_IP = 20


def recent(times, now, window=WINDOW_SECONDS):
    """Giữ lại các thời điểm (giây, kiểu time.time()) còn nằm trong cửa sổ 15 phút."""
    return [t for t in times if now - window < t <= now]


def _wait_minutes(times, limit, now, window):
    """Số phút còn phải chờ nếu đã sai >= limit lần; 0 nếu chưa tới giới hạn."""
    times = sorted(recent(times, now, window))
    if len(times) < limit:
        return 0
    # Lần sai thứ (len - limit + 1) tính từ cũ nhất hết hạn thì số lần sai tụt xuống dưới giới hạn
    unlock_at = times[len(times) - limit] + window
    return max(1, math.ceil((unlock_at - now) / 60))


def lockout_minutes(account_times, ip_times, now, window=WINDOW_SECONDS,
                    max_account=MAX_PER_ACCOUNT, max_ip=MAX_PER_IP):
    """Trả về số phút phải chờ trước khi được thử lại (0 = được thử ngay).

    account_times: thời điểm các lần sai của email này từ IP này
    ip_times:      thời điểm các lần sai từ IP này (mọi email)
    """
    return max(_wait_minutes(account_times, max_account, now, window),
               _wait_minutes(ip_times, max_ip, now, window))
