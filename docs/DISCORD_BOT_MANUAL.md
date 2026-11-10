# SỔ TAY HƯỚNG DẪN SỬ DỤNG DISCORD BOT SEE-NOTION

> **Dành cho**: Thành viên & Ban Điều hành CLB SEE (Sustainable Engineering Edge)  
> **Hệ thống**: Quản trị Công việc, Deadline & Tự động hoá Notion qua Discord  
> **Phiên bản**: v2.1-production | Cập nhật: 10/11/2026  

---

## MỤC LỤC
1. [Giới thiệu & Quy trình hoạt động](#1-giới-thiệu--quy-trình-hoạt-động)
2. [Nguyên tắc Phân quyền (RBAC)](#2-nguyên-tắc-phân-quyền-rbac)
3. [Danh mục lệnh Thao tác Task (Member & Admin)](#3-danh-mục-lệnh-thao-tác-task)
   - [3.1. Lệnh `/create` — Tạo task mới](#31-lệnh-create--tạo-task-mới)
   - [3.2. Lệnh `/my` — Tra cứu task của tôi](#32-lệnh-my--tra-cứu-task-của-tôi)
   - [3.3. Lệnh `/update` — Cập nhật task](#33-lệnh-update--cập-nhật-task)
   - [3.4. Lệnh `/complete` — Hoàn thành task](#34-lệnh-complete--hoàn-thành-task)
   - [3.5. Lệnh `/bulk-create` — Tạo task từ biên bản họp](#35-lệnh-bulk-create--tạo-nhiều-task-từ-template)
4. [Danh mục lệnh Quản trị Hệ thống (Admin Only)](#4-danh-mục-lệnh-quản-trị-hệ-thống-admin-only)
   - [4.1. Lệnh `/link-user` — Liên kết tài khoản cá nhân](#41-lệnh-link-user--liên-kết-1-tài-khoản)
   - [4.2. Lệnh `/link-batch` — Liên kết hàng loạt](#42-lệnh-link-batch--liên-kết-danh-sách-hàng-loạt)
   - [4.3. Lệnh `/sync-team` — Đồng bộ danh bạ `team.yaml`](#43-lệnh-sync-team--đồng-bộ-toàn-bộ-danh-bạ)
5. [Cơ chế Nhắc hẹn tự động (Automated Reminders)](#5-cơ-chế-nhắc-hẹn-tự-động)
6. [Xử lý sự cố thường gặp (Troubleshooting)](#6-xử-lý-sự-cố-thường-gặp)

---

## 1. GIỚI THIỆU & QUY TRÌNH HOẠT ĐỘNG

SEE-Notion Bot là trợ lý AI tích hợp trong Discord, giúp kết nối tự động giữa giao tiếp hàng ngày của CLB và không gian dữ liệu công việc trên Notion.

### Chu trình Xác nhận 2 bước an toàn (Preview ➔ Confirm):
Khi bạn ra lệnh thay đổi dữ liệu (tạo task, cập nhật, hoàn thành), bot không tự ý ghi đè ngay mà tuân thủ quy trình:
1. **Phân tích lệnh**: Bot trích xuất thông tin (Tên task, Người làm, Hạn chót, Độ ưu tiên).
2. **Hiển thị Card Xem trước (Preview)**: Kèm theo các cảnh báo (nếu có) và 2 nút bấm: `[Xác nhận ✅]` và `[Hủy ❌]`.
3. **Thực thi**: Chỉ người gọi lệnh mới bấm được nút xác nhận (hạn xác nhận trong vòng 10 phút / 600 giây). Khi bấm xác nhận, task sẽ được đẩy lên Notion và gửi email thông báo cho người nhận việc.

---

## 2. NGUYÊN TẮC PHÂN QUYỀN (RBAC)

Để đảm bảo tính toàn vẹn và trách nhiệm trong công việc, hệ thống áp dụng cơ chế phân quyền:

* **Admin**:
  - Có toàn quyền tạo, sửa, dời hạn, hoàn thành hoặc archive **tất cả** các task trong không gian Notion.
  - Sử dụng các lệnh cấu hình danh bạ: `/link-user`, `/link-batch`, `/sync-team`.
* **Member (Thành viên)**:
  - Được quyền tạo task mới.
  - Tra cứu các task đang mở của bản thân qua `/my`.
  - **Chỉ được sửa hoặc đánh dấu hoàn thành (`/update`, `/complete`) đối với:**
    1. Task do chính mình tạo ra; HOẶC
    2. Task mà mình được phân công (Assignee).
  - *Nếu cố tình sửa task của người khác, bot sẽ từ chối và báo lỗi bảo mật: `🔒 Bạn chỉ có quyền cập nhật task do mình tạo hoặc được assign.`*

---

## 3. DANH MỤC LỆNH THAO TÁC TASK

### 3.1. Lệnh `/create` — Tạo task mới
Dùng để tạo một công việc mới trên Notion Database với đầy đủ thông tin chuẩn hóa.

* **Tham số**:
  - `name` *(Bắt buộc)*: Tên hoặc mô tả ngắn gọn công việc (Ví dụ: `Làm slide báo cáo tiến độ tuần 4`).
  - `due_date` *(Bắt buộc)*: Hạn chót cần hoàn thành. Hỗ trợ định dạng `dd/mm/yyyy` hoặc từ khóa tự nhiên như `thứ 6`, `ngày mai`, `30/11`.
  - `assignees` *(Tùy chọn)*: Tên người thực hiện, cách nhau bằng dấu phẩy (Ví dụ: `Minh, Quý, Dung`).
  - `priority` *(Tùy chọn)*: Độ ưu tiên (`Urgent`, `High`, `Medium`, `Low`). Mặc định: `Medium`.
  - `task_type` *(Tùy chọn)*: Loại công việc (`Core`, `Support`, `Management`).
  - `effort` *(Tùy chọn)*: Mức độ ước lượng thời gian (`Quick <1h`, `Short 1-3h`, `Medium 3-6h`, `Long >6h`).
  - `description` *(Tùy chọn)*: Ghi chú hoặc link tài liệu đính kèm.

* **Ví dụ thực tế**:
  ```text
  /create name: Hoàn thiện video recap Workshop due_date: 25/11/2026 assignees: Quý, Dung priority: High
  ```

---

### 3.2. Lệnh `/my` — Tra cứu task của tôi
Hiển thị danh sách tối đa 15 công việc đang ở trạng thái mở (`Not started`, `In progress`, `Blocked`) được phân công cho tài khoản của bạn.

* **Tham số**: Không có tham số.
* **Cách dùng**:
  ```text
  /my
  ```
* **Kết quả trả về**:
  ```text
  Task đang mở của bạn (2):
  • TSK-012: Viết content truyền thông sự kiện — In progress, deadline 2026-11-20
  • TSK-015: Chuẩn bị backdrop in ấn — Not started, deadline 2026-11-25
  ```

---

### 3.3. Lệnh `/update` — Cập nhật task
Hỗ trợ thay đổi deadline, người phụ trách, hoặc trạng thái công việc bằng **ngôn ngữ tự nhiên**.

* **Tham số**:
  - `text` *(Bắt buộc)*: Câu lệnh cập nhật bằng tiếng Việt tự nhiên.
* **Các mẫu câu thông dụng**:
  - *Dời hạn chót*: `/update text: Dời deadline TSK-012 sang ngày 28/11`
  - *Giao thêm người*: `/update text: Assign thêm Quý và Dung vào task slide báo cáo`
  - *Đổi trạng thái*: `/update text: Chuyển task TSK-005 sang In progress`

---

### 3.4. Lệnh `/complete` — Hoàn thành task
Đánh dấu một hoặc nhiều công việc sang trạng thái `Done`.

* **Cách 1: Gõ trực tiếp mã task**:
  ```text
  /complete text: TSK-012
  ```
  *(Bot sẽ tạo card xác nhận đóng task TSK-012).*

* **Cách 2: Chọn từ danh sách (Bỏ trống tham số `text`)**:
  ```text
  /complete
  ```
  *(Bot sẽ mở một Select Menu tương tác liệt kê các task bạn đang phụ trách. Bạn có thể chọn 1 hoặc nhiều task cùng lúc để hoàn thành).*

---

### 3.5. Lệnh `/bulk-create` — Tạo nhiều task từ template
Tính năng cực mạnh giúp chuyển đổi biên bản cuộc họp (Meeting Minutes) hoặc bảng kế hoạch công việc thành hàng loạt task Notion trong vài giây.

* **Tham số**:
  - `file` *(Khuyên dùng)*: Đính kèm file văn bản Word `.docx`, file `.csv` hoặc file `.txt`.
  - `text` *(Tùy chọn)*: Dán trực tiếp nội dung văn bản nếu không dùng file.
  - `format`: Định dạng nội dung (`Meeting Minutes` hoặc `CSV`).
  - `layout`: Kiểu bảng (`Tự động`, `Layout 1 — 5 cột`, `Layout 2 — 6 cột`).

* **Quy chuẩn bảng Action Items trong Biên bản họp**:
  Để bot nhận diện chuẩn xác nhất, bảng trong file Word hoặc CSV nên có các cột:
  | Task / Việc cần làm | Người làm (Assignee) | Deadline | Priority |
  |---|---|---|---|
  | Đặt phòng hội thảo B102 | Hân | 22/11/2026 | High |
  | Mua quà cho diễn giả | Ánh | 24/11/2026 | Medium |

---

## 4. DANH MỤC LỆNH QUẢN TRỊ HỆ THỐNG (ADMIN ONLY)

### 4.1. Lệnh `/link-user` — Liên kết 1 tài khoản
Dùng khi một thành viên mới tham gia Discord và cần kích hoạt để nhận tin nhắn DM nhắc hạn hoặc tự gõ lệnh bot.

* **Tham số**:
  - `target` *(Bắt buộc)*: Tag `@User` nếu bạn đó đã ở trong Server HOẶC paste Discord User ID (chuỗi 17-19 chữ số).
  - `email` *(Bắt buộc)*: Email sinh viên VGU (`@student.vgu.edu.vn`). *Có tính năng tự động gợi ý danh sách khi gõ!*
* **Ví dụ**:
  ```text
  /link-user target: @Phạm Trọng Quý email: 104240232@student.vgu.edu.vn
  ```
  *Hệ thống sẽ cập nhật ngay vào SQLite và tự động lưu vào file `team.yaml`.*

---

### 4.2. Lệnh `/link-batch` — Liên kết danh sách hàng loạt
Khi bạn có danh sách Discord ID của nhiều bạn cùng lúc.

* **Tham số**: `text` (Nhập mỗi người 1 dòng theo định dạng `<email> <discord_id hoặc @mention>`).
* **Ví dụ nhập liệu**:
  ```text
  /link-batch text:
  104240232@student.vgu.edu.vn 661748766990270465
  10426079@student.vgu.edu.vn @Nguyễn Minh Thảo Nguyên
  105240380@student.vgu.edu.vn 351176931997384704
  ```

---

### 4.3. Lệnh `/sync-team` — Đồng bộ toàn bộ danh bạ
* **Khi nào sử dụng**: Bất cứ khi nào Admin chỉnh sửa thủ công file `team.yaml` trên máy chủ (thêm người mới, đổi role, sửa Notion ID), bạn không cần restart máy chủ.
* **Cách dùng**:
  ```text
  /sync-team
  ```
* **Kết quả**: Bot đọc lại toàn bộ file, cập nhật bộ nhớ đệm và cơ sở dữ liệu chỉ trong **0.05 giây**.

---

## 5. CƠ CHẾ NHẮC HẸN TỰ ĐỘNG (AUTOMATED REMINDERS)

Hệ thống tích hợp tiến trình chạy ngầm quét kiểm tra hạn chót mỗi **5 phút**:

* **Các mốc thời gian nhắc việc**:
  - `before_3d`: Nhắc nhở trước hạn chót 3 ngày.
  - `before_1d`: Nhắc nhở trước hạn chót 1 ngày.
  - `due_today`: Thông báo khẩn vào đúng ngày đến hạn.
  - `overdue_1d` & `overdue_3d`: Cảnh báo quá hạn công việc.
* **Kênh gửi thông báo**:
  - **Discord DM**: Gửi tin nhắn riêng trực tiếp đến tài khoản Discord của người phụ trách.
  - **Email sinh viên**: Gửi email thông báo chính thức đến hộp thư VGU.
* **Chống làm phiền (Deduplication)**: Mỗi mốc nhắc nhở chỉ được gửi đúng **1 lần duy nhất** cho mỗi thành viên nhờ khóa chống trùng `(task_id, rule_key, due_date)`.

---

## 6. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

| Hiện tượng | Nguyên nhân | Cách khắc phục |
|---|---|---|
| `🔒 Bạn chưa có trong danh bạ team...` | Tài khoản Discord của bạn chưa được liên kết với email sinh viên trong hệ thống. | Nhờ Admin dùng lệnh `/link-user @bạn <email_vgu>` để liên kết tài khoản. |
| `🔒 Bạn chỉ có quyền cập nhật task do mình tạo hoặc được assign.` | Bạn đang cố sửa hoặc hoàn thành task thuộc về người khác (Vi phạm RBAC). | Chỉ người tạo hoặc người nhận task mới có quyền thao tác trên task đó. |
| `⚠️ Chưa thể tạo task vì assignee chưa được map với Notion` | Thành viên nhận việc chưa tham gia Workspace Notion hoặc chưa có `notion_user_id`. | Mời thành viên đó vào Workspace Notion của CLB, sau đó Admin cập nhật ID vào `team.yaml` và gõ `/sync-team`. |
| Gõ lệnh bot không thấy phản hồi | Bot bị mất kết nối mạng hoặc token Discord hết hạn. | Kiểm tra log trên máy chủ: `python -m app.main` hoặc kiểm tra trạng thái Alwaysdata. |
