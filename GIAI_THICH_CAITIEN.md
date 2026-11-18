# Giải thích: các bản sửa lỗi và cải tiến sau buổi review (18/11/2026)

File này giải thích từng thay đổi sau khi review trang web thật. Mỗi phần nói: lỗi/thiếu sót là gì,
sửa ở file nào, và code chạy ra sao. Logic đều nằm trong Python; template chỉ hiển thị.

---

## 1. Ngày giả và thông báo trùng lặp (`nthu_api.py`)

**Lỗi:** API đôi khi trả `date` không phải ngày thật (chuỗi rỗng, chữ...). Một số thông báo xuất hiện 2 lần.

**Sửa:**
- `DATE_RE` + `clean_date(value)`: chỉ nhận ngày dạng `YYYY-MM-DD` (cũng nhận `YYYY/MM/DD`, `YYYY.MM.DD`,
  rồi đổi về `YYYY-MM-DD`) và kiểm tra bằng `date.fromisoformat` để loại ngày vô lý như `2026-13-40`.
  Sai thì trả `""` (không có ngày).
- `normalize()` giữ một tập `seen` các khóa `(office, title, date)`. Gặp khóa đã có thì bỏ qua.

## 2. Lưu thông báo không có ngày đăng (`calendar_logic.mark_saved`)

**Lỗi:** thông báo không có ngày đăng nhưng tiêu đề có ngày (ví dụ "截止日 11月30日") vẫn bị khóa nút Save.

**Sửa:** `mark_saved()` đọc ngày trong tiêu đề, lấy **hôm nay** làm mốc để đoán năm. Nếu tìm được
thì `event_date` là ngày đó; không có thì `event_date = ""` và nút bị khóa (có chú thích).
Macro `_macros.html` dùng `save_date = item.event_date or item.date`.

## 3. Giờ Đài Loan (`calendar_logic.today_tw`)

**Lỗi:** server PythonAnywhere chạy giờ UTC, chậm 8 tiếng so với Đài Loan. Từ 0h đến 8h sáng,
"hôm nay" trên web vẫn là ngày hôm qua.

**Sửa:** `TAIWAN_TZ = timezone(timedelta(hours=8))` và `today_tw()` trả ngày hiện tại ở Đài Loan.
Mọi chỗ trong `app.py` trước đây dùng `date.today()` giờ dùng `today_tw()`.

## 4. Trang lỗi 404/500 và favicon (`app.py`, `templates/error.html`)

- `error_page(code)`: với đường dẫn `/api/...` trả JSON `{"error": "not found"}`, còn lại thì
  hiện trang `error.html` đẹp, đã dịch, có nút về trang chủ.
- `@app.errorhandler(404)` và `@app.errorhandler(500)` gọi hàm này.
- `/favicon.ico` chuyển hướng (301) tới `static/favicon.svg`, nên trình duyệt không báo lỗi 404 nữa.

## 5. Phân loại thông báo tốt hơn (`nthu_api.CATEGORY_KEYWORDS`)

**Lỗi:** quá nhiều thông báo rơi vào "Other".

**Sửa:**
- Thêm 3 nhóm: **Admissions** (招生入學), **Exchange** (交換與出國), **Campus notices** (校園事務).
- Thứ tự kiểm tra có ý nghĩa: nhóm cụ thể (Scholarship, Dorm...) đứng trước nhóm chung (Events).
- Từ khóa tiếng Anh khớp **nguyên từ** (`_keyword_pattern` dùng `\b`) để "award" không khớp nhầm trong
  "awarded..." của một từ khác, hay "fee" không khớp "feedback". Từ khóa tiếng Trung khớp theo chuỗi con.

## 6. Hạn chót và sự kiện (`nthu_api.upcoming_dates`)

Trang Announcements có 3 tab: **All announcements**, **Deadlines** (hạn chót) và **Talks & events**
(buổi nói chuyện, hội thảo). Cả hai tab sau chỉ lấy thông báo có ngày ghi trong tiêu đề, trong 60 ngày tới,
gần nhất trước. Trang chủ có khối **Upcoming events**: các buổi nói chuyện / hội thảo / hoạt động trong 14 ngày tới
(hằng số `HOME_EVENT_DAYS` trong `app.py`); hạn chót thì xem ở tab Deadlines.

