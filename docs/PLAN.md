# PLAN — Mowftee

## 1. Thông tin tài liệu

- **Dự án:** Mowftee
- **Nền tảng chính:** CachyOS, Hyprland, Btrfs
- **Trạng thái:** Đã hoàn thành khảo sát phần cứng; chưa cài runtime LLM
- **Mục tiêu release:** `v1.0.0`
- **Ngôn ngữ tương tác chính:** Tiếng Việt
- **Nguyên tắc:** Hoàn thành, kiểm thử, ghi log và commit từng bước trước khi chuyển tiếp

---

## 2. Danh tính dự án

- **Tên chính thức:** Mowftee
- **Cách đọc chính thức:** Maou-ph-ti
- **Tên repository dự kiến:** `mowftee`
- **Tên Python package dự kiến:** `mowftee`
- **Lệnh CLI dự kiến:** `mowftee`
- **Tên systemd service dự kiến:** `mowftee.service`
- **Tiền tố biến môi trường:** `MOWFTEE_`

Tên Mowftee phải được dùng đồng bộ trong code, cấu hình, service, log, tài liệu và giao diện.

---

## 3. Mục tiêu dự án

Xây dựng Mowftee — một AI companion chạy local — có phong cách trò chuyện tự nhiên và nhân cách riêng, lấy cảm hứng từ mô hình AI VTuber nhưng không sao chép tên, giọng, avatar hoặc tài sản của Neuro-sama.

Hệ thống cuối cùng cần có:

1. Hội thoại văn bản tiếng Việt.
2. Persona ổn định và có thể chỉnh sửa.
3. Trí nhớ dài hạn có thể xem, sửa, xóa và backup.
4. Nhận giọng nói tiếng Việt.
5. Tổng hợp giọng nói.
6. Hỗ trợ ngắt lời trong hội thoại thời gian thực.
7. Tool hỗ trợ CachyOS/Linux theo allowlist.
8. Avatar có trạng thái nghe, nghĩ, nói và biểu cảm.
9. Logging, benchmark, backup và restore.
10. Có thể dựng lại sau khi cài lại Linux.

---

## 4. Ngoài phạm vi

Các nội dung sau không thuộc phạm vi ban đầu:

- Train LLM từ đầu.
- Sao chép Neuro-sama, giọng nói, avatar hoặc thương hiệu của người khác.
- Đổi tên sản phẩm, package, CLI hoặc service mà không có migration và quyết định kỹ thuật mới.
- Cho AI chạy shell tùy ý.
- Tự động dùng `sudo`, xóa dữ liệu hoặc chỉnh bootloader.
- Mở API AI ra Internet ở các giai đoạn đầu.
- Đồng bộ toàn bộ hội thoại cá nhân lên GitHub.
- Chạy model lớn vượt khả năng RTX 3050 4 GB.
- Triển khai microservice, Kubernetes hoặc Docker khi chưa có nhu cầu thực tế.

---

## 5. Baseline phần cứng đã xác nhận

| Thành phần | Giá trị |
|---|---|
| Máy | ASUS TUF Gaming F15 FX507ZC4 |
| CPU | Intel Core i5-12500H, 12 nhân, 16 luồng |
| GPU | NVIDIA GeForce RTX 3050 Mobile, 4 GB VRAM |
| iGPU | Intel Iris Xe |
| RAM | 16 GB |
| Swap | ZRAM khoảng 15.24 GB, zstd |
| Ổ đĩa | NVMe 476.94 GiB |
| Btrfs đang dùng | Phân vùng 300 GiB |
| Dung lượng Btrfs còn trống | Khoảng 283–284 GiB |
| Desktop | Hyprland trên Wayland |
| Audio | PipeWire + WirePlumber |
| Python hệ thống | 3.14.6 |
| Git | 2.55.0 |
| Ollama | Chưa cài |
| NVIDIA driver | 610.57.04 |
| CUDA UMD | 13.3 |

Thông số chi tiết nằm trong `config/hardware-baseline.txt`.

---

## 6. Kiến trúc tổng quan

```text
Keyboard / Microphone
          │
          ▼
      Input Layer
    ├── Text input
    ├── VAD
    └── STT
          │
          ▼
 Conversation Manager
    ├── Persona Manager
    ├── Context Manager
    ├── Memory Provider
    ├── State Machine
    ├── Safety Layer
    └── Tool Manager
          │
          ▼
      LLM Provider
          │
          ├── Text output
          ├── TTS Provider
          └── Avatar Bridge
```

