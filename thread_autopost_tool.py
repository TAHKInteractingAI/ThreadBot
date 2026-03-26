import os
import sys
import time
import random
import traceback
import asyncio
import requests
import regex as re
import gspread

from datetime import datetime
from PIL import Image
from oauth2client.service_account import ServiceAccountCredentials
from playwright.async_api import async_playwright

# Windows async event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# =========================
# CONFIGURATION
# =========================
BASE_DIR = os.getcwd()
CREDENTIAL_FILE = "credentials.json"
RECRUIT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1YZrOO7Wb1fSCKeLNQnZMbXfNJuc7-kIz5ub1aXmzZdg/edit?usp=sharing"

# ===== TÊN TAB =====
RECRUIT_TAB_NAME = "Recruitment"
ACCOUNT_TAB_NAME = "Accounts"

# ===== TÊN CỘT TAB RECRUITMENT =====
COL_POSITION = "Position"
COL_JOB_CONTENT = "Job Content"
COL_THREAD_CONTENT = "Thread Content"
COL_TOPIC = "Topic"
COL_IMAGE = "Image URL"
COL_POSTED = "Posted"
COL_LINK_POST = "Link post"
COL_DATE = "Date"
COL_ACCOUNTS_CODE = "AccountsCode"

# MỞ GIỚI HẠN ĐĂNG BÀI ĐỂ ĐĂNG HẾT
MAX_POSTS_PER_RUN = 999

THREADS_URL = "https://www.threads.net"

POST_DELAY_RANGE = (3, 6)
AFTER_POST_DELAY = (5, 8)

# CẤU HÌNH THỜI GIAN NGHỈ CHỐNG SPAM (Giây)
DELAY_BETWEEN_POSTS = (60, 180)