- `upcoming_dates(items, today, days, kind)` trả về **bản sao** của từng thông báo, thêm `due` (ngày),
  `days_left` (còn bao nhiêu ngày) và `is_deadline`.
- `is_deadline` = tiêu đề có chữ báo hạn chót: 截止, 期限, 日止 ("至11月20日止" = đến hết 20/11), deadline, due...
  Không có các chữ đó thì ngày trong tiêu đề chỉ là **ngày diễn ra** (ví dụ "(專題演講)115.11.19..." là ngày
  có buổi nói chuyện, không phải hạn nộp gì cả). Bản đầu tiên gộp chung hai loại dưới tên "deadlines" nên gây nhầm.
- `kind="deadline"` chỉ lấy hạn chót, `kind="event"` chỉ lấy sự kiện, `None` lấy cả hai.
  `app.py` nối tham số `?view=` với loại này qua `ANNOUNCEMENT_VIEWS`.
- Thẻ hiện "Deadline: 2026-11-20 · tomorrow" (tô đỏ nếu còn ≤ 7 ngày) hoặc "Takes place: 2026-11-19 · today".
  Ngày bên phải ghi "Posted ..." để không nhầm ngày đăng với ngày hạn.
- Ngày đọc từ tiêu đề được nhớ lại trong `_dates_memo` để không phải đọc lại 4.500 tiêu đề mỗi lần mở trang.

## 7. Gom đơn vị (`nthu_api.office_group`, `group_offices`)

Có hơn 100 đơn vị nên ô chọn quá dài. `office_group("教務處註冊組")` cắt sau chữ 處/院/室/中心 đầu tiên
→ `"教務處"`. Ô chọn dùng `<optgroup>` theo đơn vị lớn, có thêm lựa chọn "All of 教務處".
Giá trị lọc của lựa chọn đó là `"group:教務處"` (`GROUP_PREFIX`); `filter_announcements` hiểu tiền tố này.

## 8. Hướng dẫn người mới (`home_logic.onboarding`)

Người mới đăng ký thấy trang chủ trống, nên có một **dòng nhỏ** "Get started" với 4 nút (thêm lớp, đặt mục tiêu GPA,
lưu một hạn chót, thêm việc học). Nó chỉ là gợi ý, nên làm gọn một dòng chứ không chiếm cả khối.
`db.user_counts(user_id)` đếm số dòng của người dùng trong từng bảng; `onboarding(counts, hidden)` đánh dấu bước nào đã xong.
Dòng này tự ẩn khi xong cả 4 bước, hoặc khi bấm **Hide** (POST `/onboarding/hide` lưu cookie `onboarding=hidden` 1 năm).

## 9. Gợi ý tên môn (`home_logic.name_suggestions`)

Ô "tên môn" ở trang GPA và Study có `<datalist>`: gợi ý các tên đã dùng ở thời khóa biểu, GPA, Study,
bỏ trùng (không phân biệt hoa thường), tối đa 50 tên. Gõ ít hơn, tên thống nhất hơn.

## 10. Chặn đoán mật khẩu (`login_guard.py`, `db.py`)

**Thiếu sót:** trước đây ai cũng có thể thử mật khẩu không giới hạn.

**Cách làm:**
1. Đăng nhập sai → `db.add_login_failure(email, ip, now, ...)` ghi vào bảng `login_failures`
   (và xóa luôn các bản ghi quá 15 phút để bảng không phình to).
2. Trước khi kiểm tra mật khẩu, `db.login_failure_times()` lấy các lần sai trong 15 phút, rồi
   `login_guard.lockout_minutes()` quyết định:
   - **5 lần sai** cho cùng email từ cùng IP → khóa.
   - **20 lần sai** từ một IP với bất kỳ email nào → khóa (chặn thử lần lượt nhiều tài khoản).
