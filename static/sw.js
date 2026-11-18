// Service worker: chạy nền trong trình duyệt khi web được cài như app (xem pwa.py).
// Chỉ làm MỘT việc: mất mạng thì hiện trang /offline thay vì trang lỗi của trình duyệt.
// Không lưu trang có dữ liệu cá nhân (lịch, điểm...) vào bộ nhớ đệm.
// CACHE_VERSION và OFFLINE_FILES do Python (app.py, route /sw.js) ghi vào đầu file này, lấy từ pwa.py.
const CACHE = "nthu-offline-" + CACHE_VERSION;
const FILES = OFFLINE_FILES;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // Xóa bộ nhớ đệm của phiên bản cũ
  event.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k.startsWith("nthu-offline-") && k !== CACHE).map((k) => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;   // chỉ xử lý khi mở một trang
  event.respondWith(fetch(event.request).catch(() => caches.match("/offline")));
});
