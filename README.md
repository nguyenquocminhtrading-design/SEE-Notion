# SEE Notion — AI Task Handover & Deadline Management

Bot Discord nhận lệnh **ngôn ngữ tự nhiên** → LLM parse → xác nhận → tạo task trong **Notion** → **email nhắc hạn** tự động (3 ngày trước / 1 ngày / đúng hạn / quá hạn).

> Kế hoạch đầy đủ: `notion-platform/docs/AI_TASK_HANDOVER_TECHNICAL_PLAN.md` (workspace ZCode)

---

## Cấu trúc

```
SEE Notion/
├── app/
│   ├── main.py                  # Entry: FastAPI + Discord bot + APScheduler (1 process)
│   ├── config.py                # Điểm đọc secret DUY NHẤT (env + .env)
│   ├── container.py             # Dựng dependencies 1 lần
│   ├── scheduler.py             # Cron quét reminder mỗi 5 phút
│   ├── api/routers.py           # REST: /healthz /readyz /api/v1/tasks /api/v1/audit
│   ├── db/                      # SQLite: users, pending_actions, notification_log, audit_log
│   ├── models/                  # Domain: lifecycle, ParsedCommand, Preview
│   ├── adapters/
│   │   ├── notion_gateway.py    # ĐIỂM DUY NHẤT gọi Notion (rate limit + retry + pagination)
│   │   ├── llm/                 # GLM (chính) / Ollama (local, swap bằng env)
│   │   ├── email/               # SMTP (Gmail App Password) / Resend
│   │   └── discord_client.py    # Bot: /task, /my, nút ✅/❌ xác nhận
│   └── services/                # parser, validator, confirmation, task_service, reminder_engine, authz
├── tests/unit/                  # 46 unit test (lifecycle, validator, reminder, confirmation)
├── team.yaml                    # Danh bạ team (bạn là admin duy nhất)
├── config.yaml                  # Reminder rules, TTL, giới hạn
└── .env                         # Secrets (đã copy từ .env.example — ĐIỀN GIÁ TRỊ THẬT)
```

## Các bước setup (làm đúng thứ tự)

### Bước 1 — Notion (5-10 phút)

**A. Tạo Integration và lấy `NOTION_TOKEN`**
1. Truy cập [Notion Integrations](https://www.notion.so/profile/integrations) (đăng nhập bằng tài khoản Notion của bạn).
2. Bấm nút **New integration** (hoặc "Create new integration").
3. Ở phần **Associated workspace**, chọn workspace bạn muốn dùng. Đặt tên (ví dụ: `SEE Notion Bot`).
4. Ở phần **Capabilities**, tick chọn:
   - *Read content, Update content, Insert content*.
   - *Read user information including email addresses* (Rất quan trọng để gán Assignee).
5. Bấm **Submit**. Sau khi tạo xong, copy chuỗi **Internal Integration Secret** (bắt đầu bằng `secret_...`). Đây chính là `NOTION_TOKEN` của bạn.

**B. Tạo Database và lấy `NOTION_DATABASE_ID`**
1. Tạo một trang mới trong Notion, chọn kiểu **Table** (Database) và đặt tên là `Tasks`.
2. Tạo **đúng các property sau** (Lưu ý: Type của property không đổi được sau khi tạo):

   | Property | Type |
   |----------|------|
   | Name | Title |
   | Status | Status — options: `Pending, In Progress, In Review, Done, Blocked, Cancelled` |
   | Assignee | People |
   | Creator | People |
   | Deadline | Date |
   | Start Date | Date |
   | Priority | Select: `High, Medium, Low` |
   | Description | rich_text (Text) |
   | Handover Notes | rich_text (Text) |
   | Handover Date | Date |
   | Archived (system) | Checkbox |
   | Task ID (system) | rich_text (Text) |

3. Lấy Database ID: Mở Database dưới dạng Full Page. Nhìn lên thanh địa chỉ trình duyệt, copy đoạn mã gồm 32 ký tự nằm giữa dấu `/` và dấu `?v=`. Đó chính là `NOTION_DATABASE_ID`.
   *(Ví dụ: `https://www.notion.so/workspace/1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p?v=...` -> ID là `1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p`)*

**C. Cấp quyền cho Bot truy cập Database**
1. Ở trang Database vừa tạo, bấm vào biểu tượng `•••` (dấu 3 chấm) ở góc trên bên phải.
2. Chọn **Connections** (hoặc Add connections) -> Tìm tên Integration bạn vừa tạo (ví dụ `SEE Notion Bot`) và chọn nó.
3. Bấm **Confirm**. (Nếu không làm bước này, API sẽ báo lỗi 404 Not Found).
4. Tạo 2 view trong Notion (thủ công 1 lần): **Calendar** (theo Deadline) và **Quá hạn** (filter Deadline is before today ∧ Status ≠ Done/Cancelled).

### Bước 2 — Discord Bot (5-10 phút)

**A. Tạo Bot và lấy `DISCORD_BOT_TOKEN`**
1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications).
2. Bấm **New Application** ở góc trên phải, đặt tên (ví dụ: `SEE Notion Bot`) và đồng ý các điều khoản.
3. Ở menu bên trái, chọn **Bot**.
4. Bấm **Reset Token** (hoặc Generate Token) -> Bấm **Yes, do it!**.
5. Copy đoạn mã vừa hiện ra. Đây chính là `DISCORD_BOT_TOKEN`. (Lưu ý: Token này chỉ hiện 1 lần, hãy lưu ngay vào file `.env`).

