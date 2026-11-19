# Giải thích: tăng tốc web (bản 22)

## Đo trước khi sửa (web thật, trình duyệt trên máy ở Đông Nam Á, 19/11/2026)
- Một lượt đi về tới server PythonAnywhere mất **~220 ms** (server ở xa). Mở kết nối mới (TCP + HTTPS) ~430 ms.
- Trang thường: **230–290 ms** (gần như toàn bộ là đường truyền; server chỉ xử lý 2–7 ms).
- Thỉnh thoảng **1–1,5 giây** (trang chủ 1.514 ms, tab Talks & events 1.033 ms).
- PythonAnywhere **đã tự nén** (gzip): trang 43 KB gửi đi 7,5 KB, style.css 62 KB → 13,5 KB. Phần này không cần làm.
- `style.css` và `app.js` có `Cache-Control: no-cache` → trang nào cũng hỏi lại server (thêm ~230 ms, và trang phải
  chờ CSS mới hiện).

## Sửa 1: bỏ những lần chậm 1 giây (`nthu_api.py`)
Nguyên nhân: bộ nhớ tạm thông báo hết hạn sau 5 phút. Khi đó người dùng kế tiếp phải chờ server
(a) thử gọi api.nthusa.tw (luôn bị PythonAnywhere chặn), (b) đọc lại file bản lưu 600 KB và phân loại 4.500 thông báo,
(c) tính lại ngày trong 4.500 tiêu đề (vì có danh sách mới nên kết quả nhớ cũ không dùng được).
- `_read_snapshot` **nhớ kết quả theo thời điểm sửa file** (`os.stat`): file không đổi → trả về đúng danh sách cũ,
  không đọc lại. Vì là cùng một danh sách, `upcoming_dates` cũng dùng lại kết quả đã tính.
  GitHub tải bản lưu mới lên (2 lần/ngày) → thời điểm sửa file đổi → lần sau mới đọc lại.
- **API lỗi thì 1 tiếng sau mới thử lại** (`API_RETRY_SECONDS`), và chỉ chờ kết nối tối đa 3 giây (`API_TIMEOUT`, trước là 15).
- `classify`: mỗi chủ đề gộp mọi từ khóa thành một biểu thức `a|b|c` (một lượt tìm thay vì thử từng từ):
  phân loại 4.500 tiêu đề từ ~250 ms còn ~30 ms.
- Kết quả: lần làm mới sau 5 phút từ ~300 ms (máy thử) / ~1–1,5 s (PythonAnywhere) còn **0,2 ms**.

## Sửa 2: làm nóng khi khởi động (`app.warm_caches`)
Khi server khởi động lại (bấm Reload, hoặc PythonAnywhere tự khởi động lại), người vào đầu tiên phải chờ mọi thứ được
chuẩn bị. Giờ ngay khi chạy (chỉ khi `PRODUCTION=1`), web tự đọc bản lưu, tính ngày trong tiêu đề, đọc dữ liệu bản đồ
và dịch sẵn các template Jinja. Lỗi ở bước này chỉ in ra log, không làm web ngừng chạy.

## Sửa 3: cho trình duyệt nhớ CSS/JS 1 năm (`app.static_version`, `add_static_version`, `cache_static`)
- `url_for('static', filename='style.css')` tự thành `/static/style.css?v=1795027853` (số = thời điểm sửa file).
- File tĩnh có `?v=` được trả kèm `Cache-Control: public, max-age=31536000, immutable`: trình duyệt nhớ 1 năm và
  **không hỏi lại server**. Sửa CSS rồi deploy → thời điểm sửa đổi → link đổi → trình duyệt tự tải bản mới.
- Đã thử trên Chromium: trang thứ hai chỉ còn **1 request** (trang HTML), CSS/JS lấy từ bộ nhớ trình duyệt.
- Service worker (`static/sw.js`) khớp file tĩnh bỏ qua phần `?v=` khi mất mạng, để trang offline vẫn có CSS.

## Sửa 4: font không chặn trang (`base.html`)
`<link rel="stylesheet" ... media="print" onload="this.media='all'">`: trình duyệt không chờ file font của Google trước khi vẽ
trang; trang hiện ngay bằng font hệ thống, font Bricolage/Figtree thay vào khi tải xong (`display=swap`).

## Sửa 5: chuyển trang tức thì (Speculation Rules, `base.html`)
Thẻ `<script type="speculationrules">` báo cho Chrome / Edge / Chrome Android: khi rê chuột (máy tính) hoặc chạm (điện thoại)
vào một link trong web, tải trước trang đó ở chế độ ẩn ("prerender"). Bấm xong là trang hiện ngay, che được ~230 ms đi về.
- Thử trên Chromium: rê chuột vào link → server nhận request trước; bấm → trang hiện sau **73 ms**.
- Không tải trước: `/logout`, file lịch `/calendar/feed/...`, file tĩnh, link mở tab mới. Trang nào cũng chỉ là GET
  (không thay đổi dữ liệu) nên tải trước an toàn. Safari / Firefox bỏ qua thẻ này, web vẫn chạy bình thường.
- Trang Map: `preconnect` tới unpkg.com và tiles.openfreemap.org để mở kết nối sớm.

## Không sửa được (nói thật)
- **~220 ms đường truyền mỗi lượt** là do server PythonAnywhere ở xa; gói miễn phí không chọn được server gần
  Đài Loan. Sửa 3 và 5 giúp người dùng ít phải chờ lượt đi về đó.

## Câu hỏi TA có thể hỏi
1. **Cache là gì?** Lưu lại kết quả đã tính / đã tải để lần sau dùng luôn, không làm lại. Web có 3 tầng: bộ nhớ của server
   (thông báo, bản đồ), bộ nhớ của trình duyệt (CSS/JS 1 năm), và trang tải trước (prerender).
2. **Nhớ lâu như vậy, sửa CSS thì sao?** Link có `?v=<thời điểm sửa file>`; file đổi thì link đổi, trình duyệt coi là file mới.
3. **Sao biết file bản lưu có đổi không mà không đọc file?** `os.stat` cho biết thời điểm sửa và kích thước file
   (rất nhanh); khác lần trước thì mới đọc lại.
