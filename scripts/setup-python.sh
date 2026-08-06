#!/usr/bin/env bash

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is required but was not found in PATH." >&2
    exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"

if [[ "$(pwd -P)" != "${repo_root}" ]]; then
    echo "Error: run scripts/setup-python.sh from the repository root: ${repo_root}" >&2
    exit 1
fi

if [[ ! -f pyproject.toml || ! -f .python-version || ! -f uv.lock ]]; then
    echo "Error: repository root is missing pyproject.toml, .python-version, or uv.lock." >&2
    exit 1
fi

uv sync --locked

if [[ ! -x .venv/bin/python ]]; then
    echo "Error: uv did not create .venv/bin/python." >&2
    exit 1
fi

printf 'Project interpreter: %s\n' "$(realpath .venv/bin/python)"
printf 'Project Python: '
.venv/bin/python --version
