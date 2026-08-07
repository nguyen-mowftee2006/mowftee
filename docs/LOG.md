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


---

## 2026-08-07 00:17 +07 — Đóng G0-02

### Xác nhận repository

- Remote đã đổi thành `https://github.com/nguyen-mowftee2006/mowftee.git`.
- Commit `05afbd0` đã được push lên `origin/main`.
- Working tree sạch.
- Nhánh `main` đồng bộ với `origin/main`.
- Remote `bimatnhe` được ghi trong entry trước chỉ phản ánh trạng thái lịch sử tại thời điểm entry đó được tạo.

### Trạng thái

`G0-02`: **Hoàn thành**.

### Việc tiếp theo

`G0-03 — Chốt môi trường Python`.

G0-03 chưa được thực hiện trong entry này.


---

## 2026-08-07 00:27 +07 — G0-03 Môi trường Python

### Mục tiêu

Khóa môi trường Python riêng cho project, tách khỏi Python hệ thống của CachyOS.

### Quyết định

- Project dùng CPython 3.11 với `requires-python = ">=3.11,<3.12"`.
- `uv` quản lý interpreter, dependency và virtual environment `.venv/`.
- Python hệ thống 3.14.6 không được dùng để cài dependency project.
- Hatchling build wheel từ `src/mowftee`.
- Dependency khai báo trong `pyproject.toml`; `uv.lock` phải được commit.
- Setup và khôi phục môi trường dùng `uv sync --locked`.

### Thay đổi

- Cập nhật `pyproject.toml` với build system, Python constraint và nhóm dev gồm pytest, Ruff.
- Tạo `.python-version` với nội dung `3.11`.
- Tạo `uv.lock` và `.venv/` bằng `uv`; `.venv/` không được Git theo dõi.
- Tạo script idempotent `scripts/setup-python.sh`.
- Thay placeholder bằng một smoke test import tại `tests/test_import.py`.

### Kết quả kiểm thử

- Interpreter project: CPython 3.11.15 trong `.venv/`.
- `uv lock --check`: đạt.
- `uv sync --locked`: đạt.
- `uv run python --version`: Python 3.11.15.
- Interpreter được xác nhận thuộc `.venv/`.
- Import `mowftee`: đạt.
- Pytest: 1 test đạt.
- `uv run ruff check .`: đạt.
- `scripts/setup-python.sh` chạy liên tiếp hai lần thành công và không sửa lock file.

### Trạng thái

`G0-03`: **Hoàn thành**.

### Việc tiếp theo

`G0-04 — Chốt storage layout`.


---

## 2026-08-07 00:51 +07 — G0-04 Storage layout

### Khảo sát

- `/`, `/home` và `/srv` là các Btrfs subvolume riêng, mount `rw` với `compress=zstd:1`.
- `@srv` không bị snapshot tự động; Snapper, Timeshift và Btrfs Assistant không được cài hoặc cấu hình.
- Quota/qgroup đang tắt; CoW giữ mặc định.
- Không có ổ ngoài hoặc cloud mount dành cho backup.
- User/group, service và biến `OLLAMA_MODELS` của Ollama chưa tồn tại.

### Quyết định

- XDG paths dùng biến môi trường với giá trị mặc định dưới `$HOME`, không hard-code user.
- Public model nằm tại `/srv/mowftee/models/ollama`; không tạo child Btrfs subvolume.
- Public model và cache không cần backup.
- Memory, private config, custom voice và LoRA bắt buộc backup ngoài máy; triển khai backup thuộc G0-06.
- Chỉ tạo model directory với `ollama:ollama 0750` sau khi user/group Ollama tồn tại.

### Thay đổi

- Tạo các XDG directories của Mowftee với owner là user hiện tại và mode `0700`.
- Tạo `/srv/mowftee` và `/srv/mowftee/models` với `root:root 0755`.
- Tạo script idempotent `scripts/setup-storage.sh`.
- Chốt storage metadata trong `config/model-manifest.yaml`.
- Không tạo config, database, log, secret, backup target hoặc `/srv/mowftee/models/ollama`.

### Kiểm tra

- `scripts/setup-storage.sh` chạy liên tiếp hai lần thành công.
- Shell syntax hợp lệ.
- Owner và mode của toàn bộ Mowftee XDG directories đạt yêu cầu.
- Hai system parent directories là `root:root 0755`.
- Không có file runtime trong XDG paths.
- `/srv/ftp` và `/srv/http` không bị thay đổi.

### Trạng thái

`G0-04`: **Hoàn thành**, với deferred action tạo/chown model directory ở bước cài Ollama.

### Việc tiếp theo

`G0-05 — Thiết lập cấu hình và logging`.


---

## 2026-08-07 01:26 +07 — G0-05 Cấu hình và logging

### CHECK

- Nhánh `main` ban đầu sạch và đồng bộ với `origin/main` tại commit `0795092a188e71c03ca8c728d45084a85593b689`.
- G0-04 đã hoàn thành; bước hiện tại khi bắt đầu là G0-05.
- Project tiếp tục dùng CPython 3.11 do `uv` quản lý; không dùng Python hệ thống 3.14.6 cho dependency project.
- XDG storage layout đã tồn tại; repo chưa có config loader hoặc logging implementation trùng chức năng.
- Không có runtime config, JSONL log, secret hoặc cache được Git theo dõi.

### Quyết định

