# SYSTEM ARCHITECTURE — Mowftee Living Technical Architecture

- **Purpose:** Canonical living technical architecture and accepted architectural decisions.
- **Authority:** Canonical for current architecture, subsystem boundaries, technical policies and architectural decisions.
- **Audience:** HQ / worker / developer.
- **Update trigger:** Actual architecture, interface, subsystem boundary, technical policy, resource constraint, recovery design or architectural decision changes.
- **Must not contain:** Historical command transcripts, benchmark logs, milestone chronology, temporary runtime state, or duplicated roadmap specifications.

---

## 1. Architecture Overview

Mowftee is designed as a local-first, privacy-preserving AI companion for CachyOS (Arch Linux family), implemented as a **modular monolith** in Python.

### Core Architecture Principles
- **Local-First:** All AI inference, context management, memory, and tools run locally on the user's hardware. Local APIs bind strictly to loopback (`127.0.0.1`).
- **Modular Monolith:** Single Python application codebase (`src/mowftee`) structured with clean interface boundaries (`Protocol` abstractions). Engines (LLM, STT, TTS, Memory, Tools, Avatar) interact through decoupled providers.
- **Graceful Degradation:** Subsystem failures (e.g. TTS error, memory unavailable) degrade gracefully to simpler fallback modes (e.g. text display, in-memory session) without crashing the core application.
- **Explicit Security & Privacy:** Shell execution is forbidden; tools operate on strict allowlists with schema validation, permission levels (L0–L5), and audit logs. Sensitive content and secrets are redacted from logs by default.

### System Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                        │
│ Terminal CLI (Implemented) / GUI / Microphone / Avatar (Planned)
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                      Application Core                       │
│ State Machine (Planned)                                     │
│ Conversation Manager (Implemented)                          │
│ Layered Context Assembly (Implemented)                      │
│ Persona Engine (Planned - Phase 2)                          │
│ Safety & Allowlist Layer (Planned - Phase 6)                │
└────────┬─────────────────┬──────────────────┬───────────────┘
         │                 │                  │
 ┌───────▼──────┐  ┌───────▼──────┐   ┌───────▼──────┐
 │ LLM Provider │  │    Memory    │   │ Tool Manager │
 │ (Ollama HTTP │  │  (SQLite DB  │   │  (Allowlist  │
 │ Implemented) │  │  Planned)    │   │  Planned)    │
 └───────┬──────┘  └───────┬──────┘   └───────┬──────┘
         │                 │                  │
 ┌───────▼─────────────────▼──────────────────▼───────────────┐
 │             Voice & Presentation Subsystems                │
 │ VAD / STT / TTS / Audio Queue / Avatar (Planned)           │
 └────────────────────────────────────────────────────────────┘