Kiến trúc ban đầu là **modular monolith**: một ứng dụng Python, các module tách rõ interface nhưng chưa tách thành nhiều service.

---

## 7. Quy tắc kiến trúc

1. Mỗi engine phải thay thế được qua provider/interface.
2. Không hard-code model, đường dẫn hoặc tham số máy trong logic.
3. Module lỗi phải hạ cấp chức năng thay vì làm sập toàn hệ thống.
4. Tool Linux phải có schema, allowlist, timeout và audit log.
5. Không truyền trực tiếp văn bản người dùng vào shell.
6. Mọi dữ liệu cá nhân nằm ngoài Git.
7. Model công khai tải lại được không cần backup bắt buộc.
8. Model tự fine-tune và voice tự tạo phải backup.
9. Mỗi thay đổi lớn phải có quyết định kỹ thuật trong Decision Log.
10. Chỉ tối ưu sau khi có benchmark; không tối ưu theo cảm tính.

---

## 8. Bố trí dữ liệu

### 8.1 Source code

```text
$HOME/Projects/mowftee/
```

### 8.2 Cấu hình người dùng

```text
$HOME/.config/mowftee/
```

### 8.3 Dữ liệu cần giữ

```text
$HOME/.local/share/mowftee/
├── memory/
├── conversations/
├── voices/
└── user-data/
```

### 8.4 Log và benchmark

```text
$HOME/.local/state/mowftee/
├── logs/
├── audit/
└── benchmarks/
```

### 8.5 Cache

```text
$HOME/.cache/mowftee/
```

### 8.6 Model tải lại được

Đường dẫn ưu tiên:

```text
/srv/mowftee/models/ollama/
```

Lý do:

- `/srv` đã là subvolume Btrfs riêng `@srv`.
- Tránh để model lớn nằm trực tiếp trong root subvolume `@`.
- Dễ tách khỏi snapshot hệ thống.
- Dễ cấp quyền cho service Ollama.

Trước khi dùng phải xác minh chính sách snapshot hiện tại có bao gồm `@srv` hay không. Nếu `@srv` bị snapshot thường xuyên, tạo child subvolume riêng cho model.

---

## 9. Ngân sách tài nguyên ban đầu

Các giá trị dưới đây là mục tiêu, chưa phải kết quả benchmark.

### 9.1 LLM

| Chỉ số | Mục tiêu |
|---|---:|
| Quy mô model khởi đầu | 3B–4B, quantized |
| Context ban đầu | 4096 token |
| Time to first token | ≤ 4 giây |
| Tốc độ sinh | ≥ 10 token/giây |
| Phiên kiểm thử | 50 lượt không crash |
| VRAM | Không OOM |
| RAM trống tối thiểu khi chạy | 3 GB |
| Thời gian chạy ổn định | 60 phút |

### 9.2 Voice

| Chỉ số | Mục tiêu |
|---|---:|
| Phát hiện bắt đầu nói | ≤ 250 ms |
| Phát hiện kết thúc nói | 400–900 ms |
| STT câu ngắn | ≤ 2 giây |
| TTS bắt đầu phát | ≤ 1.5 giây |
| Dừng TTS khi ngắt lời | ≤ 300 ms |
| Tổng độ trễ cảm nhận | ≤ 4 giây |

### 9.3 Phân bổ dự kiến

- **RTX 3050:** ưu tiên LLM.
- **CPU:** STT vòng đầu, VAD, TTS nhẹ, memory và tool.
- **Intel Iris Xe:** desktop/Hyprland; avatar có thể ưu tiên iGPU nếu phần mềm cho phép.
- **ZRAM:** chỉ là vùng đệm khi thiếu RAM, không được xem là RAM thay thế cho model lớn.

---

## 10. Cổng hoàn thành chung

Mỗi giai đoạn phải đạt đủ:

- **G1 — Functional:** chức năng hoạt động.
- **G2 — Test:** bộ kiểm thử đạt.
- **G3 — Performance:** chỉ số được đo và đạt hoặc có giải thích.
- **G4 — Stability:** không còn lỗi nghiêm trọng chưa xử lý.
- **G5 — Documentation:** tài liệu đã cập nhật.
- **G6 — Version control:** đã commit; release quan trọng có tag.

---

