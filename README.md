# THREADS AUTO POST TOOL (BOT ĐĂNG BÀI TỰ ĐỘNG LÊN THREADS)

Tool tự động hóa việc đăng bài tuyển dụng/marketing lên nền tảng Threads (Meta). Hoạt động hoàn toàn tự động thông qua cấu hình trên Google Sheet, hỗ trợ tự động bẻ khóa 2FA, lưu Cookie siêu nhẹ và chạy ngầm định kỳ trên GitHub Actions.

## Tính Năng Nổi Bật

- **Quản lý tập trung trên Google Sheet:** Đọc nội dung, link ảnh, thời gian đăng trực tiếp từ Google Sheet.
- **Đăng Bài Kép (Post + Reply):** Hỗ trợ tách nội dung làm bài đăng chính (Job Content) và bình luận phụ (Thread Content) để vượt giới hạn 500 ký tự của Threads.
- **Tự Động Đăng Nhập & Vượt 2FA:** Tích hợp `pyotp` để tự động sinh mã xác thực 6 số (Authenticator) giúp Bot vượt qua các chốt chặn bảo mật của Meta một cách dễ dàng.
- **Quản Lý Phiên (Cookie):** Tự động lưu và sử dụng file `storage_state.json` (Cookie) siêu nhẹ để giữ trạng thái đăng nhập, tránh bị Meta nghi ngờ spam.
- **Anti-Spam Cơ Bản:** Gõ phím với tốc độ ngẫu nhiên như người thật, tự động tắt popup quảng cáo/thông báo, khoảng nghỉ ngẫu nhiên giữa các bài đăng.
- **Hỗ Trợ Đám Mây (Cloud Ready):** Tối ưu 100% để chạy ngầm (Headless) trên GitHub Actions với múi giờ Việt Nam.

---

## Yêu Cầu Hệ Thống

1. **Python:** Phiên bản 3.10 trở lên.
2. **Trình duyệt:** Cài đặt Playwright Chromium.
3. **Google Cloud Console:** File `credentials.json` (Service Account) đã cấp quyền truy cập Google Sheets API và Google Drive API.

---

## Hướng Dẫn Cài Đặt Ban Đầu (Local)

- **Bước 1: Cài đặt thư viện Python**

Mở Terminal/CMD tại thư mục chứa code và chạy lệnh sau:

```bash
pip install -r requirements.txt
playwright install chromium 
```

- **Bước 2: Cấu hình Google Sheet**

1. Tạo một Google Sheet với 2 tab: `Recruitment` và `Accounts`.

2. Share quyền Editor của Sheet cho email của Service Account (trong file `credentials.json`).

3. **Tab Accounts** cần có các cột: `Email`, `Password`, `2FA_Secret`, `AccountsCode`.
(Lưu ý: `2FA_Secret` là đoạn mã Khóa bí mật tĩnh lấy từ phần Cài đặt 2FA của Instagram).

4. **Tab Recruitment** cần có các cột: `Position`, `Job Content`, `Thread Content`, `Topic`, `Image URL`, `Posted`, `Link post`, `Date`, `AccountsCode`.

- **Bước 3: Chạy Tool**

Để xem Bot chạy trực tiếp trên máy, mở file `thread_autopost_tool.py`, đổi `headless=True` thành `headless=False` (ở dòng khởi tạo class `ThreadsBot`). Sau đó chạy lệnh:

```bash
python thread_autopost_tool.py
```

## Hướng Dẫn Triển Khai Lên GitHub Actions (Chạy Tự Động Định Kỳ)

Để Tool tự động chạy hằng ngày mà không cần bật máy tính, hãy đẩy code lên kho lưu trữ Private trên GitHub.

1. **Bảo mật thông tin (GitHub Secrets):**

Vào Repository -> `Settings` -> `Secrets and variables` -> `Actions`.

Thêm biến `GCP_CREDENTIALS` và dán toàn bộ nội dung của file `credentials.json` vào đây.
2. **Cấu hình Luồng (Workflow):**

Đảm bảo trong thư mục code có file `.github/workflows/threads-cron.yml`.

Tool đã được setup chạy vào **9h30 sáng** và **21h30 tối** (Giờ Việt Nam). Có thể tùy chỉnh trong file yml.
3. **Cơ chế hoạt động trên Cloud:**

Lần đầu chạy, do chưa có thư mục `cookies/`, Bot sẽ tự động lấy Email, Password và Khóa 2FA_Secret từ Google Sheet để đăng nhập.

