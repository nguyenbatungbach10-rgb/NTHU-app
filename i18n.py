"""Đa ngôn ngữ: tiếng Anh (gốc) và tiếng Trung phồn thể (Đài Loan). Thuần Python, không có Flask.

Cách dùng trong template:  {{ _('Calendar') }}   ->  "Calendar" hoặc "行事曆"
                           {{ _('Page {page} of {pages}', page=2, pages=5) }}
Khóa của bản dịch chính là câu tiếng Anh, nên khi thiếu bản dịch trang vẫn hiện tiếng Anh (không bao giờ hỏng).

Các hàm chính:
    detect_lang()     -> chọn ngôn ngữ từ cookie, nếu chưa có thì theo cài đặt trình duyệt (Accept-Language)
    normalize_theme() -> "light" / "dark" / "auto" (theo hệ thống)
    translate()       -> dịch một câu và điền các chỗ {..}
    translate_error() -> dịch thông báo lỗi của API (có cả mẫu với số, ví dụ "... at most 200 characters")
    month_label(), weekday_long(), weekday_short(), format_minutes() -> ngày giờ theo từng ngôn ngữ
"""
import re

from study_logic import format_minutes as format_minutes_en

LANGUAGES = {"en": "English", "zh-TW": "繁體中文"}
DEFAULT_LANG = "en"
THEMES = ("light", "dark", "auto")
DEFAULT_THEME = "auto"

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ZH_NUM = "一二三四五六日"

