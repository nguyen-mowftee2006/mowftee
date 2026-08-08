# Mowftee

> **Cách đọc:** Maou-ph-ti  
> AI companion chạy local, ưu tiên tiếng Việt, được thiết kế cho CachyOS/Linux.

Mowftee là dự án xây dựng một AI companion có nhân cách riêng, có thể trò chuyện bằng văn bản và giọng nói, ghi nhớ có kiểm soát, hỗ trợ một số tác vụ Linux an toàn và thể hiện trạng thái qua avatar.

Dự án lấy cảm hứng từ cách tương tác của AI VTuber, nhưng không sao chép tên, giọng nói, avatar hoặc tài sản của Neuro-sama hay bất kỳ dự án nào khác.

## Trạng thái hiện tại

- **Giai đoạn:** Phase 1 hoàn thành (release `v0.1.0`); bước tiếp theo là Phase 2 (Persona).
- **G1-01 Complete:** Ollama + Vulkan runtime đã cài đặt và nghiệm thu thành công.
- **G1-02 Complete:** Đã benchmark xong các mô hình ứng viên (Default: `qwen3:4b-instruct`, Performance Fallback: `llama3.2:3b`).
- **G1-03 Complete:** LLM Provider (`OllamaLLMProvider`) đã viết và nghiệm thu thành công.
- **G1-04 Complete:** Conversation Manager (`ConversationManager`) và CLI runner tối thiểu (`mowftee.cli`, `scripts/chat.sh`) đã viết và nghiệm thu thành công.
- **G1-05 Complete:** Test & benchmark suite (5-minute smoke soak, 20-turn functional, 50-turn stability, reboot persistence, service recovery test) PASS 100%, benchmark artifact saved.
- **Model Storage:** `/srv/mowftee/models/ollama/`
- **Bước tiếp theo:** `Phase 2 — Persona và chất lượng hội thoại (v0.2.x)`

## Mục tiêu

Phiên bản hoàn chỉnh dự kiến có:

- Hội thoại tiếng Việt chạy local.
- Persona riêng và ổn định.
- Trí nhớ dài hạn có thể xem, sửa, xóa và backup.
- Nhận và tổng hợp giọng nói.
- Hội thoại thời gian thực và hỗ trợ ngắt lời.
- Tool hỗ trợ CachyOS/Linux theo allowlist.
- Avatar có trạng thái nghe, nghĩ, nói và biểu cảm.
- Logging, benchmark, backup và restore.
- Khả năng dựng lại sau khi cài lại Linux.

## Cấu hình phát triển chính

| Thành phần | Thông số |
|---|---|
| Thiết bị | ASUS TUF Gaming F15 FX507ZC4 |
| CPU | Intel Core i5-12500H, 12 nhân/16 luồng |
| GPU | NVIDIA RTX 3050 Mobile, 4 GB VRAM |
| iGPU | Intel Iris Xe |
| RAM | 16 GB |
| Hệ điều hành | CachyOS |
| Desktop | Hyprland/Wayland |
| Filesystem | Btrfs |
| Audio | PipeWire + WirePlumber |

Giới hạn chính của hệ thống là VRAM 4 GB và RAM 16 GB. Vì vậy, giai đoạn đầu sẽ benchmark model quantized khoảng 3B–4B thay vì chọn model lớn theo cảm tính.

## Kiến trúc dự kiến

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

Kiến trúc khởi đầu là **modular monolith**. Các engine LLM, STT, TTS, memory, tool và avatar được tách qua provider để có thể thay thế mà không phải viết lại toàn bộ ứng dụng.

## Lộ trình

| Giai đoạn | Nội dung | Phiên bản |
|---|---|---|
| 0 | Nền móng, cấu hình máy, Git, dữ liệu và backup | `v0.0.x` |
| 1 | Chat chữ local, streaming và benchmark model | `v0.1.x` |
| 2 | Persona và chất lượng hội thoại | `v0.2.x` |
| 3 | Trí nhớ dài hạn | `v0.3.x` |
| 4 | Voice theo từng lượt | `v0.4.x` |
| 5 | Voice thời gian thực và ngắt lời | `v0.5.x` |
| 6 | Tool hỗ trợ Linux an toàn | `v0.6.x` |
| 7 | Avatar, lip-sync và biểu cảm | `v0.7.x` |
| 8 | Tối ưu tài nguyên và độ ổn định | `v0.8.x` |
| 9 | Đóng gói, backup, restore và release | `v1.0.0` |

Mỗi giai đoạn chỉ được đóng khi chức năng hoạt động, kiểm thử đạt, hiệu năng đã được đo, tài liệu đã cập nhật và commit/tag đã được tạo.

## Tài liệu dự án

| Tài liệu | Vai trò |
|---|---|
| [PLAN.md](docs/PLAN.md) | Kế hoạch, giai đoạn, tiêu chí hoàn thành và rollback |
| [SESSION_PROMPT.md](docs/SESSION_PROMPT.md) | Ngữ cảnh để tiếp tục dự án trong phiên chat mới |
| [LOG.md](docs/LOG.md) | Nhật ký công việc, quyết định, sự cố và cách xử lý |
| [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | Phần cứng, Btrfs, kiến trúc module và Decision Log |
| [model-manifest.yaml](config/model-manifest.yaml) | Cấu hình model và engine ở dạng máy đọc |
| [hardware-baseline.txt](config/hardware-baseline.txt) | Kết quả khảo sát hệ thống ban đầu |

## Dữ liệu và khôi phục

```text
GitHub
├── source code
├── persona
├── config mẫu
└── tài liệu

Backup riêng
├── memory
├── config thật
├── dữ liệu RAG
├── model tự fine-tune
└── voice tự tạo
```

Model công khai tải lại được không đưa vào Git. Memory, secret, audio cá nhân, log runtime và cấu hình riêng của máy cũng không được commit.

Vị trí lưu trữ model:

```text
/srv/mowftee/models/ollama/
```

## Nguyên tắc an toàn

- Không cho AI chạy shell tùy ý.
- Không truyền trực tiếp nội dung người dùng vào lệnh hệ thống.
- Tool phải có schema, allowlist, timeout và audit log.
- Hành động thay đổi hệ thống phải yêu cầu xác nhận.
- API AI chỉ bind local trong các giai đoạn đầu.
- Snapshot Btrfs không được xem là backup ngoài máy.

## Quy trình phát triển

```text
Thực hiện một bước nhỏ
→ kiểm thử
→ đo tài nguyên
→ cập nhật LOG/PLAN/ARCHITECTURE
→ commit
→ chuyển bước tiếp theo
```

---

**Mowftee** hiện là dự án thử nghiệm cá nhân và chưa có bản phát hành ổn định.
