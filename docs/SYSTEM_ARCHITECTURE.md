# SYSTEM ARCHITECTURE — Mowftee

## 1. Project identity

| Thuộc tính | Giá trị |
|---|---|
| Product name | Mowftee |
| Official pronunciation | Maou-ph-ti |
| Repository | `mowftee` |
| Python package | `mowftee` |
| CLI command | `mowftee` |
| systemd service | `mowftee.service` |
| Environment prefix | `MOWFTEE_` |

Mowftee là tên duy nhất được dùng cho sản phẩm và các định danh kỹ thuật.

---

## 2. Trạng thái tài liệu

- **Architecture status:** Proposed and partially validated
- **Hardware baseline:** Validated
- **LLM runtime:** Not installed
- **Default model:** Not selected
- **Voice stack:** Not selected
- **Current project phase:** Giai đoạn 0

---

## 3. Hardware

### 3.1 Máy

- Vendor: ASUSTeK
- Model: ASUS TUF Gaming F15 FX507ZC4
- Firmware: FX507ZC4.312
- Firmware date: 2024-12-03

### 3.2 CPU

- Model: Intel Core i5-12500H
- Architecture: Alder Lake
- Physical cores: 12
- Threads: 16
- P-core/E-core topology: 4 performance cores có SMT và 8 efficiency cores
- Maximum frequency: 4.5 GHz
- L3 cache: 18 MiB
- AVX2: Có
- Virtualization: VT-x

### 3.3 GPU

#### NVIDIA

- Model: GeForce RTX 3050 Mobile
- Architecture: Ampere GA107M
- VRAM: 4096 MiB
- Driver: 610.57.04
- CUDA UMD: 13.3
- Power limit shown: 90 W
- Baseline VRAM usage: khoảng 15 MiB
- Display attached: Không ở thời điểm baseline

#### Intel

- Model: Iris Xe, Alder Lake-P GT2
- Vai trò hiện tại: desktop/Wayland compositor và màn hình laptop

### 3.4 Memory

- Installed/available class: 16 GB
- `free` reported total: khoảng 15 GiB
- Available tại baseline: khoảng 10 GiB
- ZRAM: khoảng 15.24 GiB
- Compression: zstd
- Swappiness: 150

### 3.5 Storage

- Physical drive: Micron 2400 NVMe 512 GB class
- Reported total: 476.94 GiB
- Btrfs partition: 300 GiB
- Btrfs used: khoảng 15.66 GiB
- Btrfs estimated free: khoảng 283.16 GiB
- EFI partition: 4 GiB

---

## 4. Operating System

- Distribution: CachyOS
- Base: Arch Linux
- Kernel: 7.1.6-1-cachyos
- Init: systemd 261
- Desktop: Hyprland 0.56.1
- Display: Wayland + Xwayland
- Shell: fish 4.8.1
- Audio server: PipeWire 1.6.8
- Session manager: WirePlumber 0.5.15
- Python system: 3.14.6
- Python project: CPython 3.11 (`>=3.11,<3.12`), managed by `uv`
- Git: 2.55.0

### Project Python environment

- Interpreter và dependency của project do `uv` quản lý.
- Virtual environment nằm tại `.venv/` trong repository và không được commit.
- Python hệ thống 3.14.6 không được dùng để cài dependency project.
- Dependency trực tiếp khai báo trong `pyproject.toml`; phiên bản resolve nằm trong `uv.lock` và phải được commit.
- Build backend là Hatchling; wheel lấy package từ `src/mowftee`.
- Tái tạo môi trường bằng `uv sync --locked` hoặc `scripts/setup-python.sh`.

---

## 5. Btrfs layout

| Mount | Subvolume |
|---|---|
| `/` | `@` |
| `/home` | `@home` |
| `/root` | `@root` |
| `/srv` | `@srv` |
| `/var/cache` | `@cache` |
| `/var/tmp` | `@tmp` |
| `/var/log` | `@log` |

Mount options chính:

```text
rw,noatime,compress=zstd:1,ssd,discard=async,space_cache=v2
```

### Kiến trúc lưu trữ đã chốt

```text
/srv/mowftee/models/ollama/         model tải lại được
${XDG_CONFIG_HOME:-$HOME/.config}/mowftee/       config riêng
${XDG_DATA_HOME:-$HOME/.local/share}/mowftee/    memory, conversation, custom voice/LoRA
${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/   log/audit/benchmark
${XDG_CACHE_HOME:-$HOME/.cache}/mowftee/         cache tạm
```