ZH = {
    # ---------- chung ----------
    "NTHU Campus Assistant": "清大校園助理",
    "Home": "首頁", "Calendar": "行事曆", "Schedule": "課表", "Announcements": "公告",
    "Credits & GPA": "學分與 GPA", "Study": "讀書計畫", "Campus map": "校園地圖",
    "Switch language": "切換語言", "Light or dark mode": "淺色或深色模式",
    "Log in": "登入", "Sign up": "註冊", "Log out": "登出",
    "Open menu": "開啟選單", "Close menu": "關閉選單", "Menu": "選單", "Main": "主選單",
    "Language": "語言", "Theme": "外觀", "Light": "淺色", "Dark": "深色", "Auto": "跟隨系統",
    "I2P Final Project": "I2P 期末專題",
    "NTHU student project, not an official NTHU site": "清大學生專題，非清大官方網站",
    "Today": "今天", "Title": "標題", "Date": "日期", "Time": "時間", "(optional)": "（選填）",
    "Description": "說明", "Delete": "刪除", "Cancel": "取消", "Save": "儲存", "Edit": "編輯",
    "Add": "新增", "Name": "名稱", "None": "無", "none": "沒有", "Search": "搜尋", "Go": "前往",
    "Overdue": "已逾期", "Map": "地圖",

    # ---------- trang chủ ----------
    "Classes today": "今天的課", "Show {name} on the map": "在地圖上顯示{name}",
    "No classes today.": "今天沒有課。", "Open timetable": "開啟課表",
    "Due today or overdue": "今天截止或已逾期", "Nothing due. Nice.": "沒有待繳的事項，太好了。",
    "Open study planner": "開啟讀書計畫",
    "Your classes, deadlines and grades in one place.": "課表、截止日和成績，一次看清楚。",
    "Plan the week, keep track of what is due, follow your GPA and never miss an NTHU announcement.":
        "安排每週行程、掌握待辦事項、追蹤 GPA，不再錯過任何清大公告。",
    "Create a free account": "免費建立帳號",
    "Events and deadlines by month, or see the whole year at a glance.": "按月查看活動與截止日，或一眼看完整年。",
    "Your weekly class timetable, with a warning when two classes overlap.": "每週課表，兩堂課時間衝突時會提醒你。",
    "See your GPA and credits, and the grades you need to hit your goal.": "查看 GPA 和學分，以及達成目標需要的成績。",
    "Break work into tasks, keep your materials and log study time.": "把工作拆成小任務、整理學習資料、記錄讀書時間。",
    "Find buildings, dorms and food in 2D or 3D, and where today's classes are.":
        "用 2D 或 3D 找大樓、宿舍和美食，也能看到今天上課的地點。",
    "Scholarships, registration and dorm notices, filtered for you.": "獎學金、註冊和宿舍公告，幫你篩選好。",
    "Coming up": "即將到來", "Open calendar": "開啟行事曆",
    "No upcoming events. Add one in the calendar or save a deadline from the announcements.":
        "沒有即將到來的活動。可以在行事曆新增，或從公告儲存截止日。",
    "Latest announcements": "最新公告", "View all": "查看全部",
    "Announcements are unavailable right now. Please try again later.": "目前無法取得公告，請稍後再試。",

    # ---------- tài khoản ----------
    "Email": "電子郵件", "Password": "密碼", "No account yet?": "還沒有帳號？",
    "Create your account": "建立帳號", "(at least 8 characters)": "（至少 8 個字元）",
    "Confirm password": "確認密碼", "Already have an account?": "已經有帳號了？",
    "Welcome! Your account is ready.": "歡迎！你的帳號已建立。",
    "Invalid email or password.": "電子郵件或密碼錯誤。",
    "You have been logged out.": "你已登出。",
    "Please enter a valid email address.": "請輸入有效的電子郵件地址。",
    "Password must be 8 to 128 characters.": "密碼長度必須是 8 到 128 個字元。",
    "Passwords do not match.": "兩次輸入的密碼不一致。",
    "That email is already registered.": "這個電子郵件已經註冊過了。",

    # ---------- thông báo (announcements) ----------
    "This announcement has no date": "這則公告沒有日期", "Save to Calendar": "存到行事曆",
    "Log in to save": "登入後儲存", "Saved": "已儲存",
    "Will be saved on {date} (date found in the title)": "將存在 {date}（日期取自標題）",
    "Campus Announcements": "校園公告", "Showing sample data.": "目前顯示範例資料。",
    "Live data is not available right now. Showing announcements saved on {date}.": "目前無法取得即時資料，顯示 {date} 儲存的公告。",
    "Saved on {date}": "儲存於 {date}",
    "Could not reach the NTHU Data API.": "無法連線到清大資料 API。",
    "The NTHU Data API returned no usable data.": "清大資料 API 沒有回傳可用的資料。",
    "Category": "類別", "All categories": "所有類別", "Office": "單位", "All offices": "所有單位",
    "All languages": "所有語言", "Search keyword...": "搜尋關鍵字…", "Filter": "篩選", "Clear": "清除",
    "{count} of {total} announcements, newest first": "共 {total} 則公告，顯示 {count} 則，最新的在前",
    "Newer": "較新", "Older": "較舊", "Page {page} of {pages}": "第 {page} 頁，共 {pages} 頁",
    "No announcements match your filter.": "沒有符合篩選條件的公告。",
    "Scholarship": "獎學金", "Dorm": "宿舍", "Careers": "職涯", "Registration": "註冊與選課",
    "Events": "活動", "Other": "其他",

    # ---------- lịch ----------
    "Pick another month": "選擇其他月份", "Previous year": "上一年", "Next year": "下一年",
    "See all of {year}": "查看 {year} 全年", "Previous month": "上個月", "Prev": "上個月",
    "Next month": "下個月", "Next": "下個月", "Year view": "年檢視", "Add event": "新增活動",
    "Add event on {date}": "在 {date} 新增活動", "Task due: {title}": "待辦截止：{title}",
    "Open original announcement": "開啟原始公告",
    "{n} event and deadline": "{n} 個活動與截止日", "{n} events and deadlines": "{n} 個活動與截止日",
    "{n} event(s) and deadline(s)": "{n} 個活動與截止日",
    "This year": "今年", "Go to year": "前往年份",

    # ---------- GPA ----------
    "No credits to plan for {when}.": "{when}沒有需要規劃的學分。",
    "Goal reached for {when}: you only need to pass (C- or better).": "{when}：已達成目標，只要及格（C- 以上）即可。",
    "For {when} you need an average of {needed} (about {letter} or better).": "{when}需要平均 {needed}（約 {letter} 以上）。",
    "Not reachable": "無法達成",
    "for {when}: you would need an average of {needed}, above the maximum of 4.30.": "{when}：需要平均 {needed}，超過最高的 4.30。",
    "Add course": "新增課程", "Cumulative GPA": "累計 GPA", "out of 4.30": "滿分 4.30",
    "Credits earned": "已修學分", "{p}% done": "已完成 {p}%", "{n} planned": "計畫中 {n}",
    "Target GPA": "目標 GPA", "default, change it below": "預設值，可在下方修改", "your goal": "你的目標",
    "Credits left": "剩餘學分",
    "about {n} per semester over {s} semesters": "約每學期 {n} 學分，共 {s} 個學期",
    "no semesters left in 4 years": "四年內已無剩餘學期",
    "What do I need?": "我需要多少分？", "your planned courses": "計畫中的課程",
    "all remaining credits": "所有剩餘學分", "My goals": "我的目標", "Credits to graduate": "畢業學分",
    "Save goals": "儲存目標",
    "The 128 credits is only a default. Check your department's graduation requirement and change it.":
        "128 學分只是預設值，請查詢你系上的畢業學分規定並修改。",
    'No courses yet. Press "+ Add course" to add the ones you have taken, or the ones you plan to take (leave the grade empty).':
        "還沒有課程。按「+ 新增課程」加入已修過或打算修的課（打算修的課成績留空）。",
    "Semester {s}": "{s} 學期", "cumulative": "累計", "{n} credits earned": "已修 {n} 學分",
    "Course": "課程", "Credits": "學分", "Grade": "成績", "Planned": "計畫中", "aim": "目標",
    "Course name": "課程名稱", "Semester": "學期", "(e.g. 115-1)": "（例如 115-1）",
    "Not graded yet (planned)": "尚無成績（計畫中）", "P (pass, no GPA)": "P（通過，不計 GPA）",

    # ---------- thời khóa biểu ----------
    "Weekly schedule": "每週課表", "overlaps another class": "與其他課程衝堂", "Add class": "新增課程",
    "Classes": "課程", "each week": "每週", "In class": "上課時數", "per week": "每週",
    "Time clashes": "衝堂", "classes overlap, see red cards": "有課程衝堂，請看紅色卡片",
    "class on {day}": "{day}的課", "classes on {day}": "{day}的課",
    'No classes yet. Press "+ Add class" to add each course once; it will repeat on the same weekday every week.':
        "還沒有課程。按「+ 新增課程」把每門課加入一次，之後每週同一天都會重複。",
    "Add class on {day}, period {period}": "在{day}第 {period} 節新增課程",
    "Outside the usual periods": "不在一般節次內",
    "These classes start or end outside the NTHU periods 1 to d, so they do not fit in the grid.":
        "這些課的時間超出清大第 1 節到第 d 節，所以不會出現在課表格子裡。",
    "Day": "星期", "Room": "教室", "Start": "開始", "End": "結束",

    # ---------- học tập ----------
    'Mark "{title}" as done': "將「{title}」標示為完成", "{done}/{total} steps": "{done}/{total} 個步驟",
    "Step": "步驟", "Study planning": "讀書計畫", "Add task": "新增待辦", "Log study time": "記錄讀書時間",
    "Add subject": "新增科目", "Open tasks": "未完成待辦", "{n} done": "已完成 {n} 項",
    "catch up when you can": "有空時趕快補上", "nothing late": "沒有逾期",
    "Studied this week": "本週讀書時間", "on {n} day": "共 {n} 天", "on {n} days": "共 {n} 天",
    "Studied today": "今天讀書時間", "Tasks": "待辦事項",
    'No tasks yet. Press "+ Add task", then use "+ Step" to break a big task into small steps.':
        "還沒有待辦事項。按「+ 新增待辦」，再用「+ 步驟」把大任務拆成小步驟。",
    "Subjects & materials": "科目與資料", "{t} this week": "本週 {t}",
    "No subjects yet. Add one to keep its links and notes together.": "還沒有科目。新增一個科目，把相關連結和筆記放在一起。",
    "Study time": "讀書時間", "This week by subject": "本週各科時間", "Recent sessions": "最近的讀書紀錄",
    "Subject": "科目", "Note": "備註", "No subject": "未指定科目",
    'No study time logged yet. Press "+ Log study time" after a session.': "還沒有讀書紀錄。讀完書後按「+ 記錄讀書時間」。",
    "Due date": "截止日", "Materials & notes": "資料與筆記", "(links, books)": "（連結、書籍）", "Minutes": "分鐘",

    # ---------- bản đồ ----------
    "Map view": "地圖檢視", "Search places": "搜尋地點", "Name or room, e.g. Delta 205": "名稱或教室，例如 台達 205",
    "Show on map": "顯示在地圖上", "Today's classes": "今天的課", "{room}: building not found": "{room}：找不到大樓",
    "no room set": "未填教室", "Results": "搜尋結果", "Places": "地點",
    'No place matches "{q}".': "找不到符合「{q}」的地點。",
    "Search above, or click a dot on the map. {n} places on campus.": "在上方搜尋，或點地圖上的圓點。校園內共有 {n} 個地點。",
    "Map of the NTHU campus": "清大校園地圖",
    "The map could not load. It needs an internet connection and a browser with WebGL. Search and place details still work.":
        "地圖無法載入，需要網路連線和支援 WebGL 的瀏覽器。搜尋和地點資訊仍可使用。",
    "Place data": "地點資料", "Map tiles": "地圖圖磚",
    "Building heights in 3D come from OpenStreetMap; many are estimates. Walking times are straight-line estimates.":
        "3D 建築高度來自 OpenStreetMap，很多是估計值。步行時間以直線距離估算。",
    "Buildings": "建築", "Dorms & lodging": "宿舍與住宿", "Food & drink": "餐飲", "Shops & services": "商店與服務",
    "Bus, bikes & parking": "公車、單車與停車", "Sports": "運動", "Lakes, gardens & landmarks": "湖泊、庭園與地標",
    "Gates": "校門", "Main campus": "校本部", "Nanda campus": "南大校區",
    "{label}: {name}, {meters} m (about {minutes} min walk)": "{label}：{name}，{meters} 公尺（步行約 {minutes} 分鐘）",
    "Walking directions in Google Maps": "用 Google 地圖查看步行路線", "{n} floors": "{n} 層樓",
    "Type a name to search.": "輸入名稱開始搜尋。",

    # ---------- chữ trong JavaScript ----------
    "Try again": "再試一次", "Request failed": "請求失敗",
    "Edit event": "編輯活動", "Delete this event?": "要刪除這個活動嗎？",
    "Edit course": "編輯課程", "Delete this course?": "要刪除這門課嗎？",
    "Edit task": "編輯待辦", "Delete this task?": "要刪除這個待辦嗎？", "Add step": "新增步驟",
    "Edit subject": "編輯科目", "Delete this subject?": "要刪除這個科目嗎？",
    "Add session": "記錄讀書時間", "Edit session": "編輯讀書紀錄", "Delete this session?": "要刪除這筆讀書紀錄嗎？",
    "Edit class": "編輯課程", "Delete this class?": "要刪除這堂課嗎？",
}

