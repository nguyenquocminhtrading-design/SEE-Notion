# 📋 Hướng Dẫn Lấy Notion User ID — Chi Tiết

## 🎯 Tại Sao Cần Notion User ID?

Bot SEE Notion sử dụng `notion_user_id` để **match assignee** từ Notion task với user trong hệ thống.

| Không có `notion_user_id` | Có `notion_user_id` |
|---------------------------|---------------------|
| ❌ Không gán task được cho user | ✅ Gán task trong Notion → bot nhận diện đúng user |
| ❌ Không gửi email nhắc hạn | ✅ Gửi email nhắc hạn tự động |
| ❌ Không gửi Discord DM nhắc | ✅ Gửi Discord DM nhắc (nếu có `discord_id`) |

**Log hiện tại**: `Đã seed 2 user` → chỉ **Minh** có `notion_user_id`, 3 user còn lại rỗng.

---

## 🔍 3 Cách Lấy Notion User ID

### Cách 1: Từ Notion Web UI (Khuyên dùng — Dễ nhất)

#### Bước 1: Mở Notion Settings
1. Mở **Notion** trên trình duyệt → đăng nhập workspace **SEE Club**
2. Click **avatar góc trên phải** → chọn **Settings & members**
3. Tab bên trái chọn **Members**

#### Bước 2: Tìm User & Copy ID
```
Danh sách Members:
├── Minh (see.club@vgu.edu.vn)          ← Admin/Owner
├── Cường (10523006@student.vgu.edu.vn) ← Member
├── Hân   (10623011@student.vgu.edu.vn) ← Member
└── Ánh   (10725018@student.vgu.edu.vn) ← Member
```

**Với mỗi user cần lấy ID**:
1. Hover vào dòng user → hiện **3 chấm (...)** bên phải
2. Click **3 chấm (...)** → chọn **Copy link** (hoặc Copy ID nếu có)
3. Dán vào notepad → lấy phần UUID

**Ví dụ link copy được**:
```
https://www.notion.so/@see-club/3a1d872b-594c-81b8-bf14-0002673b336a
```
→ **User ID**: `3a1d872b-594c-81b8-bf14-0002673b336a`

> **Lưu ý quan trọng**:
> - Chỉ lấy ID của user **type = person** (người thật)
> - **KHÔNG** lấy ID của bot/integration (type = bot)
> - ID format: UUID có dấu gạch ngang `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

### Cách 2: Dùng Script Tự Động (Nhanh — Chạy Trên Server)

#### Yêu cầu
- Đã SSH vào Alwaysdata
- `.env` có `NOTION_TOKEN` hợp lệ

#### Chạy lệnh sau:

```bash
ssh seecodenotion@ssh-seecodenotion.alwaysdata.net
cd /home/seecodenotion/SEE-Notion
source venv/bin/activate

python -c "
import asyncio, httpx
from app.config import get_settings

async def main():
    s = get_settings()
    headers = {
        'Authorization': f'Bearer {s.notion_token}',
        'Notion-Version': s.notion_version,
    }
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        resp = await client.get('https://api.notion.com/v1/users')
        data = resp.json()
        print('=== NOTION USERS (type=person) ===')
        for u in data.get('results', []):
            if u.get('type') == 'person':
                person = u.get('person') or {}
                email = person.get('email', 'N/A')
                name = u.get('name', 'N/A')
                print(f'{u[\"id\"]} | {name} | {email}')
        print()
        print('=== TẤT CẢ USERS (debug) ===')
        for u in data.get('results', []):
            print(f'{u.get(\"type\", \"?\")} | {u.get(\"id\", \"?\")} | {u.get(\"name\", \"?\")} | {(u.get(\"person\") or {}).get(\"email\", \"\")}')

asyncio.run(main())
"
```

#### Output mẫu:
```
=== NOTION USERS (type=person) ===
3a1d872b-594c-81b8-bf14-0002673b336a | Minh | see.club@vgu.edu.vn
5b2e9c1d-4f3a-7e8b-9c0d-123456789abc | Cường | 10523006@student.vgu.edu.vn
7c3f8d2e-5a4b-9f1c-0e2d-3456789abdef | Hân | 10623011@student.vgu.edu.vn
9e4b1c3d-6f2a-8e5b-1c4d-56789abdef12 | Ánh | 10725018@student.vgu.edu.vn

=== TẤT CẢ USERS (debug) ===
person | 3a1d872b-594c-81b8-bf14-0002673b336a | Minh | see.club@vgu.edu.vn
person | 5b2e9c1d-4f3a-7e8b-9c0d-123456789abc | Cường | 10523006@student.vgu.edu.vn
person | 7c3f8d2e-5a4b-9f1c-0e2d-3456789abdef | Hân | 10623011@student.vgu.edu.vn
person | 9e4b1c3d-6f2a-8e5b-1c4d-56789abdef12 | Ánh | 10725018@student.vgu.edu.vn
bot    | b1o2t3i4d5-6789-0abc-def1-234567890123 | SEE Notion Bot | 
```

**Copy 4 UUID đầu tiên** → điền vào `team.yaml`.

---

### Cách 3: Từ Task Đã Assign (Reverse Lookup)

Nếu đã từng assign task cho user trong Notion:

1. Mở task đó trong Notion
2. Nhấn **F12** → tab **Console**
3. Dán code sau → Enter:

```javascript
// Lấy assignee IDs từ property "Assignee" của page hiện tại
// Chạy trong Console của DevTools (F12)
const blocks = document.querySelectorAll('[data-block-id]');
const pageBlock = Array.from(blocks).find(b => b.dataset.blockId?.length === 32);
if (pageBlock) {
    console.log('Page ID:', pageBlock.dataset.blockId);
}

