"""Cài web lên màn hình điện thoại như một app (PWA = Progressive Web App). Python thuần, dễ test.

Trình duyệt cần 3 thứ để cho "Thêm vào màn hình chính / Install app":
  1. manifest (/manifest.webmanifest): tên app, icon, màu, mở toàn màn hình (display: standalone)
  2. service worker (/sw.js, static/sw.js): chạy nền trong trình duyệt; ở đây chỉ dùng để
     hiện trang "Bạn đang offline" khi mất mạng thay vì trang lỗi của trình duyệt
  3. HTTPS (PythonAnywhere đã có)
"""
CACHE_VERSION = "v3"        # đổi khi sửa danh sách OFFLINE_FILES để trình duyệt tải lại bản mới
THEME_COLOR = "#6a35c9"     # màu tím của logo (thanh trạng thái điện thoại)
BACKGROUND = "#f6f2fc"      # màu nền màn hình chờ khi mở app
ICONS = [
    {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "/static/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]
# Những file service worker lưu sẵn để trang offline vẫn đẹp khi mất mạng (KHÔNG lưu dữ liệu cá nhân)
OFFLINE_FILES = ["/offline", "/static/style.css", "/static/favicon.svg", "/static/icons/icon-192.png"]


def manifest(translate, lang):
    """Nội dung manifest (dict -> Flask trả JSON). translate(text) dịch theo ngôn ngữ người dùng."""
    return {
        "name": translate("NTHU Campus Assistant"),
        "short_name": translate("NTHU App"),
        "description": translate("Classes, deadlines, grades, campus map and NTHU announcements in one place."),
        "lang": lang,
        "start_url": "/?source=app",
        "scope": "/",
        "display": "standalone",
        "background_color": BACKGROUND,
        "theme_color": THEME_COLOR,
        "icons": ICONS,
        "shortcuts": [
            {"name": translate("Schedule"), "url": "/schedule"},
            {"name": translate("Calendar"), "url": "/calendar"},
            {"name": translate("Campus map"), "url": "/map"},
        ],
    }