# =========================
# ULTILS
# =========================
def normalize_threads_content(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s*(\p{Extended_Pictographic})", r"\n\1", t)
    t = re.sub(r"(\?)\s+", r"\1\n", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def convert_google_drive(url: str) -> str:
    match = re.search(r"/d/([^/]+)/", url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    match = re.search(r"id=([^&]+)", url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url


def get_filename_from_response(response, default="image.jpg"):
    cd = response.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        return cd.split("filename=")[-1].strip('"')
    return default


def make_square(image_path, min_size=1080, fill_color=(0, 0, 0)):
    img = Image.open(image_path)
    w, h = img.size
    size = max(min_size, w, h)
    new_img = Image.new("RGB", (size, size), fill_color)
    new_img.paste(img, ((size - w) // 2, (size - h) // 2))
    new_img.save(image_path)


def download_image(url, folder="tmp_images"):
    folder_path = os.path.join(BASE_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)
    url = convert_google_drive(url)
    response = requests.get(url, allow_redirects=True, timeout=20)
    if response.status_code != 200:
        raise Exception(f"Image download failed: {response.status_code}")

    filename = get_filename_from_response(response).replace("/", "_")
    full_path = os.path.join(folder_path, filename)
    content = response.content
    with open(full_path, "wb") as f:
        f.write(content)
    make_square(full_path)
    return full_path


# =========================
# GOOGLE SHEET LOGIC
# =========================
def connect_sheet(tab_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIAL_FILE, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(RECRUIT_SHEET_URL).worksheet(tab_name)


def get_all_accounts():
    sheet = connect_sheet(ACCOUNT_TAB_NAME)
    records = sheet.get_all_records()
    accounts = {}
    for row in records:
        code = str(row.get("AccountsCode", "")).strip()
        if code:
            accounts[code] = {
                "email": str(row.get("Email", "")).strip(),
                "password": str(row.get("Password", "")).strip(),
            }
    return accounts


def get_unposted_rows(limit=MAX_POSTS_PER_RUN):
    sheet = connect_sheet(RECRUIT_TAB_NAME)
    rows = sheet.get_all_records()
    results = []
    for idx, row in enumerate(rows, start=2):
        posted = str(row.get(COL_POSTED, "")).strip().upper()
        if posted == "YES":
            continue
        results.append({"row_index": idx, "data": row})
        if len(results) >= limit:
            break
    return results


def mark_posted(row_index: int, post_url: str):
    sheet = connect_sheet(RECRUIT_TAB_NAME)

    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sheet.update_cell(row_index, _col_index(RECRUIT_TAB_NAME, COL_POSTED), "YES")
    sheet.update_cell(row_index, _col_index(RECRUIT_TAB_NAME, COL_LINK_POST), post_url)
    sheet.update_cell(row_index, _col_index(RECRUIT_TAB_NAME, COL_DATE), now_time)


def _col_index(tab_name: str, col_name: str) -> int:
    sheet = connect_sheet(tab_name)
    headers = sheet.row_values(1)
    for i, h in enumerate(headers, start=1):
        if h.strip() == col_name:
            return i
    raise Exception(f"❌ Không tìm thấy cột: {col_name} trong tab {tab_name}")


# ==========================================
# THREADS BOT (PLAYWRIGHT)
# ==========================================
class ThreadsBot:
    def __init__(self, account_code: str, email: str, password: str, headless=True):
        self.headless = headless
        self.account_code = account_code
        self.email = email
        self.password = password

        self.profile_dir = os.path.join(BASE_DIR, "profiles", self.account_code)
        os.makedirs(self.profile_dir, exist_ok=True)

        self.pw = None
        self.context = None
        self.page = None

    async def start(self):
        self.pw = await async_playwright().__aenter__()
        self.context = await self.pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            channel="chrome",
            viewport={"width": 1280, "height": 900},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=vi-VN"
            ],
        )
        self.page = await self.context.new_page()

        await self.page.goto(THREADS_URL, wait_until="networkidle")
        is_logged_in = await self._is_logged_in()

        if not is_logged_in:
            print(
                f"⚠ Tài khoản {self.account_code} chưa đăng nhập. Tiến hành auto-login..."
            )
            await self._login()
        else:
            print(f"✅ Tài khoản {self.account_code} đã lưu phiên đăng nhập trước đó.")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.pw:
            await self.pw.stop()

    async def _is_logged_in(self) -> bool:
        try:
            await self.page.wait_for_selector("a[href^='/@']", timeout=8000)
            return True
        except:
            return False

    async def _login(self):
        await self.page.goto(f"{THREADS_URL}/login", wait_until="networkidle")
        try:
            await self.page.wait_for_selector('input[type="text"]', timeout=10000)
            await self.page.fill('input[type="text"]', self.email)
            await self.page.fill('input[type="password"]', self.password)

            await self.page.click(
                'button[type="submit"], button:has-text("Log in"), button:has-text("Đăng nhập")'
            )

            await self.page.wait_for_selector(
                "a[href^='/@']",
                timeout=15000,
            )
            print(f"✅ Đăng nhập tự động thành công cho {self.account_code}!")
        except Exception as e:
            await self.page.screenshot(path=f"error_login_{self.account_code}.png")
            raise Exception(
                f"❌ Login tự động thất bại cho {self.account_code}. Vui lòng kiểm tra lại pass hoặc Threads chặn bot. Lỗi: {e}"
            )

    async def post(self, text: str, image_path: str | None = None):
        text = normalize_threads_content(text)
        if not text.strip():
            raise ValueError("❌ Nội dung bài post trống")

        await self._open_composer()
        await self._type_text(text)
        time.sleep(2)

        if image_path:
            await self._upload_image(image_path)

        print("🚀 Sending post...")
        await self._submit_post()

        print("🔍 Confirming post on profile...")
        post_url = await self._confirm_posted()
        if not post_url:
            raise Exception("❌ Post KHÔNG xuất hiện trên Threads profile")
        return post_url

    async def reply_to_post(self, post_url: str, text: str):
        text = normalize_threads_content(text)
        if not text.strip():
            return

        print("💬 Đang tiến hành thả comment phụ (Thread Content)...")
        await self.page.goto(post_url, wait_until="networkidle")

        # Tăng thời gian chờ load trang bài viết một chút cho giống người
        await self.page.wait_for_timeout(random.randint(4000, 6000))

        try:
            # Click vào icon bong bóng chat (Trả lời / Reply)
            reply_btn = self.page.locator(
                "svg[aria-label='Trả lời'], svg[aria-label='Reply']"
            ).first
            await reply_btn.wait_for(state="visible", timeout=10000)
            await reply_btn.click()

            await self.page.wait_for_timeout(2000)

            # Bắt vào khung gõ chữ và nhập Thread Content
            editor = self.page.locator("div[contenteditable='true']").first
            await editor.wait_for(state="visible", timeout=10000)
            await editor.click()

            await self._type_text(text)
            await self.page.wait_for_timeout(1000)

            # Đăng comment
            await self._submit_post()
            print("✅ Đã đăng comment phụ thành công!")
            await self.page.wait_for_timeout(4000)
        except Exception as e:
            await self.page.screenshot(path=f"error_reply_{self.account_code}.png")
            print(f"⚠ Không thể comment phụ. Lỗi: {e}")

    async def get_profile_name(self) -> str:
        try:
            el = await self.page.wait_for_selector("a[href^='/@']", timeout=5000)
            return await el.get_attribute("href")
        except:
            return ""

    async def _open_composer(self):
        try:
            # Tìm nút mở khung đăng bài
            try:
                # Click bằng thẻ CSS tĩnh (Không phụ thuộc ngôn ngữ)
                # Bắt thẳng vào nút "New Thread" ở thanh menu
                nav_btn = self.page.locator("a[href='/compose']").first
                await nav_btn.wait_for(state="visible", timeout=3000)
                await nav_btn.click()
            except:
                try:
                    trigger_vi = self.page.locator("text='Có gì mới?'").first
                    await trigger_vi.wait_for(state="visible", timeout=3000)
                    await trigger_vi.click()
                except:
                    try:
                        trigger_en = self.page.locator('text="What\'s new?"').first
                        await trigger_en.wait_for(state="visible", timeout=3000)
                        await trigger_en.click()
                    except:
                        plus_btn = self.page.locator(
                            "svg[aria-label='Tạo'], svg[aria-label='Create'], svg[aria-label='Bắt đầu thread mới']"
                        ).first
                        await plus_btn.click(timeout=5000)

            time.sleep(2)

            # Bắt vào khung gõ chữ
            editor = self.page.locator("div[contenteditable='true']").first
            await editor.wait_for(state="visible", timeout=15000)
            await editor.click()

            time.sleep(random.uniform(*POST_DELAY_RANGE))

        except Exception as e:
            await self.page.screenshot(
                path=f"error_open_composer_{self.account_code}.png"
            )
            raise Exception(f"Không thể mở khung đăng bài: {e}")

    async def _type_text(self, text: str):
        # Tốc độ gõ phím ngẫu nhiên để chống bot
        delay_typing = random.randint(15, 30)
        await self.page.keyboard.type(text, delay=delay_typing)
        time.sleep(random.uniform(*POST_DELAY_RANGE))

    async def _confirm_posted(self) -> str:
        username = await self.get_profile_name()
        if not username:
            return ""

        for attempt in range(3):
            print(f"   ⏳ Kiểm tra bài đăng trên tường (Lần {attempt + 1}/3)...")
            await self.page.goto(f"{THREADS_URL}/{username}", wait_until="networkidle")
            await self.page.wait_for_timeout(5000)

            link_locator = self.page.locator("a[href*='/post/']").first

            if await link_locator.count() > 0:
                href = await link_locator.get_attribute("href")
                return f"{THREADS_URL}{href}" if href.startswith("/") else href

            await self.page.wait_for_timeout(2000)

        return ""

    async def _upload_image(self, image_path: str):
        file_input = self.page.locator("input[type='file']").first
        await file_input.set_input_files(image_path)
        await self.page.wait_for_timeout(5000)

    async def _submit_post(self):
        await self.page.keyboard.down("Control")
        await self.page.keyboard.press("Enter")
        await self.page.keyboard.up("Control")
        time.sleep(1)
        await self.page.keyboard.press("Enter")
        time.sleep(8)


# ==========================================
# MAIN WORKFLOW
# ==========================================
async def run():
    print("🚀 START THREADS AUTO POST")

    try:
        accounts_dict = get_all_accounts()
        print(f"🔑 Đã load {len(accounts_dict)} tài khoản từ hệ thống.")
    except Exception as e:
        print(f"❌ Lỗi khi đọc tab Accounts: {e}")
        return

    rows = get_unposted_rows(limit=MAX_POSTS_PER_RUN)
    if not rows:
        print("🎉 Không có bài nào cần đăng.")
        return
    print(f"📄 Tìm thấy {len(rows)} bài chưa đăng")

    for i, item in enumerate(rows):
        row_index = item["row_index"]
        data = item["data"]

        acc_code = str(data.get(COL_ACCOUNTS_CODE, "")).strip()

        job_content = data.get(COL_JOB_CONTENT, "").strip()
        thread_content = data.get(COL_THREAD_CONTENT, "").strip()
        image_url = data.get(COL_IMAGE, "").strip()

        print("=" * 60)
        print(f"📌 BÀI ĐĂNG {i+1}/{len(rows)} - ACCOUNT: {acc_code}")
        print(f"📍 ROW INDEX: {row_index}")

        if not acc_code or acc_code not in accounts_dict:
            print(f"⚠ Mã account '{acc_code}' không hợp lệ hoặc trống → SKIP")
            continue

        if not job_content:
            print("⚠ Job Content (Bài chính) trống → SKIP")
            continue

        acc_info = accounts_dict[acc_code]
        # Bật Headless = False để bạn nhìn thấy tiến trình, nếu muốn chạy ngầm hoàn toàn hãy sửa thành True
        bot = ThreadsBot(
            account_code=acc_code,
            email=acc_info["email"],
            password=acc_info["password"],
            headless=True,
        )

        image_path = None
        try:
            await bot.start()

            if image_url:
                try:
                    image_path = download_image(image_url)
                except Exception as e:
                    raise Exception(f"❌ Tải ảnh thất bại: {e}")

            # 1. ĐĂNG BÀI CHÍNH
            post_url = await bot.post(text=job_content, image_path=image_path)
            print(f"🔗 Post URL (Bài chính): {post_url}")

            # 2. ĐĂNG BÌNH LUẬN PHỤ
            if thread_content:
                await bot.reply_to_post(post_url=post_url, text=thread_content)

            # Cập nhật thành công lên Sheet
            mark_posted(row_index=row_index, post_url=post_url)

            # Xoá ảnh rác
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

            print(f"✅ Đã xử lý (Đăng + Comment) cho {acc_code}")

        except Exception as e:
            print(f"❌ LỖI ĐĂNG BÀI CHO {acc_code}")
            print(str(e))
            traceback.print_exc()

        finally:
            await bot.close()
            print(f"🛑 Đã đóng trình duyệt của {acc_code}")

        # 3. NGHỈ GIẢI LAO TRƯỚC KHI SANG BÀI TIẾP THEO (CHỐNG SPAM)
        if i < len(rows) - 1:
            wait_time = random.randint(*DELAY_BETWEEN_POSTS)
            print(
                f"⏳ Đang nghỉ ngẫu nhiên {wait_time} giây để Threads không phát hiện Spam..."
            )
            time.sleep(wait_time)

    print("🎯 HOÀN TẤT QUÉT & ĐĂNG TẤT CẢ CÁC BÀI!")


if __name__ == "__main__":
    asyncio.run(run())