### Lưu ý

- `@srv` là subvolume riêng, phù hợp để tách model khỏi root snapshot.
- Không có Snapper, Timeshift, Btrfs Assistant hoặc timer snapshot; `@srv` hiện không bị snapshot tự động.
- Không tạo child subvolume model khi chưa có snapshot policy cho `@srv`; xem xét lại nếu policy thay đổi.
- Snapshot trên cùng NVMe không phải backup.
- Chưa cần tắt CoW cho SQLite.
- `/srv/mowftee` và `/srv/mowftee/models` là `root:root 0755`.
- `/srv/mowftee/models/ollama` được hoãn tạo đến bước cài runtime; owner cuối cùng là `ollama:ollama`, mode `0750`.
- XDG directories của Mowftee thuộc user hiện tại và dùng mode `0700`.

---

## 6. Audio

- PipeWire: active.
- WirePlumber: active.
- Default sink: Built-in Audio Analog Stereo.
- Default source: Built-in Audio Analog Stereo.
- Default source state tại baseline: muted.
- Webcam USB có V4L2 source, không được xem là microphone mặc định.

Voice stage phải:

1. Xác nhận source chính xác.
2. Unmute source.
3. Ghi sample kiểm tra.
4. Đo noise floor.
5. Chống thu ngược âm thanh từ loa.

---

## 7. Logical architecture

```text
┌─────────────────────────────────────────────┐
│                User Interfaces              │
│ Terminal / GUI / Microphone / Avatar        │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│                 Application Core            │
│ State Machine                               │
│ Conversation Manager                        │
│ Context Manager                             │
│ Persona Manager                             │
│ Safety Layer                                │
└─────────┬────────────┬───────────┬───────────┘
          │            │           │
   ┌──────▼─────┐ ┌────▼────┐ ┌────▼─────────┐
   │LLM Provider│ │ Memory  │ │ Tool Manager │
   └──────┬─────┘ └────┬────┘ └────┬─────────┘
          │            │           │
   ┌──────▼────────────▼───────────▼───────────┐
   │         Voice and Presentation Layer      │
   │ VAD / STT / TTS / Audio Queue / Avatar    │
   └────────────────────────────────────────────┘
```

---

## 8. Provider interfaces

### 8.1 LLM Provider

```text
chat()
stream_chat()
cancel()
health_check()
get_metrics()
```

### 8.2 Memory Provider

```text
store_memory()
retrieve_memory()
list_memories()
update_memory()
delete_memory()
export_memory()
import_memory()
```

### 8.3 STT Provider

```text
transcribe()
stream_transcribe()
health_check()
get_metrics()
```

### 8.4 TTS Provider

```text
synthesize()
stream_synthesize()
stop()
health_check()
get_metrics()
```

### 8.5 Tool Provider

```text
validate()
requires_confirmation()
execute()
cancel()
audit()
```

### 8.6 Avatar Provider

```text
set_state()
set_expression()
set_speaking_level()
health_check()
```

---

## 9. State machine

### Primary states

- `STARTING`
- `IDLE`
- `LISTENING`
- `TRANSCRIBING`
- `THINKING`
- `SPEAKING`
- `SHUTTING_DOWN`

### Secondary/error states

- `INTERRUPTED`
- `TOOL_RUNNING`
- `WAITING_CONFIRMATION`
- `ERROR`

### Critical invariants

1. Không có hai TTS stream phát đồng thời.
2. Khi barge-in được kích hoạt, TTS dừng và LLM request cũ bị hủy.
3. Tool thay đổi hệ thống không chạy khi chưa xác nhận.
4. Avatar lỗi không làm đổi state của AI Core sang crash.
5. Memory lỗi chuyển sang in-memory session.
6. STT lỗi chuyển sang keyboard input.
7. TTS lỗi vẫn hiện text output.

---

## 10. Resource allocation

### Giai đoạn text

- RTX 3050: LLM.
- CPU: application core, logging, context.
- RAM: model spill/context/cache.
- iGPU: desktop.

### Giai đoạn voice

- RTX 3050: ưu tiên LLM.
- CPU: VAD, STT ban đầu, TTS nhẹ.
- iGPU: desktop và avatar nếu hỗ trợ.
- Không chạy đồng thời model LLM lớn, STT GPU nặng và avatar nặng trong cấu hình mặc định.