```

---

## 2. Platform & Resource Constraints

Technical architecture decisions are constrained by the baseline hardware profile:

- **GPU Memory Budget:** NVIDIA RTX 3050 Laptop GPU (4 GB VRAM) is currently prioritized and primarily reserved for the local LLM runtime (`OllamaLLMProvider`) under the current hardware budget. Model sizing is constrained to 3B–4B quantized parameters (`Q4_K_M`).
- **System RAM Budget:** 16 GB system RAM (supplemented by ZRAM swap). Offloading large model layers to CPU is minimized to maintain conversational throughput.
- **CPU Workload Allocation:** 12-core / 16-thread CPU handles application orchestration, context assembly, JSONL logging, and future lightweight STT/TTS/VAD pipelines.
- **Desktop & Compositor:** Intel Iris Xe iGPU handles Hyprland / Wayland desktop rendering, isolating display workloads from VRAM.
- **Target Platform Assumptions:** CachyOS (Arch Linux family), systemd service management, Btrfs filesystem (`/srv` on subvolume `@srv`), PipeWire audio server.

Refer to [`../config/hardware-baseline.txt`](../config/hardware-baseline.txt) for raw system survey data and [`../config/model-manifest.yaml`](../config/model-manifest.yaml) for model runtime metadata.

---

## 3. Current Implemented Architecture (IMPLEMENTED)

Phase 1 established the text chat core, LLM provider, conversation manager, and terminal CLI.

### 3.1 LLM Provider Boundary (`mowftee.llm`)
- **Protocol:** `LLMProvider` (`src/mowftee/llm/base.py`) defines standard methods: `chat()`, `stream_chat()`, `cancel()`, `health_check()`, `get_metrics()`.
- **Implementation:** `OllamaLLMProvider` (`src/mowftee/llm/ollama.py`) communicates via stdlib `urllib.request` HTTP REST API with Ollama running at `127.0.0.1:11434`. Zero external HTTP library dependencies.
- **Streaming & Cancellation:** NDJSON streaming parser computes real Time To First Token (TTFT). Thread-safe cancellation closes active HTTP sockets out-of-lock via `_active_requests` registry.
- **Metrics Tracking:** Snapshot metrics (`LLMMetrics`) track total requests, token counts, throughput (tokens/sec), and latency.

### 3.2 Conversation Manager (`mowftee.conversation`)
- **Atomic Turn Commit:** User and assistant message pairs (`user`, `assistant`) are committed to in-memory history (`_committed_history`) ONLY upon successful turn completion. Stream cancellations or HTTP failures leave committed history 100% unmutated.
- **Layered Context Assembly:** Context sent to LLM Provider is assembled dynamically:
  1. Base system policy (`_system_prompt`)
  2. Dynamic ISO local datetime context (when `inject_datetime: true`)
  3. Recent `max_turns` committed message pairs (sliding window)
  4. Pending user input
- **Turn Locking:** Single active turn per manager instance via `_active_lock`. Concurrent requests throw `ConversationBusyError`.
- **Minimal Terminal Runner:** `src/mowftee/cli.py` & `scripts/chat.sh` provide direct terminal chat interaction.

### 3.3 Configuration & Logging Integration
- Config loaded via `mowftee.config` (`PyYAML` loader, layered precedence).
- Structured JSONL logging via `mowftee.logging_setup` (`app.jsonl`, `performance.jsonl`, `audit.jsonl`).

Refer to [`LOG.md`](LOG.md) for empirical test logs and benchmark evidence.

---

## 4. Subsystem Boundaries & Future Design

Subsystems not yet implemented are defined by clear architectural boundaries to prevent monolithic coupling.

### 4.1 Persona Subsystem (PLANNED — Phase 2)
- **Responsibility:** Defines Mowftee's identity, default Vietnamese forms of address, tone, playfulness, and response constraints.
- **Boundary:** Persona defines *who Mowftee is*. It injects system policies into `ConversationManager` and enforces consistent persona evaluation criteria. Persona is distinct from Memory (facts) and Adaptation (interaction patterns).

### 4.2 Adaptation Subsystem (PLANNED)
- **Responsibility:** Gradually adapts interaction style based on observed user preferences using evidence and confidence scores.
- **Boundary:** Operates on evidence/confidence thresholds; does NOT perform continuous LLM fine-tuning or alter core identity.

### 4.3 Memory Subsystem (PLANNED — Phase 3)
- **Responsibility:** Manages persistent cross-session facts, user preferences, and conversation summaries in SQLite.
- **Boundary:** Memory defines *what Mowftee knows*. It provides `store_memory()`, `retrieve_memory()`, `update_memory()`, and `delete_memory()`. Memory stores selective facts, NOT raw full-transcript dumps.

### 4.4 Voice Subsystem (PLANNED — Phase 4 & 5)
- **Responsibility:** VAD, STT (speech-to-text), TTS (text-to-speech), audio queueing, and barge-in (interruption) handling.
- **Boundary:** Decoupled via `STTProvider` and `TTSProvider`. Supports sentence-chunked streaming TTS and non-blocking stream cancellation (< 300 ms target latency).

### 4.5 Tool Subsystem (PLANNED — Phase 6)
- **Responsibility:** Executes safe Linux system tools via strict allowlist and permission levels (L0 Chat to L5 Forbidden).
- **Boundary:** `ToolManager` validates parameters, enforces timeouts, logs to `audit.jsonl`, and requires explicit user confirmation for L4 system changes. Arbitrary shell execution (`run_shell`) is strictly forbidden (L5).

### 4.6 Avatar Subsystem (PLANNED — Phase 7)
- **Responsibility:** Renders visual state (listening, thinking, speaking) and audio-driven lip-sync.
- **Boundary:** Receives abstract state events from Application Core; failures in the Avatar layer do NOT crash conversational AI logic.

---

## 5. Data & Storage Architecture

### File System & XDG Layout
```text
/srv/mowftee/models/ollama/                              Public/reproducible Ollama models (ollama:ollama 0750)
${XDG_CONFIG_HOME:-$HOME/.config}/mowftee/config.yaml    User configuration overrides (mode 0700)
${XDG_DATA_HOME:-$HOME/.local/share}/mowftee/            Memory DB, persona files, custom voices (mode 0700)
${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/           JSONL logs, audit trails, benchmarks (mode 0700)
${XDG_CACHE_HOME:-$HOME/.cache}/mowftee/                 Temporary runtime cache (mode 0700)
```

### Btrfs Subvolume Policy
- Model storage path `/srv/mowftee/models/ollama/` resides under `/srv` on the dedicated `@srv` Btrfs subvolume (`/dev/nvme0n1p1[/@srv]`), keeping multi-gigabyte model blobs out of root OS snapshots (`@`).
- Reproducible public models and temporary cache files are excluded from backup payloads.

---

## 6. Configuration Architecture

Configuration uses a 4-tier layered precedence model (lowest to highest):

1. `config/default.yaml` (Packaged default resource, schema version 1)
2. `${XDG_CONFIG_HOME:-$HOME/.config}/mowftee/config.yaml` (Optional user YAML overrides)
3. `MOWFTEE_` Environment Variables (Double-underscore nested keys, e.g. `MOWFTEE_LLM__DEFAULT_MODEL`)
4. CLI Explicit Arguments

Config loader validates schema, performs non-destructive dict merges, parses scalar environment overrides safely, and raises `ConfigValidationError` on invalid inputs without leaking secrets in stack traces.

---

## 7. Logging & Observability Architecture

Logging uses three dedicated JSONL streams under `${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/`:

- **`app.jsonl`:** Lifecycle events, state transitions, application errors, recovery diagnostics.
- **`performance.jsonl`:** Model metrics, token counts, TTFT, throughput (tok/s), latency, hardware load.
- **`audit.jsonl`:** Tool execution logs, parameter validation, permission levels, user confirmations.

### Privacy & Security Constraints
- All log files use strict permissions (`0600` file, `0700` parent directory).
- UTC ISO 8601 timestamps and UUID request context tracking via `contextvars`.
- Key redaction automatically masks credentials, `Authorization`, `Cookie`, and secret keys.
- User conversation text, prompts, and raw audio are masked by default in production logs.
- File logging failures fall back gracefully to console output without crashing the application.

---

## 8. Security & Privacy Boundaries

1. **Loopback Binding:** Ollama LLM API binds strictly to `127.0.0.1:11434`. No external network interfaces exposed.
2. **Tool Safety & Allowlist:** No unvetted shell commands or arbitrary script execution. Tools require explicit parameter schemas and permission gating (L0–L5).
3. **Privilege Gating:** Application runs under normal user privileges; `sudo` execution is forbidden.
4. **Data Isolation:** User memories, private configs, custom voices, and conversation histories are stored strictly under `$HOME` and excluded from public Git repositories.

---

## 9. Recovery Architecture

Mowftee disaster recovery follows a clear separation between code, public assets, and private data:

- **Source Code & History:** Recovered via Git repository checkout and annotated version tags (`vX.Y.Z`).
- **Runtime Environment:** Re-created using `uv sync --locked` from `pyproject.toml` / `uv.lock`.
- **Public Models:** Re-downloaded via Ollama manifest specs; excluded from backup archives.
- **Private Data Recovery:** Restored from GPG AES-256 encrypted archives containing non-reproducible private state when present (SQLite memory databases, private user configs, custom persona files).
- **Tooling Contract:** Official backup (`scripts/backup.sh`) and restore (`scripts/restore.sh`) scripts accept `--target` and `--archive` arguments. Encrypted archives (`.tar.gz.gpg`) and SHA-256 sidecars (`.tar.gz.gpg.sha256`) remain paired with generated names unchanged.
- **Operator Directory Convention:** Off-machine backup archives are organized by the operator under `$HOME/Mowftee Backups/Phase N - vX.Y.Z/`.

Refer to [`LOG.md`](LOG.md) for historical backup validation logs.

---

## 10. Architectural References & Design Direction (REFERENCE / DIRECTION)

The Sanbaka / Project AIRI design notes serve as conceptual architectural reference material (design direction), NOT an implementation commitment or roadmap change:

1. **Cooperating Subsystems:** Decouple Brain / Conversation, Persona-State, Memory, Voice, Tools, and Body (Avatar) into interacting providers.
2. **Dynamic Persona:** Persona should evolve beyond a single static prompt into core identity, current state, user preferences, familiarity/relationship context, and current conversation context.
3. **Evidence-Based Adaptation:** User adaptation requires evidence and confidence scoring rather than instant permanent shifts.
4. **Subsystem Separation:** Maintain strict conceptual separation between Memory (what Mowftee knows), Persona (who Mowftee is), and Adaptation (how Mowftee interacts).
5. **Future Memory Categories & Consolidation:** Memory taxonomy distinguishes working/session memory, stable user facts, preferences, episodic memories, and task/project memory. Consolidation and forgetting mechanisms are added only when justified by empirical testing.
6. **Voice Streaming & Barge-In:** Voice pipeline supports sentence-chunked streaming TTS and interruption/barge-in detection rather than a purely linear sequence.
7. **Abstract Avatar Signals:** Avatar layer consumes abstract state and expression signals (listening/thinking/speaking), avoiding direct coupling to LLM text parsing or `ConversationManager`.
8. **Learn Concepts, Not Stack:** Learn conceptual architecture from AIRI/Sanbaka without adopting their full tech stack; preserve CachyOS native, local-first, Python modular monolith architecture.
9. **Continuity Over Time:** Mowftee develops conversational continuity across interactions over time rather than simulating a complete static personality on day one.

---

## 11. Decision Log

### DEC-001 — Product Identity and Technical Naming
- **Status:** Accepted
- **Decision:** Product official name is Mowftee (pronounced Maou-ph-ti). Technical identifiers are `mowftee` (repo/package/CLI), `mowftee.service` (systemd), and `MOWFTEE_` (env prefix).
- **Reason:** Consistency across codebase, documentation, services, and paths.

### DEC-002 — Modular Monolith Architecture
- **Status:** Accepted
- **Decision:** Build Mowftee as a modular monolith in Python with clear provider abstractions (`Protocol`).
- **Reason:** Low complexity, single-developer efficiency, zero IPC overhead, while allowing modular engine replacement.

### DEC-003 — Pretrained Quantized Models over Training from Scratch
- **Status:** Accepted
- **Decision:** Use pretrained quantized LLM models (3B–4B parameter range) rather than training models from scratch.
- **Reason:** Hardware constraints (RTX 3050 4 GB VRAM / 16 GB RAM).

### DEC-004 — Ollama as Initial Local LLM Runtime
- **Status:** Accepted
- **Decision:** Adopt Ollama as the primary candidate LLM runtime; `llama.cpp` server as fallback candidate.
- **Reason:** Simplified local model management and HTTP REST API.

### DEC-005 — Storing Model Weights Outside Git Repository
- **Status:** Accepted
- **Decision:** Store downloaded model weights under `/srv/mowftee/models/ollama/`. Exclude weights from Git and backups.
- **Reason:** Large reproducible binaries belong in dedicated model storage.

### DEC-006 — Btrfs Copy-on-Write Policy for SQLite
- **Status:** Accepted
- **Decision:** Retain default Btrfs CoW configuration for SQLite memory files until benchmark evidence justifies changes.
- **Reason:** Prevent premature optimization and preserve snapshot/reflink capabilities.

### DEC-007 — Allowlisted Tools without Arbitrary Shell Execution
- **Status:** Accepted
- **Decision:** All system tools must be allowlisted with explicit schemas, parameter validation, and audit logging. Arbitrary `run_shell` is forbidden.
- **Reason:** System security and auditability.

### DEC-008 — Isolated CPython 3.11 Environment Managed by `uv`
- **Status:** Accepted
- **Decision:** Use dedicated CPython 3.11 (`>=3.11,<3.12`) managed by `uv` in `.venv/` with committed `uv.lock`. System Python 3.14 is forbidden for project packages. Build backend is Hatchling.
- **Reason:** Isolate project dependencies from CachyOS rolling release system Python updates.

### DEC-009 — Portable XDG Storage Layout and `@srv` Model Subvolume
- **Status:** Accepted
- **Decision:** Store user config under `XDG_CONFIG_HOME`, data under `XDG_DATA_HOME`, state under `XDG_STATE_HOME`, and cache under `XDG_CACHE_HOME`. Public models reside at `/srv/mowftee/models/ollama` on `@srv` subvolume (`ollama:ollama 0750`).
- **Reason:** Clean separation of user data, logs, and reproducible model weights across Btrfs subvolumes.

### DEC-010 — Layered YAML Configuration & Privacy-Aware JSONL Logging
- **Status:** Accepted
- **Decision:** PyYAML loader with 4-tier precedence (`default.yaml` -> user `config.yaml` -> `MOWFTEE_` env -> CLI args). Three JSONL logging streams (`app.jsonl`, `performance.jsonl`, `audit.jsonl`) with automatic secret redaction, UUID request context, and console fallback.
- **Reason:** Reproducible configuration and auditability without leaking secrets or crashing on file handler errors.

### DEC-011 — Local Encrypted Staging before Off-Machine Backup
- **Status:** Accepted
- **Decision:** Backup tool creates tar gzip archives encrypted with GPG AES-256, sidecar SHA-256 checksums, and SQLite `Connection.backup()` snapshots. Restores decrypt to temporary directories for manifest and checksum verification prior to publishing.
- **Reason:** Data integrity and security prior to off-machine transmission.

### DEC-012 — Off-Machine Backup Target & Cloud Round-Trip Validation
- **Status:** Accepted
- **Decision:** Private Google Drive chosen as off-machine backup target. Verification requires production backup -> local restore sanity check -> upload -> delete local original -> download -> restore -> data diff validation.
- **Reason:** Ensure disaster recovery capability from cloud storage.

### DEC-013 — Canonical Package Versioning Policy
- **Status:** Accepted
- **Decision:** `pyproject.toml` is the single canonical source of truth for version metadata. `src/mowftee/__init__.py` and `config/model-manifest.yaml` must remain in sync. Milestone releases use annotated Git tags (`vX.Y.Z`).
- **Reason:** Explicit, simple version tracking without dynamic build machinery.

### DEC-014 — Native CachyOS Ollama + Vulkan Runtime Setup
- **Status:** Accepted
- **Decision:** Install native CachyOS `ollama` and `ollama-vulkan` packages on Vulkan backend (RTX 3050 Laptop GPU). Service bound loopback-only to `127.0.0.1:11434` with model storage at `/srv/mowftee/models/ollama`.
- **Reason:** Native package lifecycle management and Vulkan GPU acceleration.

### DEC-015 — Default LLM Selection and Fallback Policy
- **Status:** Accepted
- **Decision:** Selected default model: `qwen3:4b-instruct` (digest `0edcdef34593`, `Q4_K_M`). Performance fallback model: `llama3.2:3b` (digest `a80c4f17acd5`, `Q4_K_M`). Automatic switching mechanism is not implemented in Phase 1.
- **Reason:** Empirical benchmark results (TTFT, throughput, instruction compliance, reasoning accuracy, and Vietnamese fluency).

### DEC-016 — LLM Provider Implementation & Runtime Boundary
- **Status:** Accepted
- **Decision:** Implemented `OllamaLLMProvider` using stdlib `urllib.request` REST client under `@runtime_checkable` `LLMProvider` Protocol. Runtime config source is strictly `config/default.yaml` (`llm` section). Model manifest is a selection record, not read at runtime.
- **Reason:** Zero external HTTP dependencies, clean provider isolation, and thread-safe cancellation.

### DEC-017 — Conversation Manager Atomic Turn Lifecycle & System Policy Layering
- **Status:** Accepted
- **Decision:** Implemented `ConversationManager` with atomic turn commits (turns appended to committed history ONLY on successful completion). Thread-safe turn locking via `_active_lock`. Layered context assembly (system policy + ISO datetime injection + recent `max_turns` + pending message).
- **Reason:** Prevent history corruption on stream failure or cancellation, ensure thread safety, and inject real-time context.

### DEC-018 — Phase 1 Validation & Release v0.1.0 Closure Boundary
- **Status:** Accepted
- **Decision:** Officially closed Phase 1 with release `v0.1.0` tag after passing Phase 1 Definition of Done and G1-05 benchmark tests. Saved benchmark artifact at `${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/benchmarks/g1-05-phase1-benchmark.json`.
- **Reason:** Complete Phase 1 Definition of Done verification and establish stable release baseline prior to Phase 2.

---

## 12. Source-of-Truth Pointers

- **Mandatory Working Rules:** [`../CLAUDE.md`](../CLAUDE.md)
- **Development Router:** [`../README.md`](../README.md)
- **Roadmap & Definition of Done:** [`PLAN.md`](PLAN.md)
- **Current Handoff & Session State:** [`SESSION_PROMPT.md`](SESSION_PROMPT.md)
- **Engineering History & Empirical Evidence:** [`LOG.md`](LOG.md)
- **Runtime Model Metadata:** [`../config/model-manifest.yaml`](../config/model-manifest.yaml)
- **Raw Hardware Survey:** [`../config/hardware-baseline.txt`](../config/hardware-baseline.txt)
