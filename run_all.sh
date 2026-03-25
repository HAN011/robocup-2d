#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEAM="${1:-}"
HOST="${2:-localhost}"
PORT="${3:-6000}"
OPPONENT_TEAM="${4:-${TEAM}_Opponent}"
OFFLINE_TRAINER_PORT="$((PORT + 1))"
ONLINE_COACH_PORT="$((PORT + 2))"
LOG_DIR="${PROJECT_ROOT}/logs"
RCSS_RECORD_DIR="${RCSS_RECORD_DIR:-${LOG_DIR}/server_records}"
RCSS_LD_LIBRARY_PATH="/usr/local/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
RCSSSERVER_BIN="${RCSSSERVER_BIN:-/usr/local/bin/rcssserver}"
RCSSMONITOR_BIN="${RCSSMONITOR_BIN:-/usr/local/bin/rcssmonitor}"
START_SCRIPT="${START_SCRIPT:-${PROJECT_ROOT}/start.sh}"
SERVER_DELAY="${SERVER_DELAY:-1}"
MONITOR_DELAY="${MONITOR_DELAY:-1}"
PYTHON_BIN="${PYTHON_BIN:-}"
RUN_OPPONENT="${RUN_OPPONENT:-1}"

if [[ -z "${TEAM}" ]]; then
  echo "Usage: $0 TEAM [HOST] [PORT] [OPPONENT_TEAM]" >&2
  exit 1
fi

if [[ ! -x "${START_SCRIPT}" ]]; then
  echo "start script not executable: ${START_SCRIPT}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"
mkdir -p "${RCSS_RECORD_DIR}"
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

launch_with_logs() {
  local log_file="$1"
  shift

  "$@" >"${log_file}" 2>&1 &
  pids+=("$!")
}

launch_with_logs_in_dir() {
  local log_file="$1"
  local workdir="$2"
  shift 2

  (
    cd "${workdir}"
    "$@"
  ) >"${log_file}" 2>&1 &
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

launch_with_logs_in_dir "${LOG_DIR}/rcssserver.log" "${RCSS_RECORD_DIR}" \
  env LD_LIBRARY_PATH="${RCSS_LD_LIBRARY_PATH}" \
  "${RCSSSERVER_BIN}" \
  "server::port=${PORT}" \
  "server::coach_port=${OFFLINE_TRAINER_PORT}" \
  "server::olcoach_port=${ONLINE_COACH_PORT}" \
  "server::game_log_dir=${RCSS_RECORD_DIR}" \
  "server::text_log_dir=${RCSS_RECORD_DIR}" \
  "server::keepaway_log_dir=${RCSS_RECORD_DIR}" \
  "server::coach_w_referee=true" \
  "server::auto_mode=true" \
  "server::connect_wait=5" \
  "server::kick_off_wait=5" \
  "server::game_over_wait=5"

sleep "${SERVER_DELAY}"

launch_with_logs "${LOG_DIR}/rcssmonitor.log" \
  env LD_LIBRARY_PATH="${RCSS_LD_LIBRARY_PATH}" \
  "${RCSSMONITOR_BIN}" \
  --connect \
  --server-host "${HOST}" \
  --server-port "${PORT}"

sleep "${MONITOR_DELAY}"

PYTHON_BIN="$(resolve_python_bin)"

launch_with_logs "${LOG_DIR}/team_launcher.log" \
  env PYTHON_BIN="${PYTHON_BIN}" \
  LOG_DIR="${LOG_DIR}/home" \
  "${START_SCRIPT}" \
  "${TEAM}" \
  "${HOST}" \
  "${PORT}"

if [[ "${RUN_OPPONENT}" != "0" ]]; then
  launch_with_logs "${LOG_DIR}/team_opponent_launcher.log" \
    env PYTHON_BIN="${PYTHON_BIN}" \
    LOG_DIR="${LOG_DIR}/away" \
    "${START_SCRIPT}" \
    "${OPPONENT_TEAM}" \
    "${HOST}" \
    "${PORT}"
fi

status=0
for pid in "${pids[@]}"; do
  wait "${pid}" || status=$?
done

exit "${status}"
