# Mowftee Development

This branch (`dev`) is the active development workspace for Mowftee.
Read [`CLAUDE.md`](CLAUDE.md) first before performing any work.

## Development Router

| Question / Need | Authoritative Source |
|---|---|
| What rules & protocols must I follow? | [`CLAUDE.md`](CLAUDE.md) |
| What is the active handoff state & next step? | [`docs/SESSION_PROMPT.md`](docs/SESSION_PROMPT.md) |
| What is the canonical roadmap, phase goals & DoD? | [`docs/PLAN.md`](docs/PLAN.md) |
| How is the system designed & structured? | [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) |
| Why was an architectural or technical decision made? | Decision Log in [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) |
| Where is test, benchmark & incident evidence? | [`docs/LOG.md`](docs/LOG.md) |
| What runtime/model metadata is defined? | [`config/model-manifest.yaml`](config/model-manifest.yaml) |
| Where is raw hardware baseline evidence? | [`config/hardware-baseline.txt`](config/hardware-baseline.txt) |
| What is the recovery & backup architecture? | Recovery Architecture in [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) |

## Cold Start

1. Read [`CLAUDE.md`](CLAUDE.md).
2. Read [`docs/SESSION_PROMPT.md`](docs/SESSION_PROMPT.md).
3. Follow this router to canonical docs as required by task scope.
4. Verify Git and runtime state as required by `CLAUDE.md`.
5. Continue the documented active objective unless the explicit current task overrides it.

## Git Branch Model

- **`main`:** Released, stable branch; public/release-facing surface.
- **`dev`:** Active integration and development branch; this `README.md` is the development documentation router.
- **`feat/*`, `fix/*`, `docs/*`, `experiment/*`:** Feature/fix branches created off `dev` when isolation is justified, and merged back into `dev`.

Refer to [`CLAUDE.md`](CLAUDE.md) for authoritative documentation ownership and update rules.
