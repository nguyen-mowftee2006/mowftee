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
- **LLM runtime:** Installed & Validated (Ollama 0.32.6-1.1 + ollama-vulkan 0.32.6-1.1 via Vulkan backend on RTX 3050, systemd enabled/active, bind 127.0.0.1:11434)
- **Default model:** `qwen3:4b-instruct` (digest `0edcdef34593`, `Q4_K_M`); Performance fallback: `llama3.2:3b` (digest `a80c4f17acd5`, `Q4_K_M`)
- **LLM Provider:** Implemented & Validated (`OllamaLLMProvider` in `src/mowftee/llm/ollama.py`)
- **Conversation Manager:** Implemented & Validated (`ConversationManager` in `src/mowftee/conversation/manager.py`)
- **Voice stack:** Not selected
- **Current project phase:** Giai đoạn 1 (v0.1.x IN PROGRESS); G1-01, G1-02, G1-03 & G1-04 Complete; bước tiếp theo là G1-05 — Test và benchmark

---

### DEC-015 — Default LLM model selection and performance fallback

- **Context:** Cần lựa chọn mô hình LLM mặc định cho Mowftee dựa trên kết quả thực nghiệm chuẩn hóa (TTFT, tốc độ sinh, khả năng tuân thủ câu lệnh, chất lượng tiếng Việt, suy luận toán/logic, độ ổn định 20 và 50 lượt hội thoại).
- **Decision:**
  1. **Default Selected LLM:** `qwen3:4b-instruct` (digest `0edcdef34593`, `Q4_K_M`, 4.0B parameters).
  2. **Performance Fallback LLM:** `llama3.2:3b` (digest `a80c4f17acd5`, `Q4_K_M`, 3.2B parameters).
- **Reasoning & Empirical Evidence:**
  - `qwen3:4b-instruct`: TTFT streaming ~0.188s (target < 4.0s), tốc độ sinh 50 lượt trung bình 31.95 tok/s, hoàn thành 50/50 lượt (100%), 0 lỗi instruction, 0 lỗi reasoning, 0 lỗi context/recall, 0 hallucination. Chất lượng tiếng Việt tự nhiên và mượt mà nhất.
  - `llama3.2:3b`: TTFT streaming ~0.206s (target < 4.0s), tốc độ sinh 50 lượt trung bình 68.20 tok/s, hoàn thành 50/50 lượt (100%), nhưng gặp 2 lỗi vi phạm định dạng instruction, 1 lỗi suy luận toán học và 1 lỗi safety filter trigger nhầm.
- **Observed Processor Behavior:**
  - `llama3.2:3b` (runner 2.5 GB) duy trì 100% GPU thuần trên VRAM 4GB của RTX 3050.
  - `qwen3:4b-instruct` (runner 3.2 GB) đạt 13%/87% CPU/GPU runner do phình nhẹ 13% CPU tràn từ 2.7 GB VRAM khả dụng.
  - Hành vi processor thay đổi theo kích thước runner, trạng thái session và runner isolation; không khẳng định tất cả các model đều 100% GPU trong mọi tình huống.
- **Scope & Limitations:**
  - `llm.selection_status` semantics: `benchmark_required` khi benchmark/chọn default chưa hoàn tất; `selected` khi benchmark hoàn tất và default model đã được chọn. Policy này áp dụng cho LLM metadata; không tự thay đổi STT/TTS/embedding status.
  - Chưa triển khai cơ chế tự động chuyển đổi fallback (fallback switching mechanism chưa implemented trong codebase).
  - Cấu hình chỉ cập nhật thông số mô hình mặc định và `selection_status: selected` trong manifest.
- **Revisit when:** Thay đổi hardware VRAM, xuất hiện thế hệ model 3B/4B nhỏ hơn hoặc tích hợp tự động switching logic ở G1-03.


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
- PyYAML là runtime dependency cho config YAML; phiên bản resolve hiện tại là 6.0.3 trong `uv.lock`.
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
- `/srv/mowftee/models/ollama` đã được tạo khi cài Ollama; owner `ollama:ollama`, mode `0750`.
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

- User `config.yaml` dưới XDG config path.
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

## 13. Configuration and logging architecture

### 13.1 Configuration

Nguồn cấu hình được merge theo precedence từ thấp đến cao:

```text
config/default.yaml
→ ${XDG_CONFIG_HOME:-$HOME/.config}/mowftee/config.yaml
→ MOWFTEE_ environment overrides
→ CLI overrides dạng mapping
```

- `config/default.yaml` bắt buộc tồn tại và dùng `config_schema_version: 1`.
- Build wheel force-include default YAML thành `mowftee/default.yaml`; loader ưu tiên file source và fallback sang package resource sau khi cài wheel.
- `config/example.yaml` chỉ là tài liệu mẫu, không bao giờ được tự động load làm user config.
- User config là tùy chọn; nếu tồn tại nhưng YAML hoặc giá trị sai thì phải báo `ConfigError`/`ConfigValidationError`, không silently fallback.
- Nested environment key dùng hai dấu gạch dưới, ví dụ `MOWFTEE_LOGGING__LEVEL`; scalar được parse mà không dùng `eval`.
- Merge và sanitize không mutate mapping đầu vào. Exception chỉ nêu path/field liên quan, không dump secret hoặc toàn bộ config.

### 13.2 Logging

Đường dẫn runtime:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/logs/app.jsonl
${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/logs/performance.jsonl
${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/audit/audit.jsonl
```

Mỗi dòng là một JSON object UTF-8 với các field thống nhất: `timestamp`, `level`, `event`, `module`, `request_id`, `session_id`, `message`, `error_type`, `duration_ms`, `metadata`.

- Timestamp là UTC ISO 8601; request ID là UUID được truyền qua `contextvars`.
- Console và file output cấu hình độc lập; file dùng `RotatingFileHandler` chuẩn, mode `0600`, thư mục Mowftee mode `0700`.
- Gọi setup nhiều lần thay thế handler do Mowftee quản lý, không nhân đôi record và không thay đổi root logger.
- Key secret được lọc không phân biệt hoa thường, kể cả nested mapping, collection, URL query và exception metadata.
- Giá trị header `Authorization`, `Cookie`, `Set-Cookie` bị che toàn bộ; chained YAML parser error không được giữ nếu có thể chứa nội dung config.
- Prompt, conversation, file content và audio metadata bị chặn mặc định theo privacy flags.
- Raw audio luôn bị chặn kể cả khi cho phép log audio metadata.
- Nếu tạo file hoặc emit/rotation lỗi, kênh tương ứng fallback sang console và phát diagnostic ngắn, không làm ứng dụng crash.

#### `app.jsonl`

- Lifecycle.
- State transition.
- Error.
- Recovery.
- Timeout.

#### `performance.jsonl`

- Model identifier.
- Input/output tokens.
- Time to first token.
- Throughput.
- Total duration.
- RAM/VRAM/CPU/GPU.

#### `audit.jsonl`

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
- **Backup:** Memory, private config, custom voice và LoRA bắt buộc backup ngoài máy. G0-06A đã triển khai local encrypted staging; G0-06B đã xác minh off-machine backup bằng full cloud round-trip qua Google Drive riêng tư. Conversation history là dữ liệu nhạy cảm và chỉ backup khi người dùng bật tùy chọn.
- **Permissions:** XDG directories là `0700` của user; model directory cuối cùng là `ollama:ollama 0750`.
- **Completed action:** Thư mục `/srv/mowftee/models/ollama` đã được tạo với `ollama:ollama 0750` khi cài Ollama runtime ở G1-01.
- **Rollback:** Dừng ứng dụng/service, chuyển dữ liệu bằng công cụ bảo toàn metadata, cập nhật config rồi xác minh trước khi xóa đường dẫn cũ. Không xóa public model nếu chưa có xác nhận.
- **Revisit when:** Bật snapshot cho `@srv`, thay đổi service account hoặc chuyển model sang filesystem khác.

### DEC-010 — Layered YAML config và privacy-aware JSONL logging

- **Context:** Modular monolith cần một nguồn cấu hình có thể tái tạo nhưng vẫn tách config riêng/secret khỏi Git, cùng logging đủ quan sát mà không mặc định ghi dữ liệu cá nhân.
- **Decision:** Dùng PyYAML cho schema version 1 với precedence default → user config XDG → `MOWFTEE_` environment → CLI mapping; dùng ba kênh JSONL app/performance/audit dưới XDG state path.
- **Validation:** Default config là bắt buộc; user config lỗi không bị bỏ qua; nested merge không mutate input; field sai được báo bằng exception riêng.
- **Privacy:** Redact secret theo key, URL query và toàn bộ authorization/cookie header; prompt, conversation, file content và audio metadata mặc định không được ghi; raw audio luôn bị chặn.
- **Reliability:** UUID request context dùng `contextvars`; rotation dùng thư viện chuẩn; file mode `0600`; setup idempotent và không thay đổi root logger.
- **Fallback:** Lỗi tạo, ghi hoặc rotate file hạ cấp riêng kênh sang console với diagnostic ngắn thay vì làm crash ứng dụng.
- **Validated with:** 39 pytest tests, Ruff, lock/sync check, config/logging smoke test trong XDG tạm và wheel-install smoke test.
- **Revisit when:** Schema cần migration, logging chuyển sang collector bên ngoài hoặc privacy policy có yêu cầu phân loại dữ liệu mới.

---

### DEC-011 — Local encrypted backup/restore trước backup ngoài máy

- **Context:** Dữ liệu riêng cần có định dạng archive, kiểm tra toàn vẹn và quy trình restore an toàn trước khi tích hợp target cloud hoặc thiết bị ngoài.
- **Decision:** G0-06A tạo archive tar gzip mã hóa đối xứng bằng GPG AES-256, sidecar SHA-256 cho ciphertext, manifest và checksum SHA-256 nội bộ cho payload.
- **SQLite:** Database đang mở được snapshot bằng `sqlite3.Connection.backup()`; không sao chép mù file SQLite đang ghi.
- **Restore safety:** Xác minh sidecar, giải mã vào vùng tạm, từ chối path traversal, symlink và special file, kiểm tra manifest/checksum rồi mới publish destination.
- **Privacy:** Manifest không chứa hostname, username hoặc absolute source path.
- **Status:** Archive G0-06A được đánh dấu `local_staging`; archive nằm trên cùng máy chưa phải backup ngoài máy. G0-06B đã xác minh off-machine backup thật qua Google Drive riêng tư.
- **Validation:** Bash syntax, `uv lock --check`, locked sync, Ruff, 45 backup tests, 84 full tests, diff check và wheel smoke test đều đạt.
- **Status:** G0-06B đã hoàn thành full off-machine cloud round-trip và restore validation.

---

### DEC-012 — Off-machine backup target và cloud round-trip validation

- **Context:** Local encrypted staging trên cùng máy/NVMe không phải off-machine backup.
- **Decision:** G0-06B sử dụng Google Drive riêng tư làm off-machine target.
- **Transfer:** upload/download thủ công qua trình duyệt; không dùng Drive API, rclone, OAuth integration, cloud SDK hoặc daemon sync.
- **Không phải off-machine backup:** Btrfs snapshot, directory/partition khác cùng máy hoặc cùng NVMe, repository, GitHub source code và local staging.
- **Encryption:** production archive dùng GPG symmetric AES-256.
- **Passphrase:** đi qua pinentry/gpg-agent; không lưu trong CLI, env, config, Git, log hoặc cloud.
- **Integrity:** ciphertext đi kèm outer SHA-256 sidecar.
- **Validation:** production backup → checksum → local restore sanity test → upload → xóa local original → download → checksum → restore vào temporary destination → đối chiếu restored data.
- **Validated archive:** `mowftee-backup-20260807T072238Z-5dd3acf1.tar.gz.gpg`.
- **Process improvement:** local restore sanity test được thực hiện trước upload và trước khi xóa local copy để xác nhận passphrase và restore usability.
- **SQLite:** operational validation được skip vì `mowftee.sqlite3` chưa tồn tại trong dữ liệu thật hiện tại; không tính là failure.

### DEC-013 — Canonical package versioning policy

- **Context:** Release `v0.0.1` được tạo và tag thành công ở mốc kết thúc Phase 0 (commit `794ba78`), nhưng package metadata tại thời điểm đó vẫn mang giá trị `0.0.0`. Cần chốt chính sách versioning chuẩn cho dự án.
- **Decision:**
  1. `pyproject.toml` là nguồn chuẩn (canonical source of truth) cho package version.
  2. `src/mowftee/__init__.py` (`__version__`) và `config/model-manifest.yaml` (`application.version`) phải luôn được đồng bộ trực tiếp với `pyproject.toml`.
  3. Phiên bản trong chu kỳ phát triển giữa các release dùng định dạng `dev` (ví dụ `0.1.0.dev0`).
  4. Trước mỗi release, version được bump chuẩn, chạy test, tạo release closure commit và gắn annotated Git tag khớp đúng phiên bản đó.
  5. Không rewrite commit `794ba78` hay tag `v0.0.1` lịch sử.
  6. Không áp dụng dynamic versioning machinery (`setuptools-scm`, `hatch-vcs`) tại thời điểm hiện tại.
- **Reason:** Đơn giản, explicit, ít phụ thuộc bên ngoài, dễ audit và hoàn toàn phù hợp với quy mô dự án hiện tại.
- **Revisit when:** Dự án chuyển sang quy trình CI/CD tự động hoá release hoàn toàn.

---

### DEC-014 — Native CachyOS Ollama + Vulkan runtime setup

- **Context:** Cần cài đặt và nghiệm thu LLM runtime local trên CachyOS, tận dụng RTX 3050 4GB VRAM.
- **Decision:**
  1. Cài hai CachyOS native packages: `ollama` (`0.32.6-1.1`) và `ollama-vulkan` (`0.32.6-1.1`).
  2. Backend: Vulkan API (`vulkan-tools` verified Vulkan Instance 1.4.357, NVIDIA RTX 3050 Laptop GPU).
  3. Service & Bind: `ollama.service` (`ollama:ollama`), `enabled` và `active`, bind loopback local-only `127.0.0.1:11434`.
  4. Model Storage: `/srv/mowftee/models/ollama` (`ollama:ollama 0750`) trên subvolume `/@srv`.
  5. Validation Smoke Model: `qwen3:0.6b` (digest `7df6b6e09427`, 522 MB) chạy 100% GPU via Vulkan để smoke test; KHÔNG đại diện cho default/winner model của Mowftee.
  6. Persistence: Boot persistence được xác minh thành công qua post-reboot final gate test.
- **Reason:** Ưu tiên package lifecycle native CachyOS, tránh dependency CUDA toolkit không cần thiết ở G1-01, giữ model storage tách biệt và API localhost-only; Vulkan/RTX 3050 đã được operationally validated.
- **Revisit when:** Thay đổi GPU backend hoặc cập nhật lớn của CachyOS packages.

---

### DEC-016 — LLM Provider Implementation & Runtime Configuration Boundary

- **Context:** Cần đóng gói giao tiếp LLM REST API với Ollama thành `OllamaLLMProvider` có khả năng thay thế qua Protocol `LLMProvider`, hỗ trợ cả non-streaming, NDJSON streaming, thread-safe cancellation, real TTFT timing và metrics, đồng thời giữ ranh giới rõ ràng về nguồn cấu hình runtime.
- **Decision:**
  1. Xây dựng package `mowftee.llm` export các base dataclasses (`ChatMessage`, `LLMResponse`, `LLMStreamChunk`, `LLMMetrics`), phân cấp exception (`LLMError`, `LLMConnectionError`, `LLMTimeoutError`, `LLMResponseError`, `LLMCancelledError`), và `@runtime_checkable` `LLMProvider` Protocol.
  2. Triển khai `OllamaLLMProvider` trong `src/mowftee/llm/ollama.py` dùng duy nhất stdlib `urllib.request` HTTP REST Client (zero external HTTP dependencies).
  3. Cấu hình runtime duy nhất là `config/default.yaml` (`llm` section). `config/model-manifest.yaml` là file hồ sơ/metadata selection, KHÔNG được đọc ở runtime.
  4. TTFT của streaming được đo thực tế bằng `time.perf_counter()` từ trước khi gửi HTTP request tới token content khác `""` đầu tiên.
  5. Quản lý cancellation bằng registry `_active_requests`, trạng thái `_cancelled_requests`, và `_registry_lock`. Thao tác `response.close()` được thực hiện ngoài lock để tránh blocking I/O; cancel idempotency đảm bảo lần đầu trả `True`, các lần sau trả `False`.
  6. Redaction logging nghiêm ngặt: không log prompt, message content, response text, options payload hay raw HTTP body.
  7. Lệnh CLI `mow` và TUI interface là planned extension, KHÔNG kéo vào scope G1-03.
- **Reason:** Bảo đảm kiến trúc modular monolith sạch, không hard-code API Ollama ngoài provider, tách biệt cấu hình runtime và metadata manifest, xử lý hủy request an toàn, và bảo vệ quyền riêng tư người dùng.
- **Validated with:** 43 unit tests (`tests/test_llm_provider.py`), 154 total unit test suite (`uv run pytest`), real Ollama smoke test với `qwen3:4b-instruct` (health_check, chat, stream TTFT ~304ms, cancel, metrics), và manual interactive chat test.
- **Revisit when:** Bổ sung LLM provider engine khác (ví dụ `llama.cpp` server) hoặc triển khai Conversation Manager ở G1-04.

---

### DEC-017 — Conversation Manager Atomic Turn Lifecycle & System Policy Layering

- **Context:** Cần quản lý phiên hội thoại văn bản nhiều lượt, tiêm system prompt và thời gian thực tự động, giới hạn context window theo số cặp lượt gần nhất, hỗ trợ hủy request không gây nghẽn thread và bảo toàn lịch sử hội thoại khi gặp lỗi hoặc bị hủy.
- **Decision:**
  1. Triển khai package `mowftee.conversation` với `ConversationError`, `ConversationBusyError` và `ConversationManager`.
  2. **Giao thức Atomic Turn Commit:** Cặp tin nhắn (`user`, `assistant`) chỉ được append đồng thời vào `_committed_history` trong RAM khi lượt hội thoại hoàn tất thành công. Nếu xảy ra lỗi HTTP, timeout hoặc hủy turn (`cancel_current_turn()`), `_committed_history` giữ nguyên 100% không bị mutate (không append-then-rollback).
  3. **Quản lý Active Turn & Thread Safety:** Giới hạn tối đa 1 turn active trên mỗi `ConversationManager` instance qua `_active_lock` (`threading.Lock`). Yêu cầu turn mới khi đang active bị từ chối ngay lập tức bằng `ConversationBusyError`.
  4. **Ghép Context Theo Lớp (Layered Context Assembly):** Context gửi tới LLM Provider được lắp ghép theo thứ tự: (1) Base system policy (`_system_prompt`) + (2) Dynamic ISO local datetime context (`_clock_fn`) khi `inject_datetime: true` + (3) Extension point + (4) Recent `max_turns` pairs gần nhất + (5) Pending user message.
  5. **Giới hạn Context vs Stored History:** `max_turns` chỉ giới hạn số lượng cặp tin nhắn gần nhất đưa vào context gửi LLM; KHÔNG thực hiện cắt tỉa phá hủy (destructive trim) đối với `_committed_history` trong RAM.
  6. **Lazy Streaming & Cancellation:** `stream_chat()` trả về generator lazily; việc claim active turn và gọi `provider.stream_chat()` chỉ diễn ra ở lần iteration `next(gen)` đầu tiên. Nếu generator đóng sớm (`gen.close()`), khối `finally` tự động hủy request bên dưới và dọn dẹp active state. `cancel_current_turn()` đọc active ID dưới lock rồi gọi `provider.cancel()` ngoài lock, thực thi tức thì mà không bị nghẽn deadlock.
  7. **CLI Runner tối thiểu:** Triển khai `src/mowftee/cli.py` và `scripts/chat.sh` để nghiệm thu giao tiếp terminal trực tiếp. Canonical CLI tên chính thức vẫn là `mowftee`.
- **Reason:** Đảm bảo tính nhất quán lịch sử hội thoại tuyệt đối, triệt tiêu lỗi model tự đoán ngày tháng sai nhờ tiêm datetime chính xác, xử lý hủy request an toàn không deadlock, và giữ cấu trúc sẵn sàng cho các mốc Persona / Memory tương lai.
- **Validated with:** 25 unit tests (`tests/test_conversation.py`, `tests/test_cli.py`), 180 total unit test suite (`uv run pytest`), và real Ollama smoke test với `qwen3:4b-instruct` (health_check, non-stream chat, stream chat TTFT ~292ms & 100% chuẩn xác ngày tháng '8/8/2026', cancellation, clear_history, metrics).
- **Revisit when:** Triển khai Phase 2 Persona Engine hoặc Phase 3 Long-term Memory Database.

---

## 16. Recovery architecture

Local encrypted backup/restore đã được triển khai ở G0-06A.

Backup ngoài máy đã được xác minh ở G0-06B bằng full cloud round-trip qua Google Drive riêng tư.

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
