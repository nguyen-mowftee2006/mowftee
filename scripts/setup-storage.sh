#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
    echo "Error: do not run this script as root." >&2
    exit 1
fi

if [[ -z "${HOME:-}" ]]; then
    echo "Error: HOME is not set." >&2
    exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"

if [[ ! -f "${repo_root}/pyproject.toml" || ! -f "${repo_root}/scripts/setup-storage.sh" ]]; then
    echo "Error: could not identify the Mowftee repository root." >&2
    exit 1
fi

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

xdg_parents=(
    "${XDG_CONFIG_HOME}"
    "${XDG_DATA_HOME}"
    "${XDG_STATE_HOME}"
    "${XDG_CACHE_HOME}"
)

for parent in "${xdg_parents[@]}"; do
    mkdir -p -- "${parent}"
done

mowftee_dirs=(
    "${XDG_CONFIG_HOME}/mowftee"
    "${XDG_DATA_HOME}/mowftee"
    "${XDG_DATA_HOME}/mowftee/memory"
    "${XDG_DATA_HOME}/mowftee/conversations"
    "${XDG_DATA_HOME}/mowftee/artifacts"
    "${XDG_DATA_HOME}/mowftee/artifacts/voices"
    "${XDG_DATA_HOME}/mowftee/artifacts/lora"
    "${XDG_STATE_HOME}/mowftee"
    "${XDG_STATE_HOME}/mowftee/logs"
    "${XDG_STATE_HOME}/mowftee/audit"
    "${XDG_STATE_HOME}/mowftee/benchmarks"
    "${XDG_CACHE_HOME}/mowftee"
)

for directory in "${mowftee_dirs[@]}"; do
    install -d -m 0700 -- "${directory}"
done

expected_uid="$(id -u)"

for directory in "${mowftee_dirs[@]}"; do
    actual_uid="$(stat -c '%u' -- "${directory}")"
    actual_mode="$(stat -c '%a' -- "${directory}")"

    if [[ "${actual_uid}" != "${expected_uid}" || "${actual_mode}" != "700" ]]; then
        echo "Error: unexpected owner or mode for ${directory}." >&2
        exit 1
    fi
done

printf 'Repository root: %s\n' "${repo_root}"
printf 'Config path: %s\n' "${XDG_CONFIG_HOME}/mowftee"
printf 'Data path: %s\n' "${XDG_DATA_HOME}/mowftee"
printf 'State path: %s\n' "${XDG_STATE_HOME}/mowftee"
printf 'Cache path: %s\n' "${XDG_CACHE_HOME}/mowftee"