3. Bị khóa → trả mã **429 Too Many Requests**, hiện "Try again in N minutes" (đã dịch), và
   **không kiểm tra mật khẩu** (kể cả mật khẩu đúng).
4. Đăng nhập đúng → `db.clear_login_failures()` xóa các lần sai.

**Vì sao đếm theo email + IP mà không chỉ theo email?** Nếu chỉ theo email, kẻ xấu có thể cố tình nhập
sai 5 lần để khóa tài khoản của bạn. Đếm theo cả IP thì bạn đăng nhập từ máy khác vẫn được.

**Số phút chờ tính thế nào?** Sắp xếp các lần sai; khi lần sai thứ (số lần − giới hạn + 1) tính từ cũ nhất
hết hạn 15 phút thì số lần sai tụt dưới giới hạn. Làm tròn lên, ít nhất 1 phút.

## 11. Cookie an toàn trên server thật (`app.py`)

Đặt biến môi trường `PRODUCTION=1` (trong file WSGI của PythonAnywhere). Khi đó:
- `SESSION_COOKIE_SECURE = True` và cookie `lang`/`theme` cũng có cờ `Secure`: trình duyệt chỉ gửi
  cookie qua HTTPS, nên người nghe lén mạng Wi-Fi không lấy được phiên đăng nhập.
- `ProxyFix` đọc IP thật của người dùng từ header `X-Forwarded-For` do proxy của PythonAnywhere gắn vào.
  Nếu không có, mọi người dùng đều có cùng IP của proxy và bị khóa chung.
- Chạy `python app.py` trên máy mình thì **không** bật, vì không có HTTPS và không có proxy
  (bật ProxyFix khi không có proxy thì người dùng tự gửi header giả IP được).

## 12. Danh sách gọn kiểu "lịch hẹn" (`templates/_macros.html`, `.agenda` trong `style.css`)

Trước đây mỗi thông báo là một thẻ to riêng (đơn vị + nhãn + ngày đăng + tiêu đề tím đậm + dòng "Date:"),
nên 5 mục đã chiếm hết màn hình. Giờ trang chủ và 2 tab Deadlines / Talks & events dùng **một khung chung**,
các dòng ngăn bằng đường kẻ mảnh:

```
[20 ]  Tiêu đề (tối đa 2 dòng, cắt bằng "...")        tomorrow  [Save to Calendar]
[Nov]  人事室
```

- `date_tile(iso, urgent)`: ô ngày, số ngày to + tháng nhỏ (`month_short` đã dịch "Nov" / "11月").
  Hạn chót còn ≤ 3 ngày thì ô và chữ "tomorrow" chuyển màu đỏ.
- `dated_row(item)`: một hạn chót/sự kiện (kết quả của `upcoming_dates`). Có một dòng chữ ẩn (`sr-only`)
  "Deadline: 2026-11-20" cho trình đọc màn hình, vì ô ngày chỉ là hình.
- `event_row(ev)`: sự kiện trong Calendar của bạn (khối "Coming up").
- `brief_row(item)`: thông báo mới, chỉ tiêu đề + đơn vị + ngày đăng.
- `save_button(...)`: nút "Save to Calendar" tách ra một macro để thẻ lớn và dòng gọn dùng chung, không viết lặp.
- Trên điện thoại (`@media (max-width: 560px)`) ô ngày nhỏ lại và phần "tomorrow"/nút xuống dưới tiêu đề.
- Tab "All announcements" vẫn dùng thẻ lớn vì ở đó cần thấy nhãn loại (Scholarship, Dorm...).

## 13. Thông báo tự cập nhật mỗi ngày (GitHub Actions + API của PythonAnywhere)

**Vấn đề:** server PythonAnywhere (gói miễn phí) không gọi được api.nthusa.tw, nên web dùng bản lưu.
Nếu không ai cập nhật bản lưu, sau vài tuần "Upcoming events" sẽ trống. Tài khoản miễn phí tạo sau 15/01/2026
cũng không có "scheduled task" để tự chạy việc gì đó mỗi ngày trên PythonAnywhere.