- Dùng PyYAML làm runtime dependency; `uv` resolve phiên bản 6.0.3 và cập nhật `pyproject.toml`, `uv.lock`.
- Config precedence: `config/default.yaml` → user config tại `${XDG_CONFIG_HOME:-$HOME/.config}/mowftee/config.yaml` → biến môi trường `MOWFTEE_` → CLI override dạng mapping.
- Schema ban đầu là `config_schema_version: 1`; user config là tùy chọn nhưng lỗi YAML/validation không bị silently ignored.
- Log dùng JSONL UTF-8, tách app/performance/audit dưới `${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/`.
- Dùng UUID và `contextvars` cho request context; dùng `RotatingFileHandler` chuẩn, file mode `0600`, thư mục Mowftee mode `0700`.
- Secret và nội dung prompt, conversation, file, audio bị redact mặc định theo privacy policy. Nếu file handler lỗi, logging fallback sang console và báo ngắn gọn thay vì làm ứng dụng crash.

### Thay đổi

- Tạo `config/default.yaml`, `config/example.yaml`.
- Tạo `src/mowftee/config.py`, `src/mowftee/logging_setup.py`.
- Tạo `tests/test_config.py`, `tests/test_logging.py`.
- Bổ sung ignore cho rotated JSONL log.
- Không tạo user config thật, runtime log thật, memory database, Ollama runtime hoặc model.

### Kết quả kiểm thử

- `uv lock --check`: đạt.
- `uv sync --locked`: đạt.
- `uv run pytest`: 30 test đạt.
- `uv run ruff check .`: đạt.
- Config smoke test trong XDG tạm: schema version `1`.
- Logging smoke test trong XDG tạm: tạo và parse được `app.jsonl`, có UTC timestamp, event, UUID request ID; secret mẫu không xuất hiện.
- `git diff --check`: đạt; không có runtime config/log/cache được Git theo dõi và XDG thật không có file runtime mới.

### Trạng thái

`G0-05`: **Hoàn thành**.

### Việc tiếp theo

`G0-06 — Thiết lập backup tối thiểu`.

G0-06 chưa được thực hiện trong entry này. Ollama chưa được cài và chưa tải model.


---

## 2026-08-07 01:42 +07 — G0-05 Hardening trước commit

### Rà soát bổ sung

Rà soát độc lập sau kết quả trung gian 30 test phát hiện bốn blocker trước commit:

- Default YAML chưa được đóng gói vào wheel.
- Raw PyYAML cause có thể giữ dòng config lỗi trong traceback.
- Chuỗi authorization/cookie header có thể còn lộ phần credential.
- Bật audio metadata có thể vô tình cho phép raw audio.

Không có commit được tạo khi các blocker này còn tồn tại.

### Khắc phục

- Force-include `config/default.yaml` thành package resource `mowftee/default.yaml`; loader fallback sang resource khi chạy từ wheel.
- Loại raw YAML parser cause khỏi exception public; sửa collision environment override có giá trị `null` và bỏ qua XDG base path tương đối.
- Redact toàn bộ `Authorization`, `Cookie`, `Set-Cookie`; raw audio luôn bị chặn bất kể privacy flag metadata.
- Bổ sung console fallback cho lỗi emit/rotation sau setup, đóng handler khi setup dở dang và bảo vệ cyclic metadata.

### Kiểm tra cuối sau hardening

- Pytest: **39 test đạt**; số này thay cho kết quả trung gian 30 test trong entry trước.
- Ruff: đạt.
- Wheel-install smoke test: build wheel, cài vào venv CPython 3.11 tạm, xác nhận package resource tồn tại và `load_config()` trả schema version `1`.
- Không tạo artifact build trong repository; toàn bộ venv/XDG của smoke test nằm trong thư mục tạm và đã được xóa.

### Trạng thái

`G0-05`: **Hoàn thành sau hardening**. Bước tiếp theo vẫn là `G0-06 — Thiết lập backup tối thiểu`; G0-06 chưa được thực hiện.

---

## 2026-08-07 — G0-06A Local encrypted backup/restore

### Trạng thái ban đầu

- Làm việc trên nhánh `wip/g0-06a-backup`.
- Base là `aca2deb` — `chore: complete G0-05 config and logging`.
- WIP implementation được bảo toàn tại `b98b092` — `wip: preserve G0-06A backup implementation`.
- Không làm lại backup tooling từ đầu.

### Implementation

- Bổ sung ignore cho archive backup, sidecar checksum và file partial.
- Tạo `scripts/backup.sh` và `scripts/restore.sh`.
- Tạo `src/mowftee/backup.py`.
- Tạo `tests/test_backup.py`.
- Archive dùng tar gzip và mã hóa đối xứng GPG AES-256.
- Ciphertext có sidecar SHA-256.
- Payload có manifest cùng checksum SHA-256 nội bộ.
- SQLite sử dụng `sqlite3.Connection.backup()` để tạo snapshot nhất quán.
- Restore từ chối path traversal, symlink, special file, member ngoài manifest và destination đã tồn tại.
- Archive được đánh dấu `local_staging` và luôn cảnh báo rằng chưa phải backup ngoài máy.

### Kiểm tra cuối

- `bash -n scripts/backup.sh scripts/restore.sh`: đạt.
- `uv lock --check`: đạt.
- `uv sync --locked`: đạt.
- `uv run ruff check .`: đạt.
- `uv run pytest tests/test_backup.py -v`: **45 test đạt**.
- `uv run pytest`: **84 test đạt**.
- `git diff main...HEAD --check`: đạt.
- Wheel build và cài vào venv CPython 3.11 tạm: đạt.
- Import `mowftee.backup`, kiểm tra version và load packaged default config từ wheel: đạt.
- Working tree sạch trước khi cập nhật tài liệu.

### Kết luận

`G0-06A`: **Hoàn thành** sau vòng kiểm tra cuối.

Archive hiện chỉ là local encrypted staging. `G0-06B — Backup ngoài máy` chưa được thực hiện.

Không merge `main`, không push commit đóng bước, không tag `v0.0.1`, không cài Ollama và không tải model trong G0-06A.
