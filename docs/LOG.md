# LOG — Mowftee

> Nhật ký chỉ thêm mới. Không xóa hoặc viết lại các entry cũ. Khi sửa sai, thêm entry mới giải thích.

---

## 2026-08-06 23:27 +07 — G0-01 Hardware baseline

### Mục tiêu

Thu thập thông số máy trước khi chốt kiến trúc và cài runtime AI.

### Lệnh đã chạy

Script thu thập:

- `inxi -Fza`
- `lscpu`
- `nvidia-smi`
- `free -h`
- `lsblk`
- `df`
- `findmnt`
- `btrfs subvolume list`
- `btrfs filesystem usage`
- `wpctl status`
- kiểm tra Python, Git, Ollama và package liên quan

### Kết quả chính

- Máy: ASUS TUF Gaming F15 FX507ZC4.
- CPU: Intel Core i5-12500H, 12 nhân, 16 luồng.
- GPU: RTX 3050 Mobile, 4096 MiB VRAM.
- GPU baseline: khoảng 15 MiB VRAM được dùng; desktop chủ yếu chạy trên Intel Iris Xe.
- RAM: 15 GiB hiển thị, khoảng 10 GiB available tại thời điểm đo.
- ZRAM: khoảng 15 GiB, gần như chưa dùng.
- Btrfs: 300 GiB; còn khoảng 283–284 GiB.
- Root dùng subvolume `@`.
- `/home`, `/srv`, `/var/cache`, `/var/log`, `/var/tmp` là các subvolume riêng.
- PipeWire và WirePlumber đang hoạt động.
- Source audio mặc định tồn tại nhưng đang mute.
- Python hệ thống: 3.14.6.
- Git: 2.55.0.
- Ollama: chưa cài.
- NVIDIA driver: 610.57.04.
- CUDA UMD: 13.3.

### Đánh giá

Máy phù hợp để xây Mowftee local với model quantized khoảng 3B–4B. Giới hạn chính là VRAM 4 GB và RAM 16 GB. Cần benchmark thực tế trước khi chọn model mặc định.

### Quyết định tạm thời

- GPU ưu tiên LLM.
- STT vòng đầu chạy CPU.
- TTS chọn sau benchmark tiếng Việt.
- Model công khai lưu ngoài repo.
- `/srv/mowftee/models/ollama/` là vị trí model ưu tiên vì `/srv` là subvolume riêng.
- Không tắt CoW cho SQLite ở thời điểm này; chỉ xem xét khi có số liệu phân mảnh hoặc write amplification.
- Không dùng Python hệ thống trực tiếp cho dependency dự án.

### Sự cố / điểm cần xử lý

1. Ollama chưa được cài.
2. Chưa xác minh `@srv` có bị snapshot định kỳ hay không.
3. Micro mặc định đang mute.
4. Chưa có backup ngoài ổ.
5. Python hệ thống 3.14.6 có thể quá mới với một số dependency; cần môi trường project riêng.

### Trạng thái

`G0-01`: **Hoàn thành**.

### Việc tiếp theo

`G0-02`: Tạo repository và cấu trúc tối thiểu.

### Git commit

Chưa có repo tại thời điểm ghi entry này.


---

## 2026-08-06 23:41 +07 — Chốt tên Mowftee

### Mục tiêu

Chọn danh tính chính thức trước khi tạo repository và viết README.

### Quyết định

- Tên chính thức: **Mowftee**.
- Cách đọc chính thức: **Maou-ph-ti**.
- Repository: `mowftee`.
- Python package: `mowftee`.
- CLI: `mowftee`.
- systemd service dự kiến: `mowftee.service`.
- Prefix biến môi trường: `MOWFTEE_`.
- Các đường dẫn XDG và model dùng định danh `mowftee`.

### Lý do

- Gắn với danh tính hiện có của người dùng.
- Có cách đọc riêng và dễ nhận biết.
- Có thể dùng nhất quán cho sản phẩm, code, command và repository.
- Không sử dụng tên, avatar hoặc giọng của một AI khác.

### File đã cập nhật

- `docs/PLAN.md`
- `docs/SESSION_PROMPT.md`
- `docs/LOG.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `config/model-manifest.yaml`

`config/hardware-baseline.txt` được giữ nguyên vì đây là dữ liệu đo thực tế.

### Trạng thái

Tên Mowftee: **Đã chốt**.

### Việc tiếp theo

1. Chép bộ tài liệu vào repo.
2. Gửi link repo.
3. Kiểm tra cấu trúc repo.
4. Viết lại README làm tài liệu dẫn đường.
5. Tiếp tục bước `G0-02`.


---

## 2026-08-07 00:11 +07 — G0-02 Repository và cấu trúc tối thiểu

### Mục tiêu

Hoàn thiện cấu trúc repository tối thiểu mà chưa cài runtime, dependency hoặc tải model.

### Thay đổi

- Tạo `.gitignore` cho Python, secret, config cục bộ, dữ liệu runtime, log, audio và model.
- Tạo `pyproject.toml` chỉ với metadata tối thiểu; chưa chốt Python version, build backend hoặc dependency.
- Tạo package `src/mowftee` và các vị trí `prompts`, `tests`, `scripts` ở mức tối thiểu.
- Tạo `LICENSE` với thông báo bảo lưu quyền; chưa cấp giấy phép mã nguồn mở.
- Cập nhật trạng thái G0-02 trong tài liệu dự án.

### Kiểm tra

- Working tree ban đầu sạch và nhánh `main` đồng bộ với `origin/main`.
- Không có model, memory, secret, audio cá nhân hoặc runtime log trong danh sách thay đổi.
- `git diff --check` không báo lỗi whitespace.
- Không sửa `README.md` hoặc `docs/SYSTEM_ARCHITECTURE.md`.

### Điểm cần xử lý

- Remote hiện có tên repository `bimatnhe`, chưa khớp định danh đã chốt `mowftee`; không tự đổi remote trong G0-02.
- Python version và toolchain tiếp tục được chốt ở G0-03.

### Trạng thái

`G0-02`: **Hoàn thành sau khi commit các thay đổi này**.