**Cách làm:** để **máy của GitHub** làm việc đó.

```
GitHub Actions (06:17 và 14:17 giờ Đài Loan)
  1. tools/save_announcements.py --output snapshot.json    tải thông báo từ api.nthusa.tw
  2. tools/upload_snapshot.py snapshot.json                gửi file lên PythonAnywhere bằng API
          -> /home/nthuapp/NTHU-app/instance/announcements_snapshot.json
Web (nthu_api.load_snapshot)
  đọc cả data/announcements_snapshot.json và instance/announcements_snapshot.json, lấy bản MỚI HƠN (so saved_at)
```

- `.github/workflows/update-announcements.yml`: lịch chạy (`cron` tính theo giờ UTC) và nút chạy tay (`workflow_dispatch`).
- `tools/upload_snapshot.py`: POST file tới `https://www.pythonanywhere.com/api/v0/user/<tên>/files/path<đường dẫn>`
  với header `Authorization: Token <API token>`. Trả mã 0 nếu thành công (HTTP 200/201), 1 nếu lỗi.
- Token nằm trong **GitHub Secrets** (`PA_USERNAME`, `PA_TOKEN`), không nằm trong code, không bao giờ in ra log.
- File được ghi vào `instance/` vì thư mục này **không có trong git** (`.gitignore`): `git pull` trên PythonAnywhere
  không bao giờ bị lỗi "local changes would be overwritten".
- Web đọc lại bản lưu mỗi 5 phút (`CACHE_SECONDS`), nên không cần bấm Reload.
- `save_announcements.py` ghi giờ lưu theo **giờ Đài Loan** (`TAIWAN_TZ`), vì máy của GitHub chạy giờ UTC.

**Lưu ý:** với repo công khai, GitHub tự tắt lịch chạy nếu repo không có commit nào trong 60 ngày.
Khi đó vào tab Actions bấm bật lại (Enable workflow).

## 14. Dòng "Updated" thay cho khung cảnh báo vàng (`nthu_api.is_stale`)

Từ khi GitHub tự cập nhật mỗi ngày, bản lưu thường chỉ cũ vài tiếng, nên khung vàng "Live data is not available"
làm người dùng tưởng web lỗi. Giờ:
- Bản lưu cũ **dưới 48 giờ** (`STALE_HOURS`): chỉ một dòng chữ xám "Updated 2026-11-19 06:17".
- Cũ **hơn 48 giờ**: hiện lại khung vàng (nghĩa là việc tự cập nhật bị hỏng, cần xem tab Actions trên GitHub).
- `is_stale(saved_at, now)` đọc chuỗi "YYYY-MM-DD HH:MM" bằng `datetime.strptime`; đọc không được thì coi là cũ.
- `app.notice_is_stale()` gọi hàm này với giờ Đài Loan rồi truyền `stale` cho template.

## 15. Header bảo mật (`app.add_security_headers`)

`@app.after_request` gắn vào **mọi** câu trả lời:

| Header | Tác dụng |
|---|---|
| `X-Frame-Options: DENY` và `Content-Security-Policy: frame-ancestors 'none'` | Trang lạ không nhúng được web mình vào `<iframe>` → chống **clickjacking** (nhúng ẩn web mình rồi lừa người dùng bấm "Delete my account") |
| `X-Content-Type-Options: nosniff` | Trình duyệt không tự "đoán" loại file, không chạy nhầm một file thường như script |
| `Referrer-Policy: strict-origin-when-cross-origin` | Bấm link sang trang khác chỉ gửi tên miền, không gửi cả đường dẫn (có thể chứa từ khóa tìm kiếm) |
| `Strict-Transport-Security` (chỉ khi `PRODUCTION=1` và đang dùng HTTPS) | Trình duyệt nhớ 1 năm: luôn vào web bằng HTTPS |

Dùng `setdefault` để không ghi đè nếu một route đã tự đặt header đó.

## 16. "Remember me" (`account_logic.REMEMBER_DAYS`, `app.start_session`)