# 11. Lộ trình triển khai

## Giai đoạn 0 — Nền móng dự án (`v0.0.x`)

### Mục tiêu

Chuẩn hóa repo, môi trường, dữ liệu, log, backup và khả năng tái tạo trước khi viết lõi AI.

### Phụ thuộc

Không có.

### Bước G0-01 — Thu thập baseline

- **Trạng thái:** Hoàn thành.
- **Đầu vào:** CachyOS đang chạy.
- **Đầu ra:** `config/hardware-baseline.txt`.
- **Kiểm tra:** file chứa CPU, GPU, RAM, Btrfs, audio và package.
- **Rollback:** Không cần.

### Bước G0-02 — Tạo repository và cấu trúc tối thiểu

- **Trạng thái:** Hoàn thành.

Quy ước định danh bắt buộc:

```text
Product     : Mowftee
Pronounce   : Maou-ph-ti
Repository  : mowftee
Package     : mowftee
CLI         : mowftee
Service     : mowftee.service
Config path : ~/.config/mowftee
Data path   : ~/.local/share/mowftee
State path  : ~/.local/state/mowftee
Cache path  : ~/.cache/mowftee
Model path  : /srv/mowftee/models/ollama
```

Tạo:

```text
mowftee/
├── src/
├── prompts/
├── config/
├── tests/
├── scripts/
├── docs/
├── pyproject.toml
├── .gitignore
├── LICENSE
└── README.md
```

Tiêu chí hoàn thành:

- Repo Git `mowftee` hoạt động.
- Không có dữ liệu cá nhân trong staging.
- Commit đầu tiên được tạo.
- Remote GitHub chỉ thêm sau khi kiểm tra `.gitignore`.

Kết quả:

- Repository cục bộ và nhánh `main` hoạt động.
- Cấu trúc tối thiểu, `.gitignore`, `pyproject.toml` và `LICENSE` đã có.
- Python version, build backend và dependency được để lại cho G0-03.
- Không có model, memory, secret, audio cá nhân hoặc runtime log trong staging.

### Bước G0-03 — Chốt môi trường Python

- **Trạng thái:** Hoàn thành.

Yêu cầu:

- Không cài package AI trực tiếp vào Python hệ thống.
- Tạo virtual environment riêng.
- Khóa phiên bản Python dùng cho project.
- Chọn phiên bản Python sau khi kiểm tra compatibility của dependency.
- Python hệ thống 3.14.6 không mặc định trở thành Python của project.

Đầu ra:

- `pyproject.toml`.
- Lock file.
- Script `scripts/setup-python.sh`.
- `python --version` trong venv được ghi log.

Kết quả:

- Project dùng CPython `>=3.11,<3.12`; môi trường thực tế được kiểm tra với Python 3.11.15.
- `uv` quản lý interpreter, dependency và virtual environment `.venv/`.
- Python hệ thống 3.14.6 không được dùng để cài dependency project.
- Dependency khai báo trong `pyproject.toml`; `uv.lock` được commit.
- Môi trường được tái tạo bằng `uv sync --locked` qua `scripts/setup-python.sh`.
- `uv lock --check`, sync locked, import, pytest và Ruff đều đạt.

### Bước G0-04 — Chốt storage layout

Kiểm tra:

- Chính sách snapshot cho `@`, `@home`, `@srv`.
- Quyền ghi của user/service Ollama.
- Dung lượng trống.
- Có cần child subvolume model hay không.

Đầu ra:

- Đường dẫn model cuối cùng.
- Đường dẫn memory và log.
- Script tạo thư mục và quyền.
- Decision Log cập nhật.

### Bước G0-05 — Thiết lập cấu hình và logging

Tạo:

```text
config/default.yaml
config/example.yaml
config/model-manifest.yaml
```

Log:

```text
app.jsonl
performance.jsonl
audit.jsonl
```

Tiêu chí:

- Cấu hình sai phải báo lỗi rõ.
- Secret không được ghi log.
- Log có timestamp và request ID.

### Bước G0-06 — Thiết lập backup tối thiểu

Backup bắt buộc:

- Config thật.
- Persona.
- Memory.
- Voice/model tự tạo.
- Tài liệu RAG riêng.

Không backup bắt buộc:

- Model Ollama công khai.
- Cache.
- Audio tạm.

Tiêu chí:

