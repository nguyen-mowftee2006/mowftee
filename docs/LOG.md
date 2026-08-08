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

---

## 2026-08-07 — Correction: G0-06A push status

Commit `121ebbf` (`docs: close G0-06A backup milestone`) sau đó đã được push lên `origin/wip/g0-06a-backup`.

Entry lịch sử cũ không bị sửa lại.

---

## 2026-08-07 — G0-06B: Xác minh backup ngoài máy qua Google Drive

### Target

- Google Drive riêng tư.
- Upload/download thủ công qua trình duyệt.
- Không dùng Drive API, rclone, OAuth integration, cloud SDK hoặc daemon sync.

### Vòng validation đầu

- Production backup attempt #1 thất bại do operator nhập sai bước xác nhận passphrase; staging sau fail sạch.
- Attempt #2 thành công.
- Archive: `mowftee-backup-20260807T054900Z-1bfb0426.tar.gz.gpg`.
- Local postcheck và outer SHA-256: PASS.
- Upload Drive, xóa local, tải lại, outer SHA-256 sau download: PASS.
- Restore không hoàn thành vì operator không còn khả năng truy cập production passphrase.
- Ciphertext integrity được xác minh bằng SHA-256; archive này được xem là stale/unusable backup.
- Không bypass hoặc brute-force GPG.

### Recovery

- Operator tạo passphrase mới và xác nhận đã lưu an toàn trong password manager.
- Production backup mới thành công:
  `mowftee-backup-20260807T072238Z-5dd3acf1.tar.gz.gpg`
- Exact pair, permission, no plaintext, no `.partial`, outer SHA-256: PASS.

### Cải tiến quy trình

Sau production backup và checksum PASS, thêm local restore sanity test trước upload và trước khi xóa local copy để xác nhận passphrase và restore usability.

Local restore sanity test:

- restore exit 0;
- restored `config/mowftee/config.yaml`;
- `cmp` với config thật: PASS;
- thư mục verify tạm đã được dọn.

### Cloud round-trip cuối

- Upload archive + sidecar lên Google Drive: PASS.
- Xóa local original pair: PASS.
- Download lại từ Drive: PASS.
- Permission download đưa về `0600`.
- Outer SHA-256 sau download: PASS.
- Restore bản download vào `/tmp/mowftee-g0-06b-restore`: exit 0.
- Đối chiếu restored config với source bằng `cmp`: PASS.

### SQLite

`~/.local/share/mowftee/memory/mowftee.sqlite3` chưa tồn tại nên SQLite operational validation được SKIP và không tính là failure.

### Kết luận

- `G0-06A`: Hoàn thành.
- `G0-06B`: Hoàn thành.
- `G0-06`: Hoàn thành về mặt kỹ thuật và operational validation.
- Phase 0 chưa được đóng chính thức.
- Nhánh `wip/g0-06b-offmachine-backup` chưa merge, chưa push, chưa tag `v0.0.1`.

### Housekeeping

- Có thể dọn archive vòng đầu `...1bfb0426...` trên Google Drive.
- Có thể dọn `/tmp/mowftee-g0-06b-restore` khi không còn cần giữ evidence.

---

## 2026-08-07 — Pre-G1 metadata sync và version policy

### Mục tiêu

Đồng bộ thông tin metadata public/project sau khi hoàn thành Phase 0 (release `v0.0.1`), xử lý nợ kỹ thuật historical version mismatch, và mở chu kỳ phát triển Phase 1 ở phiên bản `0.1.0.dev0`.

### Bối cảnh & Sự cố lịch sử

- Release `v0.0.1` đã được tạo và đóng tại commit `794ba78` với annotated Git tag `v0.0.1`.
- Tại thời điểm release, package metadata (`pyproject.toml`, `__version__`, `model-manifest.yaml`) vẫn giữ nguyên `0.0.0`.
- Đây được ghi nhận là historical release-process debt. Không rewrite commit `794ba78`, tag `v0.0.1` hay lịch sử Git.

