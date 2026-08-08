# SESSION PROMPT — Mowftee Handoff State

- **Purpose:** Current development handoff and active project state.
- **Authority:** Canonical for current handoff/state only.
- **Audience:** Zero-context HQ / worker / developer.
- **Update trigger:** Meaningful change to active objective, handoff state, blocker, release/dev state, or recovery state.
- **Must not contain:** Full historical logs, detailed benchmark transcripts, duplicated architecture, or duplicated roadmap specifications.

## 1. Bootstrap

- Read [`../CLAUDE.md`](../CLAUDE.md) for mandatory working rules and safety protocols.
- Read [`../README.md`](../README.md) as the development documentation router.
- Verify live Git and system runtime state directly rather than trusting stale dynamic claims.

## 2. Current Project State

- **Stable Release:** `v0.1.0` (tag `v0.1.0`).
- **Phase 1 Status:** COMPLETE.
- **Phase 2 Status:** NEXT / NOT STARTED (no Phase 2 implementation has started).
- **Branch Model:** `dev` is the active development branch (published to `origin/dev`); `main` points to stable `v0.1.0`.
- **Package Version:** `0.1.0` (remains synchronized until an explicit version transition is approved).
- **Documentation Refactor:** Refactor, audit, review/commit, and `dev` publication are COMPLETE.
- **Cold-Start Validation:** HQ cold-start acceptance PASS / COMPLETE; Worker cold-start acceptance PASS / COMPLETE; Zero-question cold-start acceptance COMPLETE.

## 3. Current Development Objective

**Current Objective:** Prepare Phase 2 Persona implementation according to PLAN and architecture. Phase 2 implementation has NOT started yet.

**Cold-Start Acceptance & Transition Flow:**
1. Documentation refactor & publication on `dev` (COMPLETE)
2. Initial HQ cold-start test & handoff defect correction (COMPLETE)
3. HQ cold-start final re-test acceptance (PASS / COMPLETE)
4. Worker cold-start test acceptance (PASS / COMPLETE)
5. Prepare Phase 2 Persona implementation (NEXT)

*Note for future HQ/workers:* Inspect current working tree and Git diff (`git status -sb`, `git diff`) to resume from the first unfinished acceptance step without asking the operator.

## 4. Released Capability Baseline

**Implemented Phase 1 Capabilities:**
- Local terminal text chat interface (`mowftee` CLI / `scripts/chat.sh`).
- Local Ollama provider with streaming NDJSON responses (`mowftee.llm`).
- In-memory sliding-window context management with atomic turn commits (`mowftee.conversation`).
- Context clear/reset and non-blocking stream cancellation.
- Selected default local model (`qwen3:4b-instruct`).
- Validated Phase 1 runtime, functional, stability, reboot persistence, and service recovery baseline.

Refer to [`LOG.md`](LOG.md) for empirical benchmark evidence and [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) for technical design.

**Capabilities NOT YET IMPLEMENTED:**
- Persona engine (Phase 2).
- Persistent long-term memory (Phase 3).
- Per-turn voice (Phase 4) & real-time voice/barge-in (Phase 5).
- Safe Linux tools (Phase 6).
- Avatar & lip-sync (Phase 7).

## 5. Product & Persona Direction for Next Work

- **Identity:** Mowftee is a female-presenting AI companion, Vietnamese-first.
- **Interaction Priority:** Natural, human-like interaction continuity supersedes raw intelligence benchmarks.
- **Behavioral Reference:** Neuro-sama is a personality/behavior reference only; Mowftee must establish its own unique identity.
- **Adaptation Design:** Learn user preferences gradually using evidence/confidence/context without continuous fine-tuning.
- **Subsystem Separation:** Persona (who Mowftee is), Memory (what Mowftee knows), and Adaptation (how Mowftee interacts) remain distinct subsystems.

Refer to the AIRI/Sanbaka design-reference material in [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md).

## 6. Runtime Essentials

- **Target OS:** CachyOS (Arch Linux family).
- **Environment:** CPython 3.11 (`>=3.11,<3.12`), managed by `uv` in `.venv/`.
- **LLM Runtime:** Ollama on `127.0.0.1:11434` (native CachyOS `ollama-vulkan`).
- **Default Model:** `qwen3:4b-instruct` (digest `0edcdef34593`).
- **Fallback Model:** `llama3.2:3b` (manual configuration fallback; no automatic switching).
- **Model Directory:** `/srv/mowftee/models/ollama/` (`ollama:ollama 0750`).
- **Canonical CLI:** `mowftee` (shorthand `mow` is a future direction, not implemented).

Refer to [`../config/model-manifest.yaml`](../config/model-manifest.yaml), [`../config/hardware-baseline.txt`](../config/hardware-baseline.txt), and [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md). Dynamic service/model state MUST be verified from the machine.

## 7. Important Known Constraints & Unresolved Evidence

- **Repetition Behavior:** Long-input fake-turn repetition was NOT REPRODUCED under structured `/api/chat` testing. Do NOT alter stop sequences, template, or repetition settings without empirical reproduction.
- **Resource Load:** Controlled follow-up runs observed peak CPU temperature of 85°C and peak GPU temperature of 76°C, with no observed instability or active thermal slowdown in those controlled runs. Available evidence did not demonstrate a persistent memory leak.

Refer to [`LOG.md`](LOG.md) for detailed test logs and evidence.

## 8. Recovery & Backup State

- **Code Recovery:** Git tag `v0.1.0` is the canonical Phase 1 code recovery point.
- **Latest Off-Machine Backup:** Phase 1 `v0.1.0`.
- **Cloud Validation:** Google Drive upload/download round-trip restore PASS.
- **Directory Convention:** `$HOME/Mowftee Backups/Phase N - vX.Y.Z/` (archive and sidecar pair remain together with tool-generated filenames unchanged). Public Ollama models are excluded from backup payloads.

Refer to Recovery Architecture in [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) and [`LOG.md`](LOG.md).

## 9. Source-of-Truth Pointers

- **Mandatory Working Rules:** [`../CLAUDE.md`](../CLAUDE.md)
- **Development Router:** [`../README.md`](../README.md)
- **Roadmap & Definition of Done:** [`PLAN.md`](PLAN.md)
- **Technical Architecture & Decisions:** [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)
- **Engineering History & Evidence:** [`LOG.md`](LOG.md)
- **Runtime Metadata:** [`../config/model-manifest.yaml`](../config/model-manifest.yaml)
- **Raw Hardware Survey:** [`../config/hardware-baseline.txt`](../config/hardware-baseline.txt)

## 10. Handoff Resolution Rule

A new HQ or worker MUST NOT ask the operator to repeat information already answerable by the repository or system state:
- For dynamic environment facts: **VERIFY** (`git status`, `systemctl`, `nvidia-smi`).
- For canonical rules and decisions: **READ** (`CLAUDE.md`, `PLAN.md`, `SYSTEM_ARCHITECTURE.md`).
- For unresolved product/architectural choices: **DECIDE** / escalate with clear options.
- If internal documentation conflicts occur: **REPORT** the conflict rather than guessing.