- Có `backup.sh`.
- Có `restore.sh`.
- Restore thử vào thư mục tạm thành công.
- Backup SQLite dùng cơ chế nhất quán, không sao chép mù khi database đang ghi.

### Definition of Done Giai đoạn 0

- [x] Có baseline phần cứng.
- [x] Repo và `.gitignore` chuẩn.
- [x] Python environment được khóa.
- [ ] Storage layout được xác minh.
- [ ] Config schema ban đầu.
- [ ] Logging hoạt động.
- [ ] Backup/restore thử thành công.
- [ ] Commit và tag `v0.0.1`.

---

## Giai đoạn 1 — Lõi hội thoại văn bản (`v0.1.x`)

### Mục tiêu

Chat local trong terminal, streaming, giữ ngữ cảnh trong phiên và có benchmark.

### Bước G1-01 — Cài runtime LLM

Ứng viên mặc định: Ollama.

Kiểm tra:

- Service khởi động.
- API chỉ bind local.
- GPU được sử dụng.
- Model path đúng storage layout.
- Sau reboot service vẫn hoạt động theo cấu hình đã chọn.

Rollback:

- Dừng service.
- Gỡ package.
- Xóa override systemd.
- Không xóa model nếu người dùng chưa xác nhận.

### Bước G1-02 — Benchmark model ứng viên

Ứng viên ban đầu:

- Model 3B quantized.
- Model 4B quantized.
- Model dự phòng nhỏ hơn nếu VRAM/RAM không đạt.

Đo:

- Time to first token.
- Token/giây.
- RAM.
- VRAM.
- Chất lượng tiếng Việt.
- Khả năng tuân thủ câu trả lời ngắn.
- Ổn định 20 và 50 lượt.

Không chọn model chỉ dựa trên dung lượng hoặc độ nổi tiếng.

### Bước G1-03 — Viết LLM Provider

Interface tối thiểu:

```text
chat()
stream_chat()
health_check()
get_metrics()
cancel()
```

Tiêu chí:

- Không để code ứng dụng gọi trực tiếp API Ollama ở nhiều nơi.
- Timeout và lỗi kết nối được xử lý.
- Có request ID.
- Có thể đổi provider sau này.

### Bước G1-04 — Conversation Manager

Chức năng:

- System message.
- Lịch sử trong RAM.
- Giới hạn context.
- Lệnh thoát.
- Hủy phản hồi.
- Streaming ra terminal.

### Bước G1-05 — Test và benchmark

- Smoke test 5 phút.
- Functional test 20 lượt.
- Stability test 50 lượt hoặc 60 phút.
- Reboot test.
- Recovery test khi service Ollama bị dừng.

### Definition of Done Giai đoạn 1

- [ ] Chat terminal hoạt động.
- [ ] Streaming hoạt động.
- [ ] Model dùng GPU hoặc có lý do rõ ràng nếu không.
- [ ] 50 lượt không crash.
- [ ] Benchmark được lưu.
- [ ] Không hard-code model/path.
- [ ] Tag `v0.1.0`.

---

## Giai đoạn 2 — Persona và chất lượng hội thoại (`v0.2.x`)

### Mục tiêu

Tạo nhân vật riêng, nhất quán, tự nhiên và không sao chép Neuro-sama.

### Công việc

- Chốt tên nhân vật.
- Viết persona version 1.
- Xưng hô mặc định.
- Quy tắc độ dài.
- Mức tinh nghịch.
- Phản ứng khi không biết.
- Không giả vờ đã chạy tool.
- Few-shot examples.
- Bộ test persona tối thiểu 20 lượt.
- Chống lặp câu cửa miệng.

### Definition of Done

- [ ] Giữ cách xưng hô.
- [ ] Không đổi sang giọng trợ lý doanh nghiệp.
- [ ] Không tự nhận là Neuro-sama.
- [ ] Không bịa ký ức.
- [ ] Điểm persona đạt ngưỡng đã chốt.
- [ ] `persona_version: 1`.
- [ ] Tag `v0.2.0`.

---

## Giai đoạn 3 — Memory (`v0.3.x`)

### Mục tiêu

Nhớ qua nhiều lần khởi động nhưng người dùng vẫn kiểm soát được dữ liệu.

### Thiết kế

```text
Short-term context
Long-term explicit memory
Conversation summaries
Retrieval
```

### Công việc