### Quyết định Version Policy

- `pyproject.toml` là canonical package version source of truth.
- `src/mowftee/__init__.py` (`__version__`) và `config/model-manifest.yaml` (`application.version`) phải luôn đồng bộ với `pyproject.toml`.
- Trong chu kỳ phát triển giữa các release, phiên bản package được đặt dưới dạng next-version development (`0.1.0.dev0`).
- Đối với các release tương lai: package version được bump trước release → đồng bộ `__version__` & manifest → kiểm thử → release closure commit → annotated Git tag khớp chính xác phiên bản.
- Không sử dụng dynamic versioning plugin (`setuptools-scm`, `hatch-vcs`) ở thời điểm hiện tại.

### Thay đổi

- Cập nhật `pyproject.toml` và `src/mowftee/__init__.py` lên `0.1.0.dev0`.
- Cập nhật `config/model-manifest.yaml`: `application.version` = `0.1.0.dev0`, `status` = `proposed`, `runtime.python_version` = `"3.11"`, `runtime.python_status` = `validated`.
- Cập nhật `README.md`, `docs/SESSION_PROMPT.md`, `docs/PLAN.md` phản ánh Phase 0 COMPLETE (`v0.0.1`) và mốc tiếp theo G1-01.
- Append Decision Log DEC-013 trong `docs/SYSTEM_ARCHITECTURE.md`.

### Trạng thái

Task metadata sync: Pre-G1 metadata sync đã hoàn thành và được commit; G1-01 là bước tiếp theo và chưa bắt đầu.


---

## 2026-08-08 00:41 +07 — G1-01 Cài đặt và nghiệm thu runtime LLM (Ollama + Vulkan)

### Mục tiêu

Cài đặt runtime Ollama trên CachyOS, cấu hình GPU Vulkan, lưu mô hình tại `/srv/mowftee/models/ollama`, chỉ bind loopback local, và kiểm tra persistence sau khi reboot.

### Quá trình thực hiện & Các sự cố đã xử lý

1. **Vulkan Verification & Dependency Setup:**
   - Operator cài `vulkan-tools`. `vulkaninfo --summary` xác nhận Instance Version 1.4.357 và nhận dạng `NVIDIA GeForce RTX 3050 Laptop GPU`.
2. **Mirror Recovery & Package Installation:**
   - Ban đầu gặp lỗi mirror 404. Operator chạy `sudo cachyos-rate-mirrors` và `sudo pacman -Syu` thành công.
   - Cài đặt hai CachyOS native packages: `ollama` (`0.32.6-1.1`) và `ollama-vulkan` (`0.32.6-1.1`).
3. **Storage & Service Configuration:**
   - Thư mục `/srv/mowftee/models/ollama` được chown `ollama:ollama 0750` trên subvolume `/@srv`.
   - Override systemd service: `OLLAMA_MODELS=/srv/mowftee/models/ollama`, `OLLAMA_HOST=127.0.0.1:11434`.
   - `systemctl enable` và `systemctl start` dịch vụ `ollama`.
4. **Smoke Model & Inference Gate:**
   - Pulled smoke model `qwen3:0.6b` (digest `7df6b6e09427`, 522 MB).
   - *Lưu ý:* `qwen3:0.6b` chỉ là validation model để nghiệm thu pipeline runtime/GPU, KHÔNG phải default model hay winner model của Mowftee.
   - Inference PASS (`ollama ps` = `100% GPU`, Vulkan backend trên RTX 3050).
5. **Post-Reboot Final Gate:**
   - Reboot máy thật và kiểm tra:
     - `systemctl is-enabled`: `enabled`
     - `systemctl is-active`: `active` (tự khởi động sau boot)
     - `127.0.0.1:11434` bind: PASS (localhost-only)
     - API `/api/version`: `0.32.6`
     - Inference sau reboot: PASS (`100% GPU`, Vulkan0 compute buffer 30.01 MiB)
     - Persistence đường dẫn `/srv/mowftee/models/ollama`: PASS

