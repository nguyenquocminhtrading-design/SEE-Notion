# SEE Notion — AI Task Handover & Deadline Management

Hệ thống quản lý công việc và hạn chót cho CLB SEE: **Nhận lệnh ngôn ngữ tự nhiên từ Discord** ➔ **LLM phân tích ý định** ➔ **Xem trước & Xác nhận 2 bước** ➔ **Tự động đồng bộ lên Notion** ➔ **Nhắc hẹn đa kênh (Discord DM + Email)** tự động theo chu kỳ.

> 📖 **Xem tài liệu kỹ thuật & audit bảo mật chuyên sâu**: [`SYSTEM_ARCHITECTURE_AND_SECURITY_AUDIT.md`](./SYSTEM_ARCHITECTURE_AND_SECURITY_AUDIT.md)

---

## 🚀 Tính năng nổi bật

- 🤖 **Ra lệnh tự nhiên qua Discord**:
  - Gõ lệnh như chat: *"Tạo task làm slide báo cáo cho Minh deadline thứ 6 tuần sau độ ưu tiên cao"*
  - Hỗ trợ tạo task đơn, cập nhật deadline, đổi người phụ trách, hoàn thành việc.
- 📑 **Nhập task hàng loạt từ biên bản họp (Meeting Minutes)**:
  - Hỗ trợ import bảng Action Items từ file DOCX hoặc CSV/Text.
- 🛡️ **Bảo mật & Phân quyền chặt chẽ (RBAC)**:
  - Admin có toàn quyền điều phối.
  - Member chỉ được sửa/đóng các task do mình tạo hoặc được giao cho mình.
  - Xác thực token chống Timing Attack, chống Arbitrary File Read.
- 👥 **Quản lý danh bạ thành viên linh hoạt**:
  - Tự động map tài khoản Notion qua Email sinh viên VGU (`@student.vgu.edu.vn`).
  - Lệnh Admin `/link-user` và `/link-batch` để gán Discord ID nhanh chóng.
  - Lệnh `/sync-team` cập nhật danh bạ tức thì không cần restart máy chủ.
- ⏰ **Nhắc việc thông minh (Automated Reminders)**:
  - Tự động quét deadline mỗi 5 phút.
  - Bắn thông báo trước 3 ngày, 1 ngày, đúng ngày và khi quá hạn qua Discord DM & Email.
  - Cơ chế Deduplication chống spam lặp tin nhắn.

---

## 📂 Cấu trúc thư mục

```
SEE Notion/
├── app/
│   ├── main.py                     # Entry point: FastAPI + Discord bot + APScheduler
│   ├── config.py                   # Đọc biến môi trường (.env) & Pydantic settings
│   ├── container.py                # Dependency Injection container
│   ├── scheduler.py                # Cron job quét nhắc hạn định kỳ
│   ├── api/
│   │   └── routers.py              # REST API (/healthz, /readyz, /api/v1/tasks)
│   ├── db/
│   │   ├── models.py               # SQLAlchemy models (User, Nonce, AuditLog, NotificationLog)
│   │   └── session.py              # Quản lý SQLite session engine
│   ├── models/                     # Data models (ParsedCommand, Preview, Task)
│   ├── adapters/
│   │   ├── discord_client.py       # Discord Bot Slash Commands & Interactive Views
│   │   ├── notion_gateway.py       # Cầu nối Notion API (Rate-limit, Retry, Pagination)
│   │   ├── llm/                    # OpenAI / GLM / Ollama Adapters
│   │   └── email/                  # SMTP (Gmail) / Resend Adapters
│   └── services/
│       ├── command_flow.py         # Orchestrator điều phối luồng lệnh (Prepare -> Execute)
│       ├── parser.py               # Phân tích cú pháp ngôn ngữ tự nhiên bằng LLM
│       ├── validator.py            # Kiểm tra tính hợp lệ của ngày, assignee, priority
│       ├── authz.py                # RBAC, phân quyền task và liên kết tài khoản
│       ├── confirmation.py         # Quản lý mã Nonce cho tương tác xác nhận
│       ├── reminder_engine.py      # Bộ máy tính toán lịch nhắc hẹn
│       ├── task_service.py         # Nghiệp vụ quản lý Task ID (TSK-xxx) và Notion
│       └── template_parser.py      # Trích xuất task từ bảng DOCX/CSV
├── tests/unit/                     # Bộ kiểm thử 60 unit tests
├── team.yaml                       # Danh bạ thành viên (Nguồn sự thật chính)
├── config.yaml                     # Cấu hình luật nhắc hẹn, TTL, múi giờ
├── .env.example                    # Mẫu khai báo biến môi trường
└── README.md                       # Hướng dẫn sử dụng & vận hành
```

---

## 🛠️ Hướng dẫn lệnh Discord dành cho Admin & Member

| Lệnh | Người dùng | Chức năng |
|---|---|---|
| `/create` | Mọi người | Tạo task mới bằng form hoặc gõ lệnh tự nhiên |
| `/my` | Mọi người | Xem danh sách các task đang mở được giao cho mình |
| `/update` | Mọi người (Có RBAC) | Dời deadline, đổi status hoặc reassign task |
| `/complete` | Mọi người (Có RBAC) | Đánh dấu hoàn thành task |
| `/bulk-create` | Admin / Member | Nhập nhiều task từ bảng DOCX hoặc CSV |
| `/link-user` | **Admin** | Liên kết 1 tài khoản Discord (`@mention` hoặc ID số) với Email |
| `/link-batch` | **Admin** | Nạp danh sách liên kết hàng loạt (`email discord_id`) |
| `/sync-team` | **Admin** | Đọc lại `team.yaml` và nạp vào DB ngay lập tức |

---

## ⚙️ Hướng dẫn cài đặt & Triển khai

### 1. Chuẩn bị môi trường
Yêu cầu **Python 3.11+** (Khuyên dùng Python 3.13).

```bash
# Tạo virtual environment
python -m venv venv

# Kích hoạt trên Windows
.\venv\Scripts\activate
# Hoặc trên Linux/macOS:
source venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
```

### 2. Cấu hình file `.env`
Tạo file `.env` từ `.env.example` và điền các khóa API:
```ini
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=xxx
DISCORD_BOT_TOKEN=xxx
DISCORD_GUILD_ID=xxx
OPENAI_API_KEY=xxx
EMAIL_HOST=smtp.gmail.com
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
APP_TOKEN=your_secure_bearer_token
```

### 3. Chạy kiểm thử (Unit Tests)
```bash
pytest
```
*(Đảm bảo toàn bộ 60/60 tests đều passed).*

### 4. Khởi chạy Server
```bash
python -m app.main
```
Ứng dụng sẽ khởi động cả FastAPI Server, Discord Bot và Scheduler nhắc việc trong 1 tiến trình.