# Chữ mà static/app.js và static/map.js cần (gửi xuống trình duyệt qua window.I18N)
JS_KEYS = [
    "Saved", "Try again", "Request failed", "Add event", "Edit event", "Delete this event?",
    "Add course", "Edit course", "Delete this course?", "Add task", "Edit task", "Delete this task?", "Add step",
    "Add subject", "Edit subject", "Delete this subject?", "Add session", "Edit session", "Delete this session?",
    "Add class", "Edit class", "Delete this class?", 'No place matches "{q}".', "Type a name to search.",
    "Results", "Places",
]

# ---------- lỗi của API ----------
ERRORS = {
    "JSON body must be an object": "資料格式錯誤（需要 JSON 物件）",
    "Invalid or missing CSRF token": "安全驗證失敗，請重新整理頁面再試一次",
    "login required": "請先登入",
    "a subtask cannot have its own subtasks": "步驟不能再有自己的步驟",
    "class not found": "找不到這堂課", "course not found": "找不到這門課", "event not found": "找不到這個活動",
    "place not found": "找不到這個地點", "session not found": "找不到這筆讀書紀錄",
    "subject not found": "找不到這個科目", "task not found": "找不到這個待辦", "parent task not found": "找不到上層待辦",
    "date must be a real date like 2026-11-20": "日期必須是真實的日期，例如 2026-11-20",
    "date must be in YYYY-MM-DD format": "日期格式必須是 YYYY-MM-DD",
    "due_date must be empty or a real date like 2026-11-20": "截止日必須留空或是真實的日期，例如 2026-11-20",
    "done must be true or false": "完成狀態必須是 true 或 false",
    "end must be later than start": "結束時間必須晚於開始時間",
    "month must be in YYYY-MM format": "月份格式必須是 YYYY-MM",
    "name, credits and semester are required": "課程名稱、學分和學期都必須填寫",
    "semester must look like 115-1 (academic year, then 1, 2 or 3)": "學期格式必須像 115-1（學年，再加 1、2 或 3）",
    "source_url must be a short text": "來源網址太長",
    "source_url must start with http:// or https://": "來源網址必須以 http:// 或 https:// 開頭",
    "start and end must be times like 10:10": "開始和結束必須是時間，例如 10:10",
    "subject_id and parent_id must be positive whole numbers or empty": "科目和上層待辦的編號必須是正整數或留空",
    "subject_id must be a positive whole number or empty": "科目編號必須是正整數或留空",
    "time must be in HH:MM format": "時間格式必須是 HH:MM",
    "title and date are required": "標題和日期都必須填寫",
    "weekday must be a whole number from 0 (Monday) to 6 (Sunday)": "星期必須是 0（星期一）到 6（星期日）的整數",
}
FIELDS = {"title": "標題", "name": "名稱", "note": "備註", "notes": "筆記", "room": "教室", "description": "說明",
          "minutes": "分鐘數", "credits": "學分", "credits_required": "畢業學分", "target_gpa": "目標 GPA"}