### Trạng thái

`G1-01`: **Hoàn thành**.

### Việc tiếp theo

`G1-02 — Benchmark model ứng viên` (NEXT / NOT STARTED).


---

## 2026-08-08 02:15 +07 — G1-02 Benchmark và chọn mô hình LLM mặc định

### Mục tiêu

Benchmark các model ứng viên (`qwen3:1.7b`, `llama3.2:3b`, `qwen3:4b`/`qwen3:4b-instruct`), đo đạc TTFT, tốc độ sinh, khả năng tuân thủ câu lệnh, tiếng Việt, suy luận, độ ổn định qua 20 và 50 lượt hội thoại, và chọn model mặc định (default) cùng model dự phòng hiệu năng (performance fallback).

### Quá trình thực hiện & Phát hiện kỹ thuật

1. **Phân tích ứng viên & Qwen3 Thinking Variant Finding:**
   - Ứng viên ban đầu gồm `qwen3:1.7b`, `llama3.2:3b`, và `qwen3:4b` (`359d7dd4bcda`).
   - Phát hiện: Tag `qwen3:4b` mặc định kích hoạt khối suy nghĩ `<think>` tiêu thụ toàn bộ 192 token dự đoán, kể cả khi dùng `/no_think` hoặc `"think": false`.
   - Giải pháp: Kéo đúng biến thể `qwen3:4b-instruct` (`0edcdef34593`). `qwen3:4b-instruct` sinh câu trả lời trực tiếp mà không bị đọng token suy nghĩ.

2. **Incident & Scratch Recovery:**
   - Trong quá trình chạy script quality screen, gặp lỗi `SyntaxError` do thoát dấu nháy kép trong inline f-string Python.
   - Script đã được ghi chính thức vào file `/home/minhthanh/.gemini/antigravity-cli/brain/f1b3e300-23cf-4a7e-9d20-df99469aee03/scratch/run_quality_screen.py` và khôi phục thành công.

3. **Reasoning Gate Correction:**
   - Bài test reasoning cũ (Test 2) có mâu thuẫn đa nghiệm (chìa khóa ở A hoặc B đều thỏa mãn duy nhất 1 câu đúng). Test này được đánh dấu `INVALID`.
   - Bài test thay thế (3 người An, Bình, Chi có số 2, 5, 8) có nghiệm duy nhất ($An=5, Bình=2, Chi=8$). Kết quả:
     - `qwen3:4b-instruct`: PASS 100% cả đáp án lẫn lập luận loại trừ từng bước.
     - `llama3.2:3b` & `qwen3:1.7b`: FAIL (tự mâu thuẫn hoặc gán sai dữ kiện).

4. **20-Turn & 50-Turn Soak Test:**
   - Cả `llama3.2:3b` và `qwen3:4b-instruct` đều hoàn thành 50/50 lượt hội thoại liên tục không crash, không trôi memory (VRAM phẳng tuyệt đối 2.48GB / 2.72GB và giải phóng 100% về 15 MiB sau khi dừng runner).
   - `qwen3:4b-instruct`: Tốc độ trung bình 31.95 tok/s, 0 lỗi instruction, 0 lỗi reasoning, 0 lỗi context/recall, 0 hallucination. Văn phong tiếng Việt tự nhiên nhất.
   - `llama3.2:3b`: Tốc độ trung bình 68.20 tok/s, 100% GPU thuần, nhưng gặp 2 lỗi instruction, 1 lỗi toán học và 1 lỗi safety trigger nhầm.