- SQLite schema.
- Migration.
- Lưu memory có chọn lọc.
- Không tự lưu mọi nội dung.
- Xem memory.
- Sửa memory.
- Xóa memory.
- Export/import.
- Backup/restore.
- Chống trùng lặp.
- Gắn nguồn và thời gian.

### Definition of Done

- [ ] Mở lại ứng dụng vẫn nhớ memory đã chọn.
- [ ] Xem/sửa/xóa được.
- [ ] Restore thành công.
- [ ] Database không vào Git.
- [ ] Migration chạy được.
- [ ] Tag `v0.3.0`.

---

## Giai đoạn 4 — Voice theo lượt (`v0.4.x`)

### Mục tiêu

Micro → STT → LLM → TTS → loa theo từng lượt.

### Công việc

- Kiểm tra và unmute source PipeWire.
- Chọn thiết bị input/output ổn định.
- Benchmark VAD.
- Benchmark STT tiếng Việt.
- Chọn TTS sau kiểm thử phát âm.
- Quản lý audio tạm.
- Fallback sang bàn phím khi STT lỗi.
- Fallback sang text khi TTS lỗi.

### Definition of Done

- [ ] Nhận câu tiếng Việt thông thường.
- [ ] Không kích hoạt liên tục vì tiếng quạt.
- [ ] TTS rõ.
- [ ] 20 lượt voice ổn định.
- [ ] Độ trễ được ghi.
- [ ] Tag `v0.4.0`.

---

## Giai đoạn 5 — Voice thời gian thực (`v0.5.x`)

### Mục tiêu

Phản hồi sớm, có thể ngắt lời và không tự nghe chính mình.

### Công việc

- Streaming LLM sang TTS.
- Sentence chunking.
- Audio queue.
- Barge-in.
- Cancel token generation.
- Echo prevention.
- State machine hoàn chỉnh.
- Xử lý khoảng lặng.

### Definition of Done

- [ ] Ngắt lời ≤ 300 ms theo mục tiêu.
- [ ] Không nói chồng.
- [ ] Không vòng lặp loa → micro.
- [ ] Module voice lỗi không làm sập text chat.
- [ ] Tag `v0.5.0`.

---

## Giai đoạn 6 — Tool Linux (`v0.6.x`)

### Mục tiêu

Hỗ trợ tác vụ thực tế nhưng không có shell tự do.

### Mức quyền

- L0: chỉ chat.
- L1: đọc trạng thái hệ thống.
- L2: mở app/file.
- L3: ghi trong workspace cho phép.
- L4: thay đổi hệ thống; bắt buộc xác nhận.
- L5: cấm.

### Tool đầu tiên

- `get_system_status`
- `get_gpu_status`
- `open_project`
- `find_file`
- `read_document`
- `create_note`

### Yêu cầu

- Schema rõ.
- Validate tham số.
- Timeout.
- Audit log.
- Confirm policy.
- Không retry tool nguy hiểm.
- Không gửi dữ liệu ra ngoài.

### Definition of Done

- [ ] Không có `run_shell(user_input)`.
- [ ] Allowlist hoạt động.
- [ ] Audit log hoạt động.
- [ ] Hành động thay đổi cần xác nhận.
- [ ] Tag `v0.6.0`.

---

## Giai đoạn 7 — Avatar (`v0.7.x`)

### Mục tiêu

Avatar phản ánh trạng thái AI mà không ảnh hưởng mạnh tới LLM.

### Thứ tự

1. PNGTuber.
2. Listening/thinking/speaking state.
3. Lip-sync theo âm lượng.
4. Biểu cảm.
5. Live2D hoặc VRM nếu tài nguyên cho phép.
6. OBS integration nếu cần.

### Definition of Done

- [ ] Trạng thái đúng.
- [ ] Lip-sync hoạt động.
- [ ] Avatar lỗi không làm sập AI Core.
- [ ] Benchmark khi bật/tắt avatar.
- [ ] Tag `v0.7.0`.

---

## Giai đoạn 8 — Tối ưu và ổn định (`v0.8.x`)

### Công việc

- Context trimming.
- Model load/unload.
- Resource policy.
- Crash recovery.
- Log rotation.
- Database maintenance.
- Test sau update package.
- Soak test tối thiểu 4 giờ.
- Đánh giá Btrfs fragmentation dựa trên số liệu.

### Definition of Done