- Mặc định phiên đăng nhập là cookie **không có ngày hết hạn**: trình duyệt xóa khi đóng → phải đăng nhập lại.
- Tích ô "Keep me logged in for 30 days" → `session.permanent = True`; Flask đặt ngày hết hạn
  `PERMANENT_SESSION_LIFETIME` = 30 ngày và **gia hạn mỗi lần mở web**.
- Có ở cả trang Log in và Sign up. Chữ nhỏ nhắc không tích trên máy dùng chung.

## 17. Trang Account: đổi mật khẩu, xóa tài khoản (`/account`, `account_logic.py`)

- Link: bấm vào email của bạn trong menu.
- **Đổi mật khẩu** (`POST /account/password`): phải nhập **mật khẩu hiện tại** (người mượn máy đang mở sẵn web
  cũng không đổi được), mật khẩu mới theo cùng luật với Sign up (`password_error`, 8–128 ký tự, nhập lại phải khớp).
- **Đổi xong thì các máy khác bị đăng xuất**: khi đăng nhập, phiên lưu `auth` = 16 ký tự HMAC của bản băm mật khẩu
  (`auth_tag`). Mỗi request, `load_user_and_check_csrf` so dấu này với mật khẩu hiện tại; đổi mật khẩu → dấu khác →
  phiên cũ bị xóa. Máy vừa đổi được cấp dấu mới nên vẫn đăng nhập.
  Vì sao không lưu thẳng bản băm? Cookie phiên của Flask được **ký** (không sửa được) nhưng **không mã hóa**
  (ai cầm cookie cũng đọc được), nên chỉ lưu một dấu không đoán ngược được.
- **Xóa tài khoản** (`POST /account/delete`): cần mật khẩu + tích ô xác nhận. `db.delete_user` chỉ xóa dòng trong
  `users`; các bảng khác có `ON DELETE CASCADE` nên sự kiện, lớp học, môn, việc học... của bạn bị xóa theo,
  dữ liệu người khác không bị đụng (có test kiểm tra).
- Template không bao giờ thấy bản băm mật khẩu: `g.password_hash` tách riêng khỏi `g.user`.
- Lần đầu cập nhật bản này lên server, mọi người đang đăng nhập sẽ bị đăng xuất một lần (phiên cũ chưa có dấu `auth`).

---

## Câu hỏi TA có thể hỏi

1. **Sao trả mã 429 mà không phải 401?** 401 = sai thông tin đăng nhập; 429 = gửi quá nhiều yêu cầu.
   Mã đúng giúp trình duyệt/công cụ hiểu chuyện gì xảy ra.
2. **Sao lưu thời gian dạng số giây (`time.time()`)?** So sánh và trừ số rất đơn giản; cửa sổ 15 phút
   chỉ là `now - 900`.
3. **Test thế nào khi phải chờ 15 phút?** Trong test, `monkeypatch` thay `time.time` bằng một hàm trả về
   thời điểm 15 phút sau (`tests/test_login_guard.py`).
4. **Sao "hôm nay" không dùng `date.today()`?** Vì đó là ngày của máy server (UTC), không phải Đài Loan.
7. **Clickjacking là gì, chặn thế nào?** Trang lạ nhúng web mình vào khung trong suốt đặt đè lên nút của nó,
   người dùng tưởng bấm nút kia nhưng thật ra bấm "Delete" của mình. Header `X-Frame-Options: DENY` cấm nhúng.
8. **Đổi mật khẩu sao máy khác bị đăng xuất, khi session nằm trong cookie?** Mỗi request đều so dấu `auth` trong
   phiên với mật khẩu hiện tại trong database (xem mục 17).
6. **Sao không để server tự gọi API?** Gói miễn phí chặn api.nthusa.tw. Máy của GitHub thì gọi được, nên
   GitHub tải về rồi gửi file sang; web chỉ việc đọc file.
5. **Macro trong Jinja là gì?** Giống hàm Python: định nghĩa một lần (`{% macro dated_row(item) %}`),
   gọi nhiều lần (`{{ dated_row(item) }}`), để HTML của mỗi dòng chỉ viết ở một chỗ.