# Lỗi có số bên trong (giới hạn độ dài, khoảng giá trị): dịch theo mẫu
ERROR_PATTERNS = [
    (re.compile(r"^(\w+) is required \(at most (\d+) characters\)$"), "{field}必須填寫（最多 {0} 個字）"),
    (re.compile(r"^(\w+) must be at most (\d+) characters$"), "{field}最多 {0} 個字"),
    (re.compile(r"^(\w+) must be text of at most (\d+) characters$"), "{field}最多 {0} 個字"),
    (re.compile(r"^(\w+) must be a whole number from (\d+) to (\d+)$"), "{field}必須是 {0} 到 {1} 的整數"),
    (re.compile(r"^(\w+) must be a number from ([\d.]+) to ([\d.]+)$"), "{field}必須是 {0} 到 {1} 的數字"),
    (re.compile(r"^grade must be empty \(planned\), P, or one of (.+)$"), "成績必須留空（計畫中）、P，或以下其中之一：{0}"),
]


# ---------- chọn ngôn ngữ / giao diện ----------

def _accept_tags(header):
    """"zh-TW,zh;q=0.9,en;q=0.8" -> ["zh-TW", "zh", "en"] (q cao trước)."""
    tags = []
    for i, part in enumerate((header or "").split(",")):
        pieces = part.strip().split(";")
        tag, q = pieces[0].strip(), 1.0
        for p in pieces[1:]:
            if p.strip().startswith("q="):
                try:
                    q = float(p.strip()[2:])
                except ValueError:
                    q = 0.0
        if tag:
            tags.append((-q, i, tag))
    return [tag for _, _, tag in sorted(tags)]


