#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PORT="${1:-6000}"
HALF_TIME_SECONDS="${HALF_TIME_SECONDS:-300}"
NR_NORMAL_HALFS="${NR_NORMAL_HALFS:-2}"
DEFAULT_LOG_ROOT="${ROBOCUP_LOG_ROOT:-log}"
if [[ "${DEFAULT_LOG_ROOT}" != /* ]]; then
  DEFAULT_LOG_ROOT="${PROJECT_ROOT}/${DEFAULT_LOG_ROOT}"
fi
LOG_ROOT="${LOG_ROOT:-${DEFAULT_LOG_ROOT}/local_server}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
SERVER_LOG_DIR="${LOG_ROOT}/${RUN_ID}"

usage() {
  cat <<'EOF' >&2
Usage: ./scripts/start_local_server.sh [port]

Environment:
  HALF_TIME_SECONDS=300  half length in seconds
  NR_NORMAL_HALFS=2      number of normal halves
  LOG_ROOT=...           server log root directory
EOF
}

if [[ "${PORT}" == "-h" || "${PORT}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v rcssserver >/dev/null 2>&1; then
  echo "[start_local_server] ERROR: rcssserver not found in PATH" >&2
  exit 1
fi

mkdir -p "${SERVER_LOG_DIR}"

exec rcssserver \
  "server::port=${PORT}" \
  "server::coach_port=$((PORT + 1))" \
  "server::olcoach_port=$((PORT + 2))" \
  "server::coach=on" \
  "server::half_time=${HALF_TIME_SECONDS}" \
  "server::nr_normal_halfs=${NR_NORMAL_HALFS}" \
  "server::game_log_dir=${SERVER_LOG_DIR}" \
  "server::text_log_dir=${SERVER_LOG_DIR}" \
  "server::keepaway_log_dir=${SERVER_LOG_DIR}"
