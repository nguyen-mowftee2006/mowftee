# PLAN — Mowftee Canonical Roadmap & DoD

- **Purpose:** Canonical roadmap, phase scope, dependencies, Definition of Done, risks, and non-goals.
- **Authority:** Canonical for roadmap/DoD only.
- **Audience:** HQ / worker / developer.
- **Update trigger:** Roadmap, phase scope, dependency, DoD, risk, non-goal, or phase status changes.
- **Must not contain:** Detailed benchmark evidence, historical command logs, raw hardware dumps, implementation transcripts, or duplicated architecture specs.

---

## 1. Roadmap Position

- **Phase 0 — Project Foundation:** COMPLETE (`v0.0.1`)
- **Phase 1 — Local Text Chat Core:** COMPLETE (`v0.1.0`)
- **Phase 2 — Persona & Conversation Quality:** NEXT / NOT STARTED (`v0.2.x`)
- **Phases 3–9:** Future roadmap (`v0.3.x` to `v1.0.0`)

*Note:* The current documentation refactor on `dev` branch is pre-Phase-2 repository maintenance and documentation normalization, not a new product phase. Git commit refs must be verified directly via Git.

---

## 2. Project Vision & Non-Goals

### Project Vision
Mowftee is an open-source, local-first Vietnamese AI companion with a distinct personality, designed for CachyOS / Arch Linux.

### Non-Goals
- Training LLMs from scratch.
- Copying Neuro-sama or any existing VTuber identity, voice, avatar, or assets.
- Executing arbitrary shell commands or unvetted `sudo` actions.
- Exposing local AI APIs to the public Internet during early phases.
- Running models exceeding local hardware capacity (RTX 3050 4 GB VRAM / 16 GB RAM).
- Adding complex microservices, Docker, or Kubernetes overhead.

---

## 3. Global Definition of Done & Release Gates

Every phase must satisfy these consolidated completion gates before closure:

1. **Functional Scope:** Implemented all features defined for the phase.
2. **Automated Testing:** Unit and integration test suite passes (`uv run pytest`, `uv run ruff check .`).
3. **Performance & Resources:** Resource usage, latency, and TTFT measured and acceptable.
4. **Stability:** No unresolved critical crashes, OOMs, or unhandled exceptions under standard runs.
5. **Documentation:** Updated canonical documentation (`PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `LOG.md`, `SESSION_PROMPT.md`) according to update triggers.
6. **Recovery & Backup:** Backup and restore implications validated when non-reproducible data is introduced.
7. **Version Control:** Clean Git state, committed code on `dev`, and annotated Git tag created (`vX.Y.Z`) when closing a milestone release phase.

---

## 4. Phase Breakdown

### Phase 0 — Project Foundation (`v0.0.x`)

- **Status:** COMPLETE
- **Target Release:** `v0.0.1`
- **Goal:** Establish repository structure, CPython 3.11 environment (`uv`), storage layout (`/srv/mowftee/models/ollama`), YAML configuration, JSONL logging, and local/off-machine encrypted backup capabilities.
- **Delivered Outcome:** Tag `v0.0.1` released; local and Google Drive off-machine backup round-trip validated.
- **Evidence:** Refer to [`LOG.md`](LOG.md).

---

### Phase 1 — Local Text Chat Core (`v0.1.x`)

- **Status:** COMPLETE
- **Target Release:** `v0.1.0`
- **Goal:** Implement terminal text chat interface, local Ollama LLM provider (`OllamaLLMProvider`), streaming NDJSON responses, in-memory conversation manager (`ConversationManager`), default model selection (`qwen3:4b-instruct`), and comprehensive test/benchmark suite.
- **Delivered Outcome:** Tag `v0.1.0` released; 5-minute soak, 20-turn functional, 50-turn stability, reboot persistence, and service recovery tests PASS; official benchmark artifact saved at `${XDG_STATE_HOME:-$HOME/.local/state}/mowftee/benchmarks/g1-05-phase1-benchmark.json`.
- **Evidence:** Refer to [`LOG.md`](LOG.md).

---

### Phase 2 — Persona & Conversation Quality (`v0.2.x`)

- **Status:** NEXT / NOT STARTED
- **Target Release:** `v0.2.0`
- **Goal:** Create a distinct, consistent, natural Vietnamese persona for Mowftee without copying external identities.

#### Approved Product & Persona Principles
- Mowftee is a female-presenting AI companion, Vietnamese-first.
- Natural, human-like interaction continuity supersedes raw intelligence benchmarks.
- Neuro-sama is a behavioral/personality reference only, NOT an identity to copy.
- Adaptation gradually learns user preferences using evidence/confidence/context, NOT continuous fine-tuning.
- Subsystem separation: Persona (who Mowftee is), Memory (what Mowftee knows), and Adaptation (how Mowftee interacts) remain distinct concepts.

#### Scope
- Persona V1 specification (`persona_version: 1`).
- Default Vietnamese forms of address.
- Response length and playfulness/mischief parameters.
- Graceful degradation on unknown topics ("I don't know" rather than hallucinating tool execution or fake facts).
- Few-shot conversation examples.
- Persona test suite (minimum 20 turns).
- Catchphrase repetition prevention.

#### Out of Scope (Strict Boundaries)
- Persistent long-term memory (deferred to Phase 3).
- Voice / STT / TTS (deferred to Phase 4 & 5).
- Safe Linux tools (deferred to Phase 6).
- Avatar & lip-sync (deferred to Phase 7).

#### Gates & Dependencies
- Phase 1 complete (`v0.1.0`).
- Documentation refactor on `dev` branch complete.

#### Definition of Done
- [ ] Persona V1 defined (`persona_version: 1`).
- [ ] Maintains consistent default Vietnamese forms of address across turns.
- [ ] Does NOT revert to corporate/enterprise assistant tone.
- [ ] Does NOT claim to be Neuro-sama or copy external assets.
- [ ] Does NOT hallucinate unexecuted tool calls or fake memories.
- [ ] Persona test suite (minimum 20 turns) PASS.
- [ ] Release version `0.2.0` synchronized and tag `v0.2.0` created upon completion.

---

### Phase 3 — Persistent Memory (`v0.3.x`)

- **Status:** FUTURE
- **Target Release:** `v0.3.0`
- **Goal:** Enable selective cross-session memory with user inspection, edit, delete, and backup capabilities.
- **Scope:** SQLite memory store, schema migrations, selective memory extraction, user CRUD interface for memories, memory export/import/backup.
- **Boundaries & Relationship to Persona:** Memory stores facts (what Mowftee knows), distinct from Persona (who Mowftee is). Must NOT automatically save all chat transcripts.
- **Definition of Done:** Selective memory persists across restarts; CRUD interface functional; restore from backup PASS; database excluded from Git; tag `v0.3.0` created.

---

### Phase 4 — Per-Turn Voice (`v0.4.x`)

- **Status:** FUTURE
- **Target Release:** `v0.4.0`
- **Goal:** Per-turn voice pipeline: Microphone -> VAD -> STT -> LLM -> TTS -> Speaker.
- **Scope:** PipeWire audio integration, VAD benchmarking, Vietnamese STT/TTS selection, fallback to keyboard/text on audio failure.
- **Definition of Done:** 20-turn voice test stable; STT/TTS latency measured; fallback graceful; tag `v0.4.0` created.

---

### Phase 5 — Real-Time Voice & Barge-In (`v0.5.x`)

- **Status:** FUTURE
- **Target Release:** `v0.5.0`
- **Goal:** Real-time streaming voice with barge-in (interruption) support and echo prevention.
- **Scope:** Sentence-chunked TTS streaming, audio queue management, cancellation tokens, barge-in detection (<= 300 ms target latency).
- **Definition of Done:** Interruption latency <= 300 ms; no speaker-to-microphone feedback loops; voice module failure does not crash text chat; tag `v0.5.0` created.

---

### Phase 6 — Safe Linux Tools (`v0.6.x`)

- **Status:** FUTURE
- **Target Release:** `v0.6.0`
- **Goal:** Allow Mowftee to perform safe, audited Linux tasks via allowlisted tools without arbitrary shell execution.
- **Scope:** Privilege levels (L0 Chat to L4 System Change with confirmation), initial tools (`get_system_status`, `get_gpu_status`, `open_project`, `find_file`, `read_document`, `create_note`), parameter validation, timeouts, audit logging.
- **Definition of Done:** No arbitrary shell tool; allowlist and audit log functional; dangerous actions require explicit confirmation; tag `v0.6.0` created.

---

### Phase 7 — Avatar & Expression (`v0.7.x`)

- **Status:** FUTURE
- **Target Release:** `v0.7.0`
- **Goal:** Display an avatar reflecting Mowftee's conversational state (listening, thinking, speaking) and emotions.
- **Scope:** PNGTuber / Live2D / VRM evaluation, audio-driven lip-sync, state machine integration.
- **Definition of Done:** Avatar state reflects AI core state; avatar failure does not crash AI core; performance impact measured; tag `v0.7.0` created.

---

### Phase 8 — Resource Optimization & Stability (`v0.8.x`)

- **Status:** FUTURE
- **Target Release:** `v0.8.0`
- **Goal:** Optimize memory retention, context trimming, model load/unload policies, and long-term stability.
- **Scope:** 4-hour soak testing, crash recovery, database maintenance, Btrfs fragmentation review.
- **Definition of Done:** No RAM leaks under 4-hour soak test; automatic recovery functional; tag `v0.8.0` created.

---

### Phase 9 — Packaging & System Recovery (`v1.0.0`)

- **Status:** FUTURE
- **Target Release:** `v1.0.0`
- **Goal:** Package full application with automated setup, diagnostic, backup, and full system disaster recovery scripts.
- **Scope:** Complete helper scripts (`doctor.sh`, `setup-python.sh`, `download-models.sh`, `backup.sh`, `restore.sh`), clean OS restoration workflow.
- **Definition of Done:** Application, memory, persona, and models fully restored from clean OS installation using documented recovery sequence; tag `v1.0.0` created.

---

## 5. Backup & Recovery Policy

- **Requirement:** Private/non-reproducible data (custom persona, memory database, real config, custom voice/LoRA) MUST be backed up off-machine.
- **Validation:** Every backup implementation requires local and off-machine restore validation.
- **Directory Convention:** `$HOME/Mowftee Backups/Phase N - vX.Y.Z/` is recommended for operator off-machine storage organization. This is an operator convention, NOT a hard-coded application runtime path.
- **Public Models:** Reproducible public Ollama models are excluded from backup payloads.
- **Status:** Phase 1 `v0.1.0` off-machine backup validation is COMPLETE.

Refer to Recovery Architecture in [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) and [`LOG.md`](LOG.md).

---

## 6. Key System Risks & Mitigations

| Risk | Mitigation Strategy |
|---|---|
| 4 GB VRAM / 16 GB RAM limitation | Limit model scale to 3B–4B quantized models; CPU offload when necessary. |
| System Python version drift | Enforce dedicated CPython 3.11 environment managed by `uv`. |
| Unvetted shell execution hazards | Strict tool allowlist, parameter validation, confirmation dialogs, audit logs. |
| Model files inflating system snapshots | Store models outside root snapshot under `/srv/mowftee/models/ollama/`. |
| Database corruption or data loss | Consistent SQLite backups (`sqlite3.Connection.backup()`) and restore tests. |

---

## 7. Source-of-Truth Pointers

- **Mandatory Working Rules:** [`../CLAUDE.md`](../CLAUDE.md)
- **Development Router:** [`../README.md`](../README.md)
- **Current Handoff & Session State:** [`SESSION_PROMPT.md`](SESSION_PROMPT.md)
- **Technical Architecture & Decisions:** [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)
- **Engineering History & Evidence:** [`LOG.md`](LOG.md)
- **Runtime Model Metadata:** [`../config/model-manifest.yaml`](../config/model-manifest.yaml)
- **Raw Hardware Survey:** [`../config/hardware-baseline.txt`](../config/hardware-baseline.txt)
