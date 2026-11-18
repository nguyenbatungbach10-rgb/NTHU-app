# Giải thích: hai ngôn ngữ (English / 繁體中文) và chế độ sáng / tối

## 1. Người dùng thấy gì
- Thanh trên cùng có hai nút nhỏ: **EN / 中文** (đổi ngôn ngữ) và **mặt trăng / mặt trời** (đổi sáng ↔ tối).
- Trong menu có đầy đủ lựa chọn: Language (English, 繁體中文) và Theme (Light, Dark, Auto = theo cài đặt của máy).
- Lựa chọn được nhớ 1 năm (cookie). Lần đầu vào trang, nếu trình duyệt đặt tiếng Trung thì trang tự hiện tiếng Trung.

## 2. Dịch hoạt động thế nào (i18n.py)
- Bản dịch là một **dict Python** `ZH`: khóa là câu tiếng Anh, giá trị là câu tiếng Trung phồn thể (cách dùng ở Đài Loan:
  行事曆, 課表, 登入, 儲存...).
- Template gọi `{{ _('Calendar') }}`. Hàm `_` (trong app.py) gọi `i18n.translate(text, ngôn_ngữ)`:
  tiếng Anh thì trả lại nguyên câu; tiếng Trung thì tra `ZH`; **thiếu bản dịch thì vẫn hiện tiếng Anh** nên trang không bao giờ hỏng.
- Câu có số: `{{ _('Page {page} of {pages}', page=2, pages=5) }}` → "Page 2 of 5" hoặc "第 2 頁，共 5 頁".
  Thứ tự các phần trong câu tiếng Trung khác tiếng Anh, nên phải dùng chỗ trống `{...}` chứ không ghép chuỗi.
- Ngày giờ: `month_label` ("November 2026" / "2026年11月"), `weekday_long` ("Monday" / "星期一"),
  `weekday_short` ("Mon" / "週一"), `format_minutes` ("1h 30m" / "1小時30分").
- Thông báo flash được lưu bằng tiếng Anh và dịch lúc hiển thị.
- **Lỗi của API** (ví dụ "title and date are required") được dịch trong `translate_api_errors` (after_request của Flask)
  trước khi gửi về trình duyệt. Lỗi có số dùng mẫu (regex): "title is required (at most 200 characters)" → "標題必須填寫（最多 200 個字）".
- **JavaScript** không tự dịch: base.html gửi xuống `window.I18N` (các câu JS cần, đã dịch sẵn bằng Python), JS chỉ tra bằng hàm `t()`.
  Khung chi tiết trên bản đồ do API trả về câu đã dịch và điền số sẵn.

## 3. Chọn ngôn ngữ (detect_lang)
1. Cookie `lang` hợp lệ ("en" hoặc "zh-TW") → dùng luôn.
2. Chưa có cookie → đọc header `Accept-Language` của trình duyệt, xếp theo độ ưu tiên `q`: gặp `zh...` trước → zh-TW, gặp `en...` trước → en.
3. Không có gì → tiếng Anh.

## 4. Route /settings
- `POST /settings` với `lang` và/hoặc `theme` → đặt cookie (1 năm, `HttpOnly`, `SameSite=Lax`) rồi quay lại trang cũ.
- Cần CSRF token như mọi POST; giá trị lạ bị bỏ qua; `next` đi qua `safe_next()` nên không thể chuyển sang trang web khác.

## 5. Chế độ tối (style.css)
- `<html data-theme="light|dark|auto">` do Python đặt từ cookie.
- Mọi màu là biến ở đầu file, viết bằng `light-dark(màu_sáng, màu_tối)`. Trình duyệt chọn màu theo `color-scheme`:
  `light` → màu sáng, `dark` → màu tối, `auto` (`light dark`) → theo cài đặt của máy. Nhờ vậy mỗi màu chỉ viết một lần.
- Mỗi tính năng có bản màu tối riêng (sáng hơn để đủ tương phản trên nền tối); chữ trên nút màu dùng `--on-accent`.
- Bản đồ vẫn dùng nền sáng của OpenFreeMap, nên khung chi tiết trên bản đồ luôn chữ tối.

## 6. Test (tests/test_i18n.py)
- Quét **mọi** `_('...')` trong template: câu nào thiếu bản dịch thì test báo ngay.
- Bản dịch phải giữ đúng các chỗ trống `{...}` và phải có chữ Hán.
- Mọi lỗi thật từ các hàm kiểm tra dữ liệu đều được dịch.
- `detect_lang` với nhiều header khác nhau; `/settings` (cookie, CSRF, giá trị lạ, `next` nguy hiểm); các trang hiện tiếng Trung;
  lỗi API và flash được dịch; mặc định là tiếng Anh.

## 7. Câu TA có thể hỏi
- **Sao không dùng thư viện Flask-Babel?** Quy tắc nhóm là không thêm package khi chưa hỏi; dict Python đủ cho hai ngôn ngữ
  và dễ giải thích. Babel phù hợp khi có nhiều ngôn ngữ và người dịch riêng.
- **Sao lưu bằng cookie mà không lưu vào database?** Người chưa đăng nhập cũng chọn được ngôn ngữ, và không cần thêm bảng.
- **`light-dark()` là gì?** Hàm CSS chọn một trong hai màu theo `color-scheme`; các trình duyệt chính đều hỗ trợ từ 2024.

## 8. Hạn chế
- Tên địa điểm, tên đơn vị, tiêu đề thông báo lấy từ nguồn dữ liệu nên giữ nguyên ngôn ngữ gốc.
- Ô chọn ngày giờ (`<input type="date">`) hiện theo ngôn ngữ của trình duyệt, không theo nút đổi ngôn ngữ.
- Bản đồ chưa có kiểu tối.