Sau khi đăng nhập lọt vào trang chủ, Bot sẽ tạo ra file `<Mã_Account>.json` siêu nhẹ chứa Cookie.

Bot tiến hành đăng bài chính, thả bình luận phụ và ghi ngày giờ chính xác (Múi giờ Asia/Ho_Chi_Minh) vào Google Sheet.

## Xử Lý Sự Cố (Troubleshooting)

Nếu Tool báo lỗi trên GitHub Actions:

Truy cập tab **Actions** trên GitHub, bấm vào lần chạy bị lỗi.

Cuộn xuống phần **Artifacts**, tải file `error-screenshots.zip` về máy để xem ảnh chụp màn hình lúc trình duyệt ảo bị lỗi, từ đó dễ dàng fix bug do sai mã hay do Meta cập nhật giao diện.

# 🚀 Hướng dẫn setup account & tự động hóa

---

## 📌 Tổng quan

Tài liệu này hướng dẫn toàn bộ quy trình:
- Thêm account vào hệ thống
- Cấu hình 2FA
- Tạo profile đăng nhập
- Trích xuất cookie
- Upload lên GitHub để hệ thống tự động chạy

---

## 🧩 BƯỚC 1: Khai báo thêm vào cột `2FA_Secret` bên Sheet Accounts

Nếu điền thêm account bên sheet **Accounts** thì cần điền thêm vào cột:

```text
2FA_Secret
🔑 Cách lấy 2FA_Secret
Mở Instagram → Vào Cài đặt → Trung tâm tài khoản (Meta Account Center)
Chọn Mật khẩu và bảo mật → Xác thực 2 yếu tố
Chọn tài khoản cần lấy → Chọn phương thức Ứng dụng xác thực (Authenticator App)
2FA_Secret nằm bên dưới mã QR
🔐 BƯỚC 2: Đăng nhập lần đầu để tạo Hồ sơ (Profile)
Down file login.py từ Git về máy
Mở cửa sổ lệnh (Terminal / Command Prompt) tại thư mục chứa file
Gõ dòng lệnh sau và nhấn Enter:
python login.py
Nhập AccountsCode bên sheet Accounts ứng với tài khoản đã thêm và nhấn Enter
Lúc này, một cửa sổ Google Chrome (trình duyệt thật) sẽ tự động bật lên và vào sẵn trang chủ Threads
Đăng nhập tài khoản đã thêm bằng:
Email
Password
Mã xác nhận 6 số
Đăng nhập thành công rồi đóng hẳn trình duyệt Chrome đó lại
Quay lại cửa sổ CMD, nhấn Enter một lần nữa để lưu hồ sơ đăng nhập ở thư mục:
profile/<AccountsCode>
🍪 BƯỚC 3: Trích xuất File Cookie từ Hồ sơ (Profile) ở bước 2
Down file get_cookie.py từ Git về máy
Mở cửa sổ lệnh (Terminal / Command Prompt) tại thư mục chứa file
Gõ dòng lệnh sau và nhấn Enter:
python get_cookie.py
Gõ AccountsCode bên sheet Accounts ứng với tài khoản đã thêm và nhấn Enter
Hệ thống sẽ báo thành công và tạo ra file:
cookies/<AccountsCode>.json
☁️ BƯỚC 4: Đưa file cho Git tự động
Mở trang web GitHub chứa code đã push
Click mở thư mục:
cookies
Ở góc phải, chọn:
Add file → Upload files
Kéo và thả file:
<AccountsCode>.json
Cuộn xuống dưới cùng, click Commit changes để lưu lại
✅ Hoàn tất

Sau khi hoàn thành tất cả các bước trên:

Account đã được cấu hình đầy đủ
Profile đã được lưu
Cookie đã được upload lên GitHub
Hệ thống có thể tự động chạy với account mới
⚠️ Lưu ý quan trọng
Không chia sẻ file cookie .json cho người khác
Không thay đổi cấu trúc thư mục:
profile/
cookies/
Đảm bảo 2FA_Secret chính xác, nếu sai sẽ không login được
Nếu gặp lỗi login → thử chạy lại từ BƯỚC 2
🛠 Troubleshooting

Không login được:

Kiểm tra lại Email / Password
Kiểm tra 2FA_Secret
Đảm bảo nhập đúng AccountsCode

Không tạo được cookie:

Kiểm tra đã login thành công chưa
Kiểm tra thư mục profile/ đã có dữ liệu chưa