def detect_lang(cookie=None, accept_header=""):
    """Ngôn ngữ của trang: cookie hợp lệ trước; chưa có thì theo trình duyệt (zh-* -> zh-TW); mặc định tiếng Anh."""
    if cookie in LANGUAGES:
        return cookie
    for tag in _accept_tags(accept_header):
        tag = tag.lower()
        if tag.startswith("zh"):
            return "zh-TW"
        if tag.startswith("en"):
            return "en"
    return DEFAULT_LANG


def normalize_theme(value):
    """Chỉ nhận light / dark / auto; giá trị lạ -> auto."""
    return value if value in THEMES else DEFAULT_THEME


# ---------- dịch ----------

def translate(text, lang, **values):
    """Dịch `text` sang `lang` rồi điền các chỗ {tên}. Thiếu bản dịch thì giữ tiếng Anh."""
    if not isinstance(text, str):
        return text
    template = ZH.get(text, text) if lang == "zh-TW" else text
    return template.format(**values) if values else template


def translate_error(message, lang):
    """Dịch thông báo lỗi của API (bảng ERRORS, rồi đến các mẫu có số)."""
    if lang != "zh-TW" or not isinstance(message, str):
        return message
    if message in ERRORS:
        return ERRORS[message]
    for pattern, template in ERROR_PATTERNS:
        match = pattern.match(message)
        if match:
            groups = match.groups()
            if template.startswith("{field}"):
                return template.format(*groups[1:], field=FIELDS.get(groups[0], groups[0]))
            return template.format(*groups)
    return ZH.get(message, message)