**B. Mời Bot vào Server của bạn**
1. Ở menu bên trái, chọn **OAuth2** -> **URL Generator**.
2. Trong phần **Scopes**, tick chọn `bot` và `applications.commands`.
3. Trong phần **Bot Permissions** vừa hiện ra bên dưới, tick chọn:
   - *Send Messages*
   - *Read Message History*
4. Kéo xuống dưới cùng, copy URL được tạo ra và dán vào thanh địa chỉ trình duyệt.
5. Chọn Server bạn muốn thêm bot vào và bấm **Authorize**.

**C. Lấy `DISCORD_GUILD_ID` và User ID**
1. Bật **Developer Mode** trên Discord: Vào Cài đặt người dùng (biểu tượng bánh răng) -> **Advanced** (Nâng cao) -> Bật **Developer Mode** (Chế độ nhà phát triển).
2. Lấy Server ID (`DISCORD_GUILD_ID`): Ra ngoài màn hình chính, chuột phải vào icon Server của bạn ở cột bên trái -> Chọn **Copy Server ID** (Sao chép ID Máy chủ).
3. Lấy User ID của bạn: Chuột phải vào tên của bạn trong kênh chat -> Chọn **Copy User ID**. Điền ID này vào file `team.yaml`.

### Bước 3 — GLM API key

Lấy key từ https://z.ai (hoặc nền tảng GLM bạn dùng) → điền `LLM_API_KEY`.

### Bước 4 — Gmail App Password (email nhắc hạn)

Để bot có thể tự động gửi email nhắc nhở, bạn cần thiết lập SMTP của Gmail.

