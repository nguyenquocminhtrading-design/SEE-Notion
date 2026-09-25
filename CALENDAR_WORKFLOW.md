# Kế hoạch & Workflow Tích hợp Gmail và Calendar cho Team

Tài liệu này trình bày phương án tối ưu nhất để kết nối hệ thống giao task (Discord Bot -> Notion) với **Gmail** và **Calendar** cho từng thành viên trong đội ngũ.

---

## 1. Phân tích Phương án: Google APIs vs Notion Calendar

### Phương án A: Tích hợp trực tiếp Google Calendar & Gmail API (Khá phức tạp)
- **Ưu điểm:** Tự động hóa hoàn toàn, bot có thể tự tạo event trên Google Calendar của member và gửi email từ địa chỉ của bot.
- **Nhược điểm:** Phải setup Google Cloud Console, xử lý OAuth2 cho từng user (rất phiền phức cho end-user) hoặc dùng Service Account với Domain-wide Delegation (chỉ dùng được nếu dùng Google Workspace cho doanh nghiệp).

### Phương án B: Sử dụng Notion Calendar + SMTP Email (⭐ Khuyên dùng - Tiện lợi nhất)
- **Về Calendar (Lịch):** Tận dụng **Notion Calendar**. Vì bot của bạn đã đẩy task lên database của Notion. Các thành viên chỉ cần tải Notion Calendar, kết nối với tài khoản Google của họ và bật hiển thị Notion Database. Các task có gán tên họ (property `Assignee`) và có `Date` sẽ **tự động** hiện trên Google Calendar của họ mà không cần viết thêm 1 dòng code nào cho việc đồng bộ Calendar.
- **Về Gmail (Thông báo):** Sử dụng thư viện `smtplib` mặc định của Python với tính năng "Mật khẩu ứng dụng" (App Password) của Gmail để bot tự động gửi email thông báo khi có task mới. Không cần setup OAuth2 phức tạp.

👉 **Kết luận:** Phương án B là tiện nhất. Workflow code dưới đây sẽ triển khai theo Phương án B.

---

## 2. Toàn bộ Workflow Code (Chi tiết qua từng file)

Để triển khai phần gửi Email và đảm bảo task vào đúng Notion để đồng bộ Calendar, hệ thống sẽ đi qua các file như sau:

### 2.1. Cập nhật `team.yaml`
Cần thêm thông tin email của từng thành viên để bot biết gửi đi đâu.

```yaml
# team.yaml
members:
  - id: "discord_id_1"
    name: "Nguyen Van A"
    notion_id: "notion_user_id_1"
    email: "nguyenvana@gmail.com" # Thêm trường này
  - id: "discord_id_2"
    name: "Tran Thị B"
    notion_id: "notion_user_id_2"
    email: "tranthib@gmail.com" # Thêm trường này
```

### 2.2. Tạo Service Gửi Email: `app/services/email_service.py` (File mới)
File này chịu trách nhiệm kết nối với Gmail SMTP và gửi email thông báo.

```python
# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

class EmailService:
    def __init__(self):
        # Email và App Password của Bot (Cài đặt trong .env)
        self.bot_email = os.getenv("BOT_EMAIL")
        self.bot_email_password = os.getenv("BOT_EMAIL_PASSWORD")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_task_notification(self, to_email: str, member_name: str, task_title: str, deadline: str, task_url: str):
        if not to_email:
            return

        subject = f"[Task Mới] Bạn có công việc mới: {task_title}"
        body = f"""
        Chào {member_name},

        Bạn vừa được giao một task mới từ hệ thống:
        - Tên công việc: {task_title}
        - Deadline: {deadline}
        
        Xem chi tiết tại Notion: {task_url}
        
        *Lưu ý: Bạn có thể xem task này trên Notion Calendar.*
        """

        msg = MIMEMultipart()
        msg['From'] = self.bot_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.bot_email, self.bot_email_password)
                server.send_message(msg)
                print(f"Đã gửi email thông báo tới {to_email}")
        except Exception as e:
            print(f"Lỗi khi gửi email: {e}")
```

