"""Gửi file bản lưu thông báo lên PythonAnywhere qua API của PythonAnywhere (GitHub Actions chạy mỗi ngày).

Vì sao cần: server PythonAnywhere (gói miễn phí) không gọi được api.nthusa.tw, và tài khoản miễn phí mới
không có "scheduled task". Nên máy của GitHub tải thông báo (tools/save_announcements.py) rồi gửi file
lên tài khoản của mình bằng API file của PythonAnywhere (gói miễn phí cũng dùng được).

Cần 2 biến môi trường (đặt trong GitHub > Settings > Secrets and variables > Actions):
    PA_USERNAME   tên tài khoản PythonAnywhere, ví dụ nthuapp
    PA_TOKEN      API token (PythonAnywhere > Account > API token). Đây là BÍ MẬT: không in ra, không commit.
Tùy chọn: PA_HOST (mặc định www.pythonanywhere.com; tài khoản ở châu Âu là eu.pythonanywhere.com),
          PA_PROJECT_DIR (mặc định /home/<PA_USERNAME>/NTHU-app).

Chạy:  python tools/upload_snapshot.py snapshot.json
File được ghi vào <PA_PROJECT_DIR>/instance/announcements_snapshot.json; web tự đọc bản mới trong vòng 5 phút
(nthu_api.load_snapshot lấy bản lưu mới hơn), không cần Reload.
"""
import os
import sys
from pathlib import Path

import requests


def target_path(username, project_dir=""):
    """Đường dẫn file trên PythonAnywhere (thư mục instance/ không có trong git nên git pull không bị đụng)."""
    project_dir = (project_dir or f"/home/{username}/NTHU-app").rstrip("/")
    return f"{project_dir}/instance/announcements_snapshot.json"


def upload_url(host, username, path):
    """URL của API file: POST https://<host>/api/v0/user/<username>/files/path<path>."""
    return f"https://{host}/api/v0/user/{username}/files/path{path}"


def read_settings(environ):
    """Lấy cấu hình từ biến môi trường; thiếu PA_USERNAME / PA_TOKEN -> None."""
    username, token = environ.get("PA_USERNAME", "").strip(), environ.get("PA_TOKEN", "").strip()
    if not username or not token:
        return None
    return {"username": username, "token": token,
            "host": environ.get("PA_HOST", "").strip() or "www.pythonanywhere.com",
            "project_dir": environ.get("PA_PROJECT_DIR", "").strip()}


def main(args, environ=os.environ):
    """Trả 0 nếu gửi được, 1 nếu lỗi (GitHub Actions sẽ báo đỏ)."""
    if len(args) != 1 or not Path(args[0]).is_file():
        print("Usage: python tools/upload_snapshot.py <snapshot file>")
        return 1
    settings = read_settings(environ)
    if settings is None:
        print("PA_USERNAME and PA_TOKEN must be set (GitHub repository secrets).")
        return 1
    path = target_path(settings["username"], settings["project_dir"])
    try:
        with open(args[0], "rb") as file:
            response = requests.post(upload_url(settings["host"], settings["username"], path),
                                     files={"content": file},
                                     headers={"Authorization": f"Token {settings['token']}"}, timeout=60)
    except requests.RequestException as error:
        print(f"Could not reach PythonAnywhere: {error}")
        return 1
    if response.status_code not in (200, 201):   # 201 = tạo file mới, 200 = ghi đè file cũ
        print(f"Upload failed: HTTP {response.status_code}. Check PA_USERNAME, PA_TOKEN and PA_HOST.")
        return 1
    print(f"Uploaded to {path} (HTTP {response.status_code}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
