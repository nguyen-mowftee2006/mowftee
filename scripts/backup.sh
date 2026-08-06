#!/usr/bin/env bash
set -euo pipefail

if (( EUID == 0 )); then
    echo "Mowftee backup tooling must not run as root." >&2
    exit 3
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "Mowftee backup: uv is required." >&2
    exit 3
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd -- "$script_dir/.." && pwd -P)"

if [[ ! -f "$repository_root/pyproject.toml" \
      || ! -f "$repository_root/uv.lock" \
      || ! -f "$repository_root/src/mowftee/backup.py" ]]; then
    echo "Mowftee backup: repository root could not be validated." >&2
    exit 3
fi

cd -- "$repository_root"
exec uv run --locked python -m mowftee.backup backup "$@"