### Safe resource policy

- Nếu RAM available < 3 GB: giảm context, dừng preload voice hoặc unload module không cần.
- Nếu GPU OOM: giảm model/context hoặc chuyển một phần sang CPU.
- Không dựa vào ZRAM để chạy model vượt cấu hình.
- Log RAM/VRAM theo request benchmark.

---

## 11. Data architecture

### Git-tracked

- Source code.
- Persona.
- Prompt examples.
- Config mặc định.
- Model manifest không chứa secret.
- Test prompts.
- Documentation.
- Migration.

### Not tracked

- `config/local.yaml`
- `.env`
- Memory database.
- Conversation archive.
- Audio cá nhân.
- Downloaded models.
- Generated voice files.
- Runtime logs.
- API key/token.

### Database

- Engine dự kiến: SQLite.
- Journaling mode: quyết định khi triển khai.
- Schema version riêng.
- Migration bắt buộc.
- Backup bằng SQLite-consistent method.
- Không dùng `cp` mù khi database đang ghi.

---

## 12. Security boundaries

### Permission levels

| Level | Ý nghĩa |
|---|---|
| L0 | Hội thoại |
| L1 | Đọc trạng thái |
| L2 | Mở app/file |
| L3 | Ghi trong workspace |
| L4 | Thay đổi hệ thống, bắt buộc xác nhận |
| L5 | Cấm |

### Bị cấm mặc định

- `run_shell(user_input)`
- Tự gọi `sudo`
- Tự xóa file
- Tự sửa bootloader
- Tự sửa firewall
- Tự đọc secret
- Tự gửi file ra Internet
- Tự thực hiện lại tool nguy hiểm sau lỗi

### Network

- LLM API chỉ bind loopback trong các giai đoạn đầu.
- Không mở ra LAN/Internet trước authentication review.
- Tool network phải khai báo rõ destination và dữ liệu gửi.

---

## 13. Logging architecture

### `app.jsonl`

- Lifecycle.
- State transition.
- Error.
- Recovery.
- Timeout.

### `performance.jsonl`

- Model identifier.
- Input/output tokens.
- Time to first token.
- Throughput.
- Total duration.
- RAM/VRAM/CPU/GPU.

### `audit.jsonl`

- Tool ID.
- Sanitized parameters.
- Permission level.
- Confirmation result.
- Execution result.
- Duration.
- Error code.

---

## 14. Model architecture — Proposed

### LLM

- Runtime candidate: Ollama.
- Fallback runtime: llama.cpp server.
- Model class: 3B–4B quantized.
- Context initial target: 4096.
- Default model: chưa chọn.
- Selection method: fixed benchmark.

### STT

- Candidate class: whisper.cpp compatible model.
- Execution target: CPU first.
- Default model: chưa chọn.
- Language focus: Vietnamese with technical English terms.

### VAD

- Candidate: integrated VAD or Silero-class VAD.
- Default: chưa chọn.

### TTS

- Default: chưa chọn.
- Must pass Vietnamese pronunciation benchmark.
- Must support low start latency or chunked synthesis.

### Memory

- SQLite.
- Long-term memory is explicit/selective.
- Conversation summaries are separate from user facts.

### Avatar

- First: PNGTuber state integration.
- Later: Live2D or VRM after resource benchmark.

---

## 15. Decision Log

### DEC-001 — Tên và định danh Mowftee

- **Context:** Dự án cần một danh tính riêng trước khi tạo repository.
- **Decision:** Dùng Mowftee, đọc là Maou-ph-ti.
- **Technical identifiers:** `mowftee`, `mowftee.service`, `MOWFTEE_`.
- **Reason:** Đồng bộ giữa sản phẩm, package, CLI, service và đường dẫn.
- **Revisit when:** Chỉ thay đổi qua migration và quyết định kiến trúc mới.

### DEC-002 — Modular monolith

- **Context:** Máy cá nhân, dự án một người, cần debug dễ.
- **Decision:** Dùng modular monolith.
- **Reason:** Ít overhead, dễ chạy và vẫn thay engine qua provider.
- **Revisit when:** Một module cần lifecycle hoặc tài nguyên độc lập.

### DEC-003 — Không train LLM từ đầu

