#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEAM="${1:-}"
HOST="${2:-localhost}"
PORT="${3:-6000}"
LOG_DIR="${LOG_DIR:-${PROJECT_ROOT}/logs}"
PYTHON_BIN="${PYTHON_BIN:-}"
PLAYER_DELAY="${PLAYER_DELAY:-0.1}"
RUN_ID="$(date +%Y%m%d_%H%M%S_%N)"
INTERNAL_LOG_ROOT="${LOG_DIR}/runtime/${RUN_ID}"

if [[ -z "${TEAM}" ]]; then
  echo "Usage: $0 TEAM [HOST] [PORT]" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"
mkdir -p "${INTERNAL_LOG_ROOT}"
cd "${PROJECT_ROOT}"

declare -a pids=()

python_supports_pyrus2d() {
  local candidate="$1"
  "${candidate}" -c 'import pyrusgeom' >/dev/null 2>&1
}

resolve_python_bin() {
  local candidate
  local candidates=(
    "${PYTHON_BIN:-}"
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
    "${CONDA_PREFIX:-}/bin/python"
    "$(command -v python3 2>/dev/null || true)"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]] && python_supports_pyrus2d "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  printf '%s\n' "python3"
}

PYTHON_BIN="$(resolve_python_bin)"
exec 3>&1

launch() {
  local log_file="$1"
  shift

  "${PYTHON_BIN}" "$@" 3>&3 >"${log_file}" 2>&1 &
  pids+=("$!")
}

cleanup() {
  trap - EXIT INT TERM

  if [[ "${#pids[@]}" -eq 0 ]]; then
    return
  fi

  kill "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

for i in $(seq 1 11); do
  launch "${LOG_DIR}/player_${i}.log" \
    player/main.py \
    --host "${HOST}" \
    --port "${PORT}" \
    --team "${TEAM}" \
    --unum "${i}" \
    --log-path "${INTERNAL_LOG_ROOT}/player_${i}"
  sleep "${PLAYER_DELAY}"
done

launch "${LOG_DIR}/coach.log" \
  coach/main.py \
  --host "${HOST}" \
  --port "${PORT}" \
  --team "${TEAM}" \
  --log-path "${INTERNAL_LOG_ROOT}/coach"

status=0
for pid in "${pids[@]}"; do
  wait "${pid}" || status=$?
done

exit "${status}"
