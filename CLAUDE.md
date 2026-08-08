# Mowftee Development Working Standard

Status: STABLE
Scope: Entire repository
Standard mutation policy: Explicit user/HQ approval only

### 1. Purpose
Defines HOW engineering work is performed across Mowftee. This document contains stable working rules, authority boundaries, safety protocols, and documentation standards. It MUST NOT contain transient or changing project status (e.g., active version, current phase, commit hash, temporary backup path, or benchmark results).

### 2. Cold-Start Protocol
Any zero-context agent or developer entering the repository MUST:
1. Read `/CLAUDE.md` to establish operational rules and constraints.
2. Read `/README.md` as the development documentation router.
3. Read `/docs/SESSION_PROMPT.md` for current handoff state, active invariants, and next steps.
4. Follow relative links to `/docs/PLAN.md`, `/docs/SYSTEM_ARCHITECTURE.md`, or `/docs/LOG.md` as required by task scope.
5. Inspect actual Git status (`git status -sb`, `git branch -vv`) before any mutation.
6. Inspect actual machine/runtime state when task execution depends on system context.
7. Continue the documented active objective unless the explicit current task overrides it.

### 3. Instruction Authority
When executing tasks, authority is evaluated in the following order:
1. **Explicit Current User/HQ Prompt:** Highest authority for task scope and immediate goals.
2. **`CLAUDE.md`:** Governing operational constitution and safety rules.
3. **Canonical Project Docs (`PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `LOG.md`):** Authoritative for design, roadmap, DoD, and history.
4. **Code & Unit Tests:** Authoritative for implemented software behavior.
5. **Worker Inference:** Fallback for unspecified implementation details.

Instruction authority MUST NOT be confused with factual authority (e.g., user prompts cannot overwrite historical benchmark facts).

Worker/HQ inference may be used to generate hypotheses or implementation options, but MUST NEVER be reported as verified project fact without empirical evidence. When a dynamic fact cannot actually be inspected, report `NOT VERIFIED` rather than guessing.

### 4. Factual Source-of-Truth Rules
Factual claims MUST derive strictly from their canonical Source of Truth (SoT):
- **Roadmap & DoD:** `/docs/PLAN.md`
- **Architecture & System Policies:** `/docs/SYSTEM_ARCHITECTURE.md`
- **History, Benchmarks & Incidents:** `/docs/LOG.md`
- **Current Handoff & Session State:** `/docs/SESSION_PROMPT.md`
- **Development Documentation Router:** `/README.md` (on `dev`)
- **Machine-Readable Model/Runtime Metadata:** `/config/model-manifest.yaml`
- **Raw Hardware Evidence:** `/config/hardware-baseline.txt`
- **Code & Test Behavior:** Source code (`src/mowftee/`) and tests (`tests/`).
- **Git History:** Actual Git repository refs and commit logs.
- **Machine/Runtime State:** Live system inspection (`systemctl`, `nvidia-smi`, `free`, `ss`).

Worker reports are unverified claims until supported by explicit factual evidence.

### 5. Known / Verify / Decide Framework
Categorize information to minimize unnecessary operator questions:
- **KNOWN:** Decided in canonical sources. Do NOT ask again.
- **VERIFY:** Dynamic environment facts. Inspect Git, filesystem, or system runtime directly.
- **DECIDE:** Genuinely unresolved product/architectural choices or missing credentials/approvals. Escalate with specific options when required.

### 6. No-Ask Resolution Protocol
Before asking the operator a question, agents MUST use the shortest sufficient authoritative path in the listed order and STOP once the question is resolved:
1. Task prompt
2. `/CLAUDE.md`
3. `/README.md` (development documentation router)
4. `/docs/SESSION_PROMPT.md`
5. Canonical docs (`PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `LOG.md`)
6. Implementation code & tests
7. Git repository state
8. Machine & runtime state
9. Upstream official documentation (consult ONLY when the task actually depends on upstream behavior/specification)

Repository-answerable or machine-verifiable facts MUST NOT be asked back to the operator. Ask the operator ONLY if the issue remains unresolved, conflicting, secret-dependent, preference-dependent, or requires explicit safety approval.

### 7. Scope Discipline
- Execute ONLY the explicitly requested task scope.
- Do NOT perform opportunistic, unrelated refactoring or silent cleanup.
- Do NOT expand task boundaries without explicit user/HQ authorization.

### 8. STOP Policy
STOP immediately and report without applying speculative fixes on:
- Unexpected command failures or unexpected non-zero exit status (expected non-zero exit semantics that are explicitly anticipated are not failures by themselves).
- Unexpected Git working tree or branch state.
- Unexpected file mutation or corruption.
- Out-of-scope system or resource anomalies.
- Insufficient empirical evidence to support a required claim.

Do NOT silently repair and continue unless explicitly instructed.

### 9. Git & Branching Strategy
- **`main`:** Released, stable production state. No direct active feature development.
- **`dev`:** Active integration and development branch.
- **Feature/Fix/Docs branches (`feat/*`, `fix/*`, `docs/*`, `experiment/*`):** Branch off `dev`, merge back into `dev`, and delete post-verification.
- **Tags (`vX.Y.Z`):** Immutable historical release anchors.