- [ ] Không tăng RAM vô hạn.
- [ ] Không OOM trong cấu hình mặc định.
- [ ] Module recovery đạt.
- [ ] Soak test đạt.
- [ ] Tag `v0.8.0`.

---

## Giai đoạn 9 — Đóng gói và hồi sinh (`v1.0.0`)

### Script bắt buộc

```text
doctor.sh
install-system.sh
setup-python.sh
download-models.sh
benchmark.sh
backup.sh
restore.sh
uninstall.sh
```

### Quy trình phục hồi

```text
Cài CachyOS/Linux
→ clone repo
→ chạy doctor
→ cài dependency
→ tải model theo manifest
→ restore dữ liệu
→ kiểm thử
→ chạy AI
```

### Definition of Done

- [ ] Dựng lại từ hệ thống sạch.
- [ ] Memory khôi phục.
- [ ] Persona và config khôi phục.
- [ ] Model đúng digest/manifest.
- [ ] Không cần dữ liệu ngoài backup đã khai báo.
- [ ] Release `v1.0.0`.

---

## 12. State machine

```text
STARTING
  └── IDLE
       ├── LISTENING
       ├── TRANSCRIBING
       ├── THINKING
       ├── TOOL_RUNNING
       ├── WAITING_CONFIRMATION
       ├── SPEAKING
       ├── INTERRUPTED
       └── ERROR
SHUTTING_DOWN
```

Mỗi trạng thái phải quyết định rõ:

- Micro có hoạt động không.
- TTS có phát không.
- LLM request có thể bị hủy không.
- Tool có được phép chạy không.
- Avatar hiển thị gì.
- Log sự kiện nào.

---

## 13. Logging

### `app.jsonl`

- Startup/shutdown.
- Module load.
- State transition.
- Error/recovery.
- Timeout.

### `performance.jsonl`

- Model.
- Input/output token.
- Time to first token.
- Token/giây.
- Tổng thời gian.
- RAM/VRAM/CPU/GPU.

### `audit.jsonl`

- Tool.
- Tham số đã lọc.
- Quyền.
- Xác nhận.
- Kết quả.
- Mã lỗi.
- Thời lượng.

Không ghi secret hoặc toàn bộ file nhạy cảm.

---

## 14. Backup

| Dữ liệu | Git | Backup riêng | Tải lại được |
|---|---:|---:|---:|
| Source | Có | GitHub | Có |
| Persona | Có | GitHub | Có |
| Config mẫu | Có | GitHub | Có |
| Config thật | Không | Có | Không |
| Memory | Không | Bắt buộc | Không |
| Hội thoại | Không | Tùy chọn | Không |
| Model công khai | Không | Không bắt buộc | Có |
| LoRA tự tạo | Không | Bắt buộc | Không |
| Voice tự tạo | Không | Bắt buộc | Không |
| Cache | Không | Không | Có |
| Secret | Không | Backup mã hóa | Không |

Snapshot cùng ổ không được coi là backup.

---

## 15. Rủi ro chính

| Rủi ro | Cách xử lý |
|---|---|
| VRAM 4 GB không đủ | Model nhỏ hơn, giảm context, CPU offload |
| RAM 16 GB bị áp lực | Unload module, giới hạn context, tránh model lớn |
| Python hệ thống quá mới | Dùng project Python riêng |
| TTS tiếng Việt kém | Benchmark trước khi chốt |
| Micro thu tiếng loa | Barge-in + echo prevention + thiết bị phù hợp |
| Model phình snapshot | Lưu ngoài root snapshot |
| Memory hỏng/mất | Backup nhất quán + restore test |
| Tool gây hại | Schema + allowlist + confirm + audit |
| Update rolling release gây lỗi | Lock dependency, log version, snapshot trước thay đổi lớn |
| Dự án mất ngữ cảnh giữa các chat | Dùng SESSION_PROMPT.md + LOG.md |

---

## 16. Việc cần làm tiếp theo

**Bước hiện tại:** `G0-04 — Chốt storage layout`.

Mục tiêu dự kiến:

1. Kiểm tra chính sách snapshot cho `@`, `@home` và `@srv`.
2. Xác minh quyền ghi dự kiến của user và service Ollama.
3. Kiểm tra dung lượng trống dành cho model.
4. Quyết định có cần child subvolume riêng cho model hay không.
5. Chốt đường dẫn model, memory và log.

Các mục trên mới là kế hoạch; G0-04 chưa được thực hiện.