- **Context:** RTX 3050 4 GB, RAM 16 GB.
- **Decision:** Dùng model pretrained quantized.
- **Reason:** Phù hợp tài nguyên và mục tiêu.
- **Revisit when:** Có phần cứng/cloud và nhu cầu nghiên cứu riêng.

### DEC-004 — Ollama là runtime đầu tiên

- **Context:** Cần quản lý model và API local đơn giản.
- **Decision:** Benchmark Ollama trước.
- **Fallback:** llama.cpp server.
- **Revisit when:** VRAM control, latency hoặc compatibility không đạt.

### DEC-005 — Model nằm ngoài repository

- **Context:** Model lớn, tải lại được.
- **Decision:** Không push model lên Git.
- **Preferred path:** `/srv/mowftee/models/ollama/`.
- **Revisit when:** Snapshot policy của `@srv` không phù hợp.

### DEC-006 — Không tắt CoW cho SQLite ở đầu dự án

- **Context:** Chưa có số liệu chứng minh vấn đề.
- **Decision:** Giữ cấu hình Btrfs mặc định.
- **Reason:** Tránh tối ưu sớm và giảm khả năng snapshot/reflink.
- **Revisit when:** Benchmark cho thấy fragmentation/write amplification đáng kể.

### DEC-007 — Tool không có shell tự do

- **Context:** AI có thể sinh lệnh sai.
- **Decision:** Tool theo schema và allowlist.
- **Reason:** An toàn và audit được.
- **Revisit when:** Không xem xét shell tự do; chỉ mở rộng tool cụ thể.

### DEC-008 — Python project tách khỏi Python hệ thống

- **Context:** Python hệ thống là 3.14.6 trên rolling release.
- **Decision:** Dùng CPython 3.11 (`>=3.11,<3.12`) do `uv` quản lý trong `.venv/`; khóa dependency bằng `uv.lock` và sync bằng `uv sync --locked`.
- **Build backend:** Hatchling với layout `src/mowftee`.
- **Reason:** Tách project khỏi Python 3.14.6 của CachyOS rolling release và giữ compatibility rộng cho các module LLM, STT và TTS dự kiến.
- **Validated with:** CPython 3.11.15, `uv lock --check`, locked sync, import smoke test, pytest và Ruff.
- **Revisit when:** Dependency AI đã chọn yêu cầu Python khác hoặc CPython 3.11 hết thời gian hỗ trợ phù hợp với dự án.

### DEC-009 — Storage layout theo XDG và `@srv`

- **Context:** Source, dữ liệu cá nhân và public model có yêu cầu quyền, snapshot và backup khác nhau.
- **Decision:** Dùng XDG paths portable cho config/data/state/cache; public Ollama model nằm tại `/srv/mowftee/models/ollama` trên `@srv`.
- **Snapshot:** `@srv` hiện không bị snapshot tự động; không tạo child subvolume model. Public model và cache không cần snapshot hoặc backup.
- **Backup:** Memory, private config, custom voice và LoRA bắt buộc backup ngoài máy; triển khai ở G0-06. Conversation history là dữ liệu nhạy cảm và backup tùy chọn theo chính sách người dùng.
- **Permissions:** XDG directories là `0700` của user; model directory cuối cùng là `ollama:ollama 0750`.
- **Deferred action:** Chỉ tạo `/srv/mowftee/models/ollama` sau khi user/group Ollama tồn tại ở bước cài runtime.
- **Rollback:** Dừng ứng dụng/service, chuyển dữ liệu bằng công cụ bảo toàn metadata, cập nhật config rồi xác minh trước khi xóa đường dẫn cũ. Không xóa public model nếu chưa có xác nhận.
- **Revisit when:** Bật snapshot cho `@srv`, thay đổi service account hoặc chuyển model sang filesystem khác.

---

## 16. Recovery architecture

### Có thể tải lại

- Ollama/runtime.
- Public LLM.
- Public STT/TTS model.
- Python packages.
- Source từ GitHub.

### Phải backup

- Memory database.
- Config thật.
- Persona chưa push.
- RAG data.
- LoRA tự tạo.
- Voice/model tự tạo.
- Secret theo dạng mã hóa.

### Recovery sequence

```text
Fresh OS
→ clone Git
→ run doctor
→ install uv
→ run `uv sync --locked`
→ download model manifest
→ restore private data
→ run migrations
→ run tests
→ start application
```