Strict Constraints:
- NO Git mutation beyond explicit task scope. This covers commit, push, tag, branch creation/deletion, state-changing switch/checkout, merge, reset, rebase, stash, and force operations.
- NEVER force-push (`-f`).
- NEVER rewrite published history.
- Do NOT use obsolete branches as data archives.

Branch-Specific README Ownership:
- `/README.md` on `dev` serves as the **Development Documentation Router**.
- `/README.md` on `main` serves as the **Release & Public-Facing Surface**.
- Release promotion MUST preserve/prepare the intended `main` `README.md` surface; do NOT blindly overwrite `main` `README.md` with the `dev` router.

### 10. Mutation Safety
- Perform pre-mutation verification (`git status`, `git diff`) before making changes.
- Perform post-mutation verification proportional to task scope.
- Sudo, system package updates, systemd service changes, or user/group modifications REQUIRE explicit user authorization.

### 11. Evidence & Verification Standard
Verification MUST be proportional to task scope:
- **Textual / Documentation Changes:** At minimum relevant diff inspection + `git diff --check`.
- **Code Changes:** Relevant unit tests and lint checks (`pytest <target>`, `ruff check <target>`).
- **Full Test Suite (`pytest`, `ruff`, full checks):** Executed when required by task instructions, milestone closure, release preparation, or broad scope impact.

Empirical evidence strictly supersedes narrative claims. A task component is "PASS" ONLY when demonstrated by actual check/test output. Clearly distinguish between `NOT VERIFIED`, `NOT REPRODUCED`, and `BLOCKED`. NEVER make absolute, unverified claims.

### 12. Documentation Standards & Change Matrix
Each documentation file has one exclusive responsibility:
- `/CLAUDE.md`: Stable engineering constitution & working rules.
- `/README.md`: Development documentation router (on `dev`).
- `/docs/PLAN.md`: Canonical roadmap, phase goals, DoD, risks, non-goals.
- `/docs/SYSTEM_ARCHITECTURE.md`: Living technical architecture & design specs.
- `/docs/LOG.md`: Append-only engineering log & benchmark evidence.
- `/docs/SESSION_PROMPT.md`: Compact AI session handoff & active state.
- `/config/model-manifest.yaml`: Machine-readable runtime metadata.
- `/config/hardware-baseline.txt`: Raw hardware survey dump.

Documentation Change Matrix:
| Trigger / Event | Primary File to Update | Secondary References |
|---|---|---|
| New architectural decision / subsystem design | `docs/SYSTEM_ARCHITECTURE.md` | `docs/LOG.md` (log entry) |
| Phase goal / DoD / roadmap status update | `docs/PLAN.md` | `README.md` (summary), `SESSION_PROMPT.md` |
| Completed test run / benchmark / incident | `docs/LOG.md` | `SYSTEM_ARCHITECTURE.md` (if DEC added) |
| Session handoff / active task change | `docs/SESSION_PROMPT.md` | None |
| Public API / CLI / high-level status change | `README.md` | None |

Rules:
- One authoritative home per fact; use relative links rather than copy-pasting text.
- Secondary references are NOT automatic updates; a secondary document is changed ONLY when its own responsibility is materially affected.
- Historical evidence belongs ONLY in `LOG.md`.
- Transient session state MUST NOT be committed to durable docs (`PLAN.md` or `SYSTEM_ARCHITECTURE.md`).

### 13. LOG Policy
- `docs/LOG.md` is strictly APPEND-ONLY.
- Historical entries MUST NOT be edited or deleted; corrections are appended as new dated entries.
- Entries MUST be factual, evidence-oriented, and concise.

### 14. Temporary & Scratch Artifacts
- Store task-created scratch scripts and temporary test files in the conversation scratch directory (`<appDataDir>/brain/<conversation-id>/scratch/`) or `/tmp/`.
- Clean up temporary scratch files immediately after task completion.
- Do NOT delete unrequested, unrelated, or system cache files.

### 15. CachyOS & Linux System Standards
- Mowftee is built specifically for CachyOS / Arch Linux.
- Do NOT silently assume generic Debian/Ubuntu/Fedora paths or package names.
- Evaluation order for system queries: Live Machine State -> CachyOS Package Manager (`pacman`) -> Repository Code -> Upstream Specs -> Inference.

### 16. Reporting Format
Reports to the user/HQ MUST be concise, structured, and evidence-based:
- Exact actions taken & test results.
- Empirical verification outputs.
- List of modified files or state changes.
- Active blockers (if any).
- Immediate STOP at the requested task boundary.

### 17. Protected Standard Mutation Policy
`/CLAUDE.md` is the governing standard of the repository and is IMMUTABLE during ordinary feature tasks. Modifying `/CLAUDE.md` REQUIRES:
1. Explicit user/HQ instruction.
2. A dedicated task scope.
3. Review and verification.

### 18. Cold-Start Completeness Criterion
Before completing a session handoff or milestone closure, verify:
*"If the current chat transcript disappeared and only the `dev` repository remained, could a new HQ/developer continue work correctly without asking operator questions for information answerable by the repository?"*
If NO, documentation state is incomplete and MUST be updated before handoff.