1. **Bật xác minh 2 bước (2-Step Verification):**
   - Đăng nhập vào tài khoản Google **dành cho bot** (khuyên dùng tài khoản riêng, không dùng email cá nhân chính).
   - Truy cập [Google Account Security](https://myaccount.google.com/security).
   - Tìm mục "2-Step Verification" và bật nó lên (làm theo hướng dẫn của Google để thêm số điện thoại).

2. **Tạo App Password (Mật khẩu ứng dụng):**
   - Sau khi bật xác minh 2 bước, truy cập trực tiếp link này: [App Passwords](https://myaccount.google.com/apppasswords).
   - Đặt tên ứng dụng (ví dụ: `SEE Notion Bot`) và bấm **Create**.
   - Google sẽ hiện ra một mật khẩu gồm 16 chữ cái trên nền vàng. Copy 16 ký tự này (không kèm khoảng trắng).
   - Điền mật khẩu này vào biến `SMTP_PASS` trong file `.env`. **Tuyệt đối không dùng mật khẩu đăng nhập Gmail thông thường ở đây.**

3. **Cấu hình .env:**
   - `SMTP_USER` = email của bot (ví dụ: `bot-cua-ban@gmail.com`).
   - `EMAIL_FROM` = Tên hiển thị người gửi (ví dụ: `SEE Notion Bot <bot-cua-ban@gmail.com>`).

### Bước 5 — Điền .env + team.yaml

- Copy từng giá trị vào `.env` (đang là placeholder).
- `team.yaml`: điền tên/email/Discord ID của bạn. Mặc định **bạn là admin duy nhất**.
- Đổi `APP_TOKEN` thành chuỗi ngẫu nhiên bất kỳ (bảo vệ REST API).

### Bước 6 — Chạy

```bash
cd "C:\Users\Acer\Desktop\My carrer\SEE Notion"
.venv\Scripts\activate          # venv đã cài sẵn dependencies
python -m app.main              # chạy app (FastAPI :8000 + bot + scheduler)
```

Kiểm tra:
- Terminal thấy `Bot online: ...` → bot đã vào server Discord.
- Trình duyệt mở http://127.0.0.1:8000/readyz → `db: ok`; `notion` sẽ ok khi token thật.
- Trên Discord gõ: `/task assign tui làm demo trước ngày 30/09/2026` → bot hiện preview → bấm ✅ → task xuất hiện trong Notion.
- `/my` → xem task đang mở của bạn.

### Chạy test

```bash
.venv\Scripts\activate
python -m pytest tests -q       # 46 test, ~1 giây
```

## Lệnh NL hỗ trợ (MVP)

| Lệnh ví dụ | Kết quả |
|------------|---------|
| "Assign Minh làm báo cáo trước ngày 30/09/2026" | Preview → tạo task + gán người + nhắc hạn |
| "Tạo task dọn kho deadline thứ 6 này ưu tiên cao" | Tạo task (thiếu người → hỏi) |
| "Dời task TSK-0003 sang 10/10" | Đổi deadline (có preview) |
| "Task báo cáo xong rồi" | Chuyển Done |
| "Việc của tui có gì" hoặc `/my` | Liệt kê task đang mở |

**An toàn:** mọi hành động ghi đều hiện preview + cần bấm ✅ (hết hạn 10 phút); LLM chỉ parse JSON, không tự thực thi; archive luôn cần xác nhận rõ ràng.

## Reminder hoạt động thế nào

Mỗi 5 phút, hệ thống quét task đang mở trong Notion. Với mỗi task, tính các rule trong `config.yaml` (−3 ngày, −1 ngày, đúng hạn, quá hạn 1/4/7 ngày). Chống gửi trùng bằng ràng buộc UNIQUE trong SQLite — restart bao nhiêu lần cũng không gửi lặp, không sót (quét lại cửa sổ 30 ngày quá khứ). Task Done/Cancelled tự ngừng nhận reminder. Đổi deadline → reminder tự tính lại theo hạn mới.

## Đổi LLM sang Ollama (khi sẵn sàng)

```bash
ollama pull qwen2.5:7b
# .env: LLM_PROVIDER=ollama, LLM_MODEL=qwen2.5:7b
python -m app.main
```

## Lưu ý quan trọng

- **Property type trong Notion không đổi được sau khi tạo** — làm đúng Bước 1 ngay từ đầu.
- Nếu không gán được Assignee qua API → kiểm tra người đó **đã là member của Notion workspace** chưa, và database đã share cho integration chưa.
- `data/app.db` là dữ liệu vận hành — backup bằng cách copy file.
- Secrets chỉ nằm trong `.env`; không commit, không log.