// Hoặc tìm trong network tab:
// 1. Mở Network tab
// 2. Filter: "loadPageChunk" 
// 3. Click task → xem response → tìm "assignee_ids"
```

4. Hoặc dùng API query task (cần script):
```bash
python -c "
import asyncio, httpx
from app.config import get_settings

async def main():
    s = get_settings()
    headers = {
        'Authorization': f'Bearer {s.notion_token}',
        'Notion-Version': s.notion_version,
    }
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Query database để lấy task có assignee
        body = {'page_size': 10}
        resp = await client.post(f'https://api.notion.com/v1/databases/{s.notion_database_id}/query', json=body)
        data = resp.json()
        for page in data.get('results', []):
            assignees = page.get('properties', {}).get('Assignee', {}).get('people', [])
            if assignees:
                title = page.get('properties', {}).get('Task name', {}).get('title', [{}])[0].get('plain_text', '?')
                for a in assignees:
                    print(f'Task: {title} | Assignee: {a.get(\"name\")} | ID: {a.get(\"id\")} | Email: {(a.get(\"person\") or {}).get(\"email\")}')
asyncio.run(main())
"
```

---

## ✏️ Cập Nhật `team.yaml`

### File hiện tại (`team.yaml`):
```yaml
users:
  - display_name: "Minh"
    full_name: "Quốc Minh"
    email: "songminh688@gmail.com"
    discord_id: "661748766990270465"
    notion_user_id: "3a1d872b-594c-81b8-bf14-0002673b336a"  # ✅ ĐÃ CÓ
    role: admin
    prefs: { email: true, discord_dm: true }

  - display_name: "Cường"
    full_name: "Trương Phước Minh Cường"
    email: "10523006@student.vgu.edu.vn"
    discord_id: "351176931997384704"
    notion_user_id: ""  # ← THÊM VÀO ĐÂY
    role: member
    prefs: { email: true, discord_dm: true }

  - display_name: "Hân"
    full_name: "Hàng gia Hân"
    email: "10623011@student.vgu.edu.vn"
    discord_id: ""
    notion_user_id: ""  # ← THÊM VÀO ĐÂY
    role: member
    prefs: { email: true, discord_dm: true }

  - display_name: "Ánh"
    full_name: "Hồng Ánh"
    email: "10725018@student.vgu.edu.vn"
    discord_id: ""
    notion_user_id: ""  # ← THÊM VÀO ĐÂY
    role: member
    prefs: { email: true, discord_dm: true }
```

### Sau khi điền (ví dụ):
```yaml
  - display_name: "Cường"
    # ...
    notion_user_id: "5b2e9c1d-4f3a-7e8b-9c0d-123456789abc"  # ← UUID từ Cách 1 hoặc 2

  - display_name: "Hân"
    # ...
    notion_user_id: "7c3f8d2e-5a4b-9f1c-0e2d-3456789abdef"  # ← UUID từ Cách 1 hoặc 2

  - display_name: "Ánh"
    # ...
    notion_user_id: "9e4b1c3d-6f2a-8e5b-1c4d-56789abdef12"  # ← UUID từ Cách 1 hoặc 2
```

> **Lưu ý format YAML**:
> - Thụt lề 2 spaces cho từng field
> - `notion_user_id` trong ngoặc kép `""`
> - Không có tab, chỉ dùng space

---

## 🔄 Quy Trình Triển Khai Hoàn Chỉnh

### 1. Local: Cập nhật file
```bash
# Mở file edit
nano team.yaml
# Hoặc dùng VS Code / editor bất kỳ
```

### 2. Commit & Push
```bash
git add team.yaml
git commit -m "chore: add notion_user_id for Cuong, Han, Anh"
git push origin main
```

### 3. Restart Bot trên Alwaysdata
1. Mở **Alwaysdata Dashboard** → **Advanced** → **Services**
2. Tìm service `30534` (SEE_Notion_Bot)
3. Click **Restart** (biểu tượng 🔄 mũi tên xoay tròn)
4. Chờ ~10 giây → click **Logs** để xem

### 4. Verify Logs (Quan trọng)
Tìm dòng:
```
2026-10-06 04:30:58,910 INFO app.services.authz Đã seed 4 user từ team.yaml
2026-10-06 04:31:03,544 INFO app.container Đã tự map 3 Notion user ID
```
- `seed 4 user` = 4 user trong team.yaml
- `map 3 Notion user ID` = 3 user mới được map tự động (Cường, Hân, Ánh)

---

## ✅ Verify Sau Restart (SSH Check)

```bash
ssh seecodenotion@ssh-seecodenotion.alwaysdata.net
cd /home/seecodenotion/SEE-Notion
source venv/bin/activate