def js_strings(lang):
    """Các chữ JavaScript cần, đã dịch. Tiếng Anh -> {} (JS dùng luôn chữ gốc)."""
    return {key: ZH[key] for key in JS_KEYS if key in ZH} if lang == "zh-TW" else {}


# ---------- ngày giờ ----------

def month_label(year, month, lang):
    """"November 2026" hoặc "2026年11月"."""
    return f"{year}年{month}月" if lang == "zh-TW" else f"{MONTHS_EN[month - 1]} {year}"


def month_long(month, lang):
    """"January" hoặc "1月"."""
    return f"{month}月" if lang == "zh-TW" else MONTHS_EN[month - 1]


def month_short(month, lang):
    """"Jan" hoặc "1月"."""
    return f"{month}月" if lang == "zh-TW" else MONTHS_EN[month - 1][:3]


def weekday_long(index, lang):
    """0 -> "Monday" hoặc "星期一"."""
    return f"星期{ZH_NUM[index]}" if lang == "zh-TW" else WEEKDAYS_EN[index]


def weekday_short(lang):
    """["Mon", ...] hoặc ["週一", ...]."""
    return [f"週{c}" for c in ZH_NUM] if lang == "zh-TW" else [d[:3] for d in WEEKDAYS_EN]


def weekday_initials(lang):
    """["M", "T", ...] hoặc ["一", "二", ...] cho lịch nhỏ."""
    return list(ZH_NUM) if lang == "zh-TW" else [d[0] for d in WEEKDAYS_EN]


def format_minutes(minutes, lang):
    """90 -> "1h 30m" hoặc "1小時30分"."""
    if lang != "zh-TW":
        return format_minutes_en(minutes)
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours}小時{rest}分"
    return f"{hours}小時" if hours else f"{rest}分"