5. **Streaming TTFT Final Gate:**
   - Prompt: *"Giải thích bằng tiếng Việt trong tối đa 3 câu: vì sao cần sao lưu dữ liệu?"* (`stream=true`, 5 runs/model).
   - `qwen3:4b-instruct`: TTFT trung bình `0.1880s` (median `0.1844s`, min `0.1765s`, max `0.2034s`), gen speed `36.09 tok/s`.
   - `llama3.2:3b`: TTFT trung bình `0.2062s` (median `0.2046s`, min `0.1940s`, max `0.2287s`), gen speed `70.10 tok/s`.
   - Cả hai model đều vượt trội chỉ tiêu TTFT < 4.0s.

### Quyết định chọn Model

- **Default Selected Model:** `qwen3:4b-instruct` (digest `0edcdef34593`, `Q4_K_M`, 4.0B parameters).
- **Performance Fallback Model:** `llama3.2:3b` (digest `a80c4f17acd5`, `Q4_K_M`, 3.2B parameters).

### Trạng thái

`G1-02`: **Hoàn thành**.

### Việc tiếp theo

`G1-03 — Viết LLM Provider` (NEXT / NOT STARTED).
---

## 2026-08-08 02:40 +07 — Post G1-02 cleanup

### Mục tiêu

Dọn dẹp các mô hình thử nghiệm không còn sử dụng và các script tạm sau khi đóng milestone G1-02.

### Quá trình thực hiện & Kết quả

1. **Commit & Fast-forward Merge:**
   - G1-02 đã đóng và ff-merge vào `main` tại commit `54ac3399de13ad5080870a0a7a817baeee847b8a`.
2. **Model Removal:**
   - Đã xóa qua Ollama CLI: `qwen3:0.6b`, `qwen3:1.7b`, `qwen3:4b`.
   - Giữ lại: `qwen3:4b-instruct` (default) và `llama3.2:3b` (performance fallback).
   - Dung lượng lưu trữ model: khoảng 8.9 GB → 4.5 GB (thu hồi khoảng 4.4 GB).
3. **Scratch Cleanup:**
   - File script tạm `/home/minhthanh/.gemini/antigravity-cli/brain/f1b3e300-23cf-4a7e-9d20-df99469aee03/scratch/run_quality_screen.py` đã được xóa.
   - Thư mục `__pycache__` không tồn tại trong scratch.
4. **Trạng thái Repo & Quyết định:**
   - Working tree repository hoàn toàn sạch (`main...origin/main`).
   - Việc dọn dẹp không làm thay đổi quyết định chọn mô hình LLM.

`Post G1-02 cleanup`: **Hoàn thành**.

### Việc tiếp theo

`G1-03 — Viết LLM Provider` (NEXT / NOT STARTED).


---

## 2026-08-08 12:50 +07 — G1-03 Viết LLM Provider (OllamaLLMProvider)

### Mục tiêu

Xây dựng module `mowftee.llm` để đóng gói giao tiếp HTTP REST API với Ollama local runtime (`127.0.0.1:11434`), hỗ trợ `health_check()`, non-streaming `chat()`, NDJSON streaming `stream_chat()`, thread-safe `cancel()`, và thống kê hiệu năng `get_metrics()`.

### Quá trình thực hiện & Thiết kế chính

1. **Base Abstractions & Taxonomy (`src/mowftee/llm/base.py`):**
   - Đĩnh nghĩa dataclasses: `ChatMessage`, `LLMResponse`, `LLMStreamChunk`, `LLMMetrics`.
   - Phân cấp ngoại lệ: `LLMError` (gốc) -> `LLMConnectionError`, `LLMTimeoutError`, `LLMResponseError`, `LLMCancelledError`.
   - Protocol `@runtime_checkable`: `LLMProvider`.

2. **Runtime Configuration & Validation (`config/default.yaml`, `src/mowftee/config.py`, `src/mowftee/logging_setup.py`):**
   - Runtime source-of-truth cho LLM config nằm tại `config/default.yaml` (`llm` section). `config/model-manifest.yaml` KHÔNG được đọc ở runtime.
   - Validation chặt chẽ: `provider` (string), `model` (string non-empty), `base_url` (giao thức http/https, có hostname, loại bỏ trailing slash), `timeout` & `health_timeout` (số thực hữu hạn > 0, từ chối bool/NaN/inf).
   - Context logging: bổ sung `get_request_id()` và `generate_request_id()`.

