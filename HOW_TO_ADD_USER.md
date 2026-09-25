# Hướng Dẫn Thêm User Mới Vào Hệ Thống (SEE Notion Bot)

Vì hệ thống quản lý danh tính rất chặt chẽ để bảo mật cho Notion Workspace của bạn, bot sẽ **KHÔNG** tự động nhận diện hay cấp quyền cho người lạ tự ý vào Discord gõ lệnh. Bạn (với tư cách là Admin) cần làm thủ công vài bước để thêm thành viên mới.

Dưới đây là 3 bước đơn giản để cấp quyền cho 1 thành viên mới.

---

## Bước 1: Lấy ID Discord của người đó
Discord ID là 1 dãy số định danh duy nhất (không phải tên hiển thị). Để lấy được dãy số này:
1. Mở ứng dụng Discord, vào **User Settings** (Cài đặt người dùng) -> **Advanced** (Nâng cao) -> Bật **Developer Mode** (Chế độ nhà phát triển).
2. Trở lại khung chat, click chuột phải vào avatar hoặc tên của thành viên mới đó.
3. Chọn **Copy User ID** (Sao chép ID người dùng). Lúc này bạn đã copy được dãy số (VD: `351176931997384704`).

---

## Bước 2: Cập nhật thông tin vào file `team.yaml`
Mở file `team.yaml` trong mã nguồn và khai báo người này vào cuối danh sách `users:`. Dán dãy số bạn vừa copy vào phần `discord_id`.

**Mẫu khai báo:**
```yaml
  - display_name: "TênNgắnGọn"     # (Ví dụ: "Cường" - để dùng khi chat: "Assign cho Cường")
    full_name: "Tên Đầy Đủ"      # Tên thật
    email: "email@gmail.com"     # (Quan trọng) Email này dùng để gửi thông báo task và để map với Notion
    discord_id: "351176931997384704" # Dãy số ID Discord vừa copy
    notion_user_id: ""           # Cứ để trống "" (đọc giải thích ở dưới)
    role: member                 # Vai trò: "member" hoặc "admin"
    prefs: { email: true, discord_dm: true } # Cho phép nhận thông báo
```

---

## Bước 3: Khởi động lại Bot
Code của bot sẽ tự động đọc file `team.yaml` ở mỗi lần khởi động.
1. Quay lại Terminal (nơi đang chạy bot).
2. Bấm `Ctrl + C` để tắt server hiện tại.
3. Chạy lại lệnh: `python -m app.main`

Sau khi bot báo khởi động thành công, người mới đã có thể chat và dùng bot bình thường.

---

### 💡 Câu hỏi thường gặp: Chỗ `notion_user_id` sao lại để trống?
Bot có một cơ chế cực kỳ thông minh tên là **`sync_notion_users`**. 
Mỗi khi bạn khởi động lại bot (ở Bước 3), bot sẽ tự động quét danh sách thành viên trong Notion của bạn. 
Nếu nó thấy người nào trên Notion có **email** trùng với email bạn vừa khai báo trong `team.yaml`, nó sẽ tự động chèn cái ID Notion của họ vào database ẩn bên dưới. Nhờ vậy, khi bạn gán task, bot biết chính xác phải tag ai bên Notion mà bạn không cần phải copy Notion ID bằng tay!

*(Lưu ý nhỏ: Người mới đó phải được mời vào Notion Workspace/Database của bạn bằng chính email đó thì bot mới quét thấy được nhé).*