python -c "
from app.db.session import get_session
from app.db.models import User
from sqlalchemy import select

s = get_session()
print('=== USERS TRONG DB ===')
for u in s.scalars(select(User).where(User.active==True)):
    notion_id = u.notion_user_id or 'NULL'
    discord = u.discord_id or 'NULL'
    print(f'{u.display_name:10} | notion_id={notion_id:36} | discord={discord} | email={u.email}')
"
```

**Kết quả mong đợi**:
```
=== USERS TRONG DB ===
Minh       | notion_id=3a1d872b-594c-81b8-bf14-0002673b336a | discord=661748766990270465 | email=songminh688@gmail.com
Cường      | notion_id=5b2e9c1d-4f3a-7e8b-9c0d-123456789abc | discord=351176931997384704 | email=10523006@student.vgu.edu.vn
Hân        | notion_id=7c3f8d2e-5a4b-9f1c-0e2d-3456789abdef | discord=NULL             | email=10623011@student.vgu.edu.vn
Ánh        | notion_id=9e4b1c3d-6f2a-8e5b-1c4d-56789abdef12 | discord=NULL             | email=10725018@student.vgu.edu.vn
```

---

## 🧪 Test End-to-End

### Test 1: Gán Task Trong Notion
1. Mở Notion → Database task
2. Tạo task mới:
   - **Task name**: "Test assign Cường"
   - **Assignee**: Chọn **Cường**
   - **Due date**: Hôm nay
   - **Status**: "Not started"
3. Save

### Test 2: Trigger Reminder Thủ Công (Không đợi 5 phút)
```bash
ssh seecodenotion@ssh-seecodenotion.alwaysdata.net
cd /home/seecodenotion/SEE-Notion
source venv/bin/activate

python -c "
import asyncio
from app.container import build_container
from app.db.session import get_session
from datetime import date

c = build_container()
s = get_session()
print('Đang quét reminder...')
sent = asyncio.run(c.reminder.scan_and_dispatch(s, date.today()))
print(f'Đã gửi {sent} thông báo')
"
```

### Test 3: Kiểm Tra Nhận Email/Discord
| User | Email | Discord DM |
|------|-------|------------|
| Cường | ✅ Nhận | ✅ Nhận (có discord_id) |
| Hân   | ✅ Nhận | ❌ Không (không có discord_id) |
| Ánh   | ✅ Nhận | ❌ Không (không có discord_id) |

---

## 🆘 Troubleshooting

### Vấn đề 1: Script Cách 2 trả về rỗng / lỗi 401
```bash
# Kiểm tra token
python -c "from app.config import get_settings; s=get_settings(); print('Token:', s.notion_token[:20]+'...')"
```
- Token sai → cập nhật `.env` → restart bot
- Token hết hạn → tạo mới ở Notion Integrations

### Vấn đề 2: User không có trong API response
- User chưa join workspace SEE Club → mời join trước
- User là guest → chỉ member mới có trong `/v1/users`
- Integration không được share database → vào Notion Settings → Connections → Add integration

### Vấn đề 3: Match email nhưng không match ID
- Email trong `team.yaml` ≠ email Notion account
- Fix: Dùng **Cách 1** lấy ID trực tiếp từ UI (chắc chắn nhất)

### Vấn đề 4: Bot restart nhưng log không có "Đã tự map X Notion user ID"
- Xem log đầy đủ: `grep -i "map\|sync\|notion" logs`
- Có thể `sync_notion_users()` bị exception → check `try/except` trong `container.py:62-66`

---

## 📋 Checklist Hoàn Thành

- [ ] Lấy được Notion User ID cho **Cường**
- [ ] Lấy được Notion User ID cho **Hân**
- [ ] Lấy được Notion User ID cho **Ánh**
- [ ] Cập nhật `team.yaml` local (3 user)
- [ ] `git add team.yaml && git commit -m "..." && git push`
- [ ] Restart service 30534 trên Alwaysdata Dashboard
- [ ] Verify log: `Đã seed 4 user` + `Đã tự map 3 Notion user ID`
- [ ] SSH check DB: 4 user đều có `notion_user_id` không NULL
- [ ] Test assign task cho Cường trong Notion
- [ ] Trigger reminder tick thủ công
- [ ] Cường nhận email + Discord DM
- [ ] Hân, Ánh nhận email

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề:
1. **Xem log đầy đủ**: Alwaysdata Dashboard → Services → 30534 → Logs
2. **Chạy debug script** (xem phần Verify)
3. **Check Notion Integration**: Settings → Connections → SEE Notion Bot → Configure → Databases đã share?

---

**Tóm tắt 1 dòng**: Lấy UUID từ Notion Settings → Members → Copy link → điền vào `team.yaml` → git push → restart bot → done.