### 2.3. Cập nhật Model Dữ liệu: `app/models/parsed_command.py`
Đảm bảo struct parse ra từ LLM có chứa thông tin assignee và date rõ ràng để map vào Notion.

```python
# app/models/parsed_command.py
# (Bạn đảm bảo có các trường này)
from pydantic import BaseModel
from typing import Optional, List

class ParsedTask(BaseModel):
    title: str
    assignee_name: Optional[str] = None # Dùng để map với team.yaml
    deadline: Optional[str] = None      # Dùng cho Notion Calendar
    # ... các trường khác
```

### 2.4. Tiện ích quản lý Team: `app/services/team_manager.py` (Ví dụ nếu có)
Một hàm để lấy email của thành viên từ `team.yaml`.

```python
# Trong file load team.yaml
def get_member_email_by_name(name_or_id):
    # Đọc từ team.yaml và trả về email
    # ...
    pass
```

### 2.5. Xử lý Logic Chính: `app/main.py` (Hoặc file handler lệnh)
Đây là nơi luồng dữ liệu chạy: Nhận lệnh -> Parse LLM -> Lưu vào Notion -> Gửi Email.

```python
# app/main.py hoặc trong handler của Bot
from app.services.email_service import EmailService
# ... các import khác

email_service = EmailService()

async def handle_create_task(ctx, user_input):
    # 1. LLM parse câu lệnh của user (dùng factory.py / validator.py)
    parsed_task = await llm_parse(user_input) 
    
    # 2. Tạo task trên Notion (đảm bảo truyền Assignee và Date)
    notion_task_url = await notion_service.create_page(
        title=parsed_task.title,
        assignee_id=get_notion_id(parsed_task.assignee_name),
        deadline=parsed_task.deadline
    )
    
    # 3. Gửi Email thông báo (NẾU có người được gán)
    if parsed_task.assignee_name:
        member_email = get_member_email_by_name(parsed_task.assignee_name)
        if member_email:
            email_service.send_task_notification(
                to_email=member_email,
                member_name=parsed_task.assignee_name,
                task_title=parsed_task.title,
                deadline=parsed_task.deadline,
                task_url=notion_task_url
            )
            
    await ctx.send(f"✅ Đã tạo task và gửi email thông báo cho {parsed_task.assignee_name}!")
```

---

## 3. Hướng dẫn Setup cho End-User (Các thành viên trong team)

Để workflow này hoạt động mượt mà mà không tốn công code Calendar API, bạn chỉ cần hướng dẫn team làm 1 lần duy nhất như sau:

1. **Setup Notion Calendar:**
   - Truy cập: [calendar.notion.so](https://calendar.notion.so/)
   - Đăng nhập bằng tài khoản Google (tài khoản công việc/cá nhân).
2. **Hiển thị Task:**
   - Ở cột bên trái của Notion Calendar, chọn `Add Notion database` và tìm đến bảng Task của team bạn.
   - 🪄 *Bùm! Mọi task có gán tên họ và có ngày tháng sẽ tự động hiển thị trên lịch như một Google Calendar event.*
3. **Email thông báo:**
   - Họ sẽ tự động nhận được email từ bot khi được giao task (nhờ đoạn code SMTP ở trên).

## 4. Cần chuẩn bị gì cho tài khoản Bot Email?
1. Tạo một tài khoản Gmail cho bot (VD: `bot.teamcua.ban@gmail.com`).
2. Vào cài đặt tài khoản Google -> Security (Bảo mật).
3. Bật Xác minh 2 bước (2-Step Verification).
4. Tìm phần **App passwords** (Mật khẩu ứng dụng) -> Tạo 1 mật khẩu mới (chọn app là Mail).
5. Copy mật khẩu 16 chữ số đó và dán vào file `.env` (Biến `BOT_EMAIL_PASSWORD`).