3. **OllamaLLMProvider Implementation (`src/mowftee/llm/ollama.py`):**
   - Giao tiếp qua stdlib `urllib.request` REST HTTP API (zero external HTTP dependencies).
   - `health_check()`: GET `/api/version` sử dụng `health_timeout`, trả về `True`/`False` an toàn mà không ném exception ra ngoài.
   - `chat()`: POST `/api/chat` non-streaming với schema validation, strict numeric field parsing (`_parse_non_negative_int`), và error mapping chuẩn (`HTTPError` -> `LLMResponseError`, `URLError(timeout)`/`TimeoutError` -> `LLMTimeoutError`, `URLError(other)` -> `LLMConnectionError`).
   - `stream_chat()`: POST `/api/chat` NDJSON streaming (`stream: true`), đọc theo dòng qua `readline()`, validate `model` nhất quán giữa các chunks, tính real TTFT bằng `time.perf_counter()`, và trả về `LLMStreamChunk` kèm metrics ở final chunk (`done: true`). EOF trước `done: true` được coi là hỏng stream và ném `LLMResponseError`.
   - `cancel()` & Registry: `_active_requests: dict[str, Any]`, `_cancelled_requests: set[str]`, `_registry_lock: threading.Lock`. Thực hiện `response.close()` ngoài registry lock để tránh I/O blocking trong lúc giữ lock; cancel idempotency đảm bảo lần 1 trả `True`, lần 2 trả `False`.
   - Logging Privacy: Không log prompt, message content, response text, options payload hay raw HTTP body dưới mọi kênh log.

4. **Unit Test Suite (`tests/test_llm_base.py`, `tests/test_llm_provider.py`):**
   - Xây dựng 43 unit test cases cover toàn bộ kịch bản mong muốn và ranh giới hệ thống: protocol validation, health_check, chat successful/error mappings, strict numeric parsing (reject bool/float/string/negative), request context lifecycle/restore, streaming chunks/NDJSON/model mismatch/premature EOF, cancel idempotency, blocking cancellation với `threading.Event`, registry cleanup trên mọi nhánh execution, và privacy redaction verification.

5. **Real Ollama Integration Smoke Test:**
   - Đã kiểm tra thực tế end-to-end với dịch vụ Ollama thật (`0.32.6`) và default model `qwen3:4b-instruct`:
     - `health_check()`: `True` (~6.95 ms)
     - `chat()`: `'Mowftee đã kết nối thành công.'` (wall duration ~6.25s)
     - `stream_chat()`: `'Chào từ Mowftee!'` (9 chunks, TTFT ~304.73 ms, generation speed ~39.33 tok/s)
     - `cancel()`: Hủy stream câu lệnh dài thành công, `cancel()` lần 1 trả `True`, worker thread nhận `LLMCancelledError` và thoát sạch, `cancel()` lần 2 trả `False`, registry & cancelled state dọn dẹp phẳng 0.
     - Final Provider Metrics: `total=3`, `success=2`, `failed=1`, `total_prompt_tokens=52`, `total_eval_tokens=20`.

6. **Manual Interactive Chat Finding:**
   - Script tương tác chat thử nghiệm xác nhận `OllamaLLMProvider` hoạt động mượt mượt; việc `qwen3:4b-instruct` trả lời kiểu trợ lý chung hay tự đổi ngôn ngữ là behavior thô của base model khi chưa có persona/context policy của G1-04.

### Trạng thái

`G1-03`: **Hoàn thành**.

### Việc tiếp theo

`G1-04 — Conversation Manager` (NEXT / NOT STARTED).
