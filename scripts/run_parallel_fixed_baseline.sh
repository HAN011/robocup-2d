#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
source "${SCRIPTS_DIR}/opponents_registry.sh"

MATCHES_PER_OPPONENT="${1:-1}"
BASE_PORT="${BASE_PORT:-6100}"
PORT_STEP="${PORT_STEP:-10}"
PARALLEL_JOBS="${PARALLEL_JOBS:-6}"
SAFE_PARALLEL_JOBS="${SAFE_PARALLEL_JOBS:-6}"
ALLOW_UNSAFE_PARALLEL="${ALLOW_UNSAFE_PARALLEL:-0}"
FAIL_ON_SUSPECT="${FAIL_ON_SUSPECT:-1}"
WORKER_LAUNCH_STAGGER_SECONDS="${WORKER_LAUNCH_STAGGER_SECONDS:-0.75}"
PARALLEL_SERVER_SYNCH_MODE="${PARALLEL_SERVER_SYNCH_MODE:-1}"
PARALLEL_SERVER_SYNCH_MICRO_SLEEP="${PARALLEL_SERVER_SYNCH_MICRO_SLEEP:-10000}"
PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS="${PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS:-1}"
PARALLEL_ASYNC_CONNECT_WAIT="${PARALLEL_ASYNC_CONNECT_WAIT:-120}"
PARALLEL_ASYNC_HOME_OPPONENT_LAUNCH_DELAY="${PARALLEL_ASYNC_HOME_OPPONENT_LAUNCH_DELAY:-0}"
PARALLEL_ASYNC_PLAYER_DELAY="${PARALLEL_ASYNC_PLAYER_DELAY:-0.03}"
RESULT_DIR="${PROJECT_ROOT}/results"
RUN_LABEL="${RUN_LABEL:-${ROBOCUP_EXPERIMENT_PROFILE:-}}"
RUN_ID="${RUN_ID:-}"
PARALLEL_LOG_ROOT="${PARALLEL_LOG_ROOT:-${PROJECT_ROOT}/log/parallel_baselines}"

sanitize_label() {
  local raw="$1"
  raw="${raw// /_}"
  raw="$(printf '%s' "${raw}" | tr -cs '[:alnum:]_-' '_')"
  raw="${raw##_}"
  raw="${raw%%_}"
  printf '%s\n' "${raw}"
}

if [[ ! "${MATCHES_PER_OPPONENT}" =~ ^[1-9][0-9]*$ ]]; then
  printf '[run_parallel_fixed_baseline] ERROR: matches per opponent must be a positive integer, got %s\n' "${MATCHES_PER_OPPONENT}" >&2
  exit 1
fi

if [[ ! "${PARALLEL_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
  printf '[run_parallel_fixed_baseline] ERROR: PARALLEL_JOBS must be a positive integer, got %s\n' "${PARALLEL_JOBS}" >&2
  exit 1
fi

if [[ ! "${SAFE_PARALLEL_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
  printf '[run_parallel_fixed_baseline] ERROR: SAFE_PARALLEL_JOBS must be a positive integer, got %s\n' "${SAFE_PARALLEL_JOBS}" >&2
  exit 1
fi

if [[ ! "${WORKER_LAUNCH_STAGGER_SECONDS}" =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]]; then
  printf '[run_parallel_fixed_baseline] ERROR: WORKER_LAUNCH_STAGGER_SECONDS must be a non-negative number, got %s\n' "${WORKER_LAUNCH_STAGGER_SECONDS}" >&2
  exit 1
fi

mkdir -p "${RESULT_DIR}" "${PARALLEL_LOG_ROOT}"
run_ts="$(date +%Y%m%d_%H%M%S)"
run_id="${RUN_ID:-${run_ts}_$$}"
parallel_log_dir="${PARALLEL_LOG_ROOT}/${run_id}"
mkdir -p "${parallel_log_dir}"

run_label_sanitized=""
if [[ -n "${RUN_LABEL}" ]]; then
  run_label_sanitized="$(sanitize_label "${RUN_LABEL}")"
fi

declare -a opponent_keys=()
declare -a opponent_ports=()
declare -a result_path_files=()
declare -a worker_logs=()
declare -a opponent_sync_modes=()
declare -a opponent_launch_first_modes=()

while IFS= read -r opponent_key; do
  [[ -n "${opponent_key}" ]] || continue
  opponent_keys+=("${opponent_key}")
done < <(selected_opponent_keys)

effective_parallel_jobs="${PARALLEL_JOBS}"
if (( effective_parallel_jobs > ${#opponent_keys[@]} )); then
  effective_parallel_jobs="${#opponent_keys[@]}"
fi

if [[ "${ALLOW_UNSAFE_PARALLEL}" != "1" ]] && (( effective_parallel_jobs > SAFE_PARALLEL_JOBS )); then
  effective_parallel_jobs="${SAFE_PARALLEL_JOBS}"
fi

if [[ -n "${run_label_sanitized}" ]]; then
  summary_file="${RESULT_DIR}/parallel_fixed_baseline_${run_label_sanitized}_${run_id}.txt"
else
  summary_file="${RESULT_DIR}/parallel_fixed_baseline_${run_id}.txt"
fi

cat >"${summary_file}" <<EOF
RoboCup 2D Parallel Fixed Baseline
timestamp: ${run_ts}
run_id: ${run_id}
run_label: ${run_label_sanitized:-none}
experiment_profile: ${ROBOCUP_EXPERIMENT_PROFILE:-baseline}
matches_per_opponent: ${MATCHES_PER_OPPONENT}
base_port: ${BASE_PORT}
port_step: ${PORT_STEP}
parallel_jobs: ${PARALLEL_JOBS}
effective_parallel_jobs: ${effective_parallel_jobs}
safe_parallel_jobs: ${SAFE_PARALLEL_JOBS}
allow_unsafe_parallel: ${ALLOW_UNSAFE_PARALLEL}
fail_on_suspect: ${FAIL_ON_SUSPECT}
worker_launch_stagger_seconds: ${WORKER_LAUNCH_STAGGER_SECONDS}
parallel_server_synch_mode: ${PARALLEL_SERVER_SYNCH_MODE}
parallel_server_synch_micro_sleep: ${PARALLEL_SERVER_SYNCH_MICRO_SLEEP}
parallel_match_disable_internal_file_logs: ${PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS}
parallel_async_connect_wait: ${PARALLEL_ASYNC_CONNECT_WAIT}
parallel_async_home_opponent_launch_delay: ${PARALLEL_ASYNC_HOME_OPPONENT_LAUNCH_DELAY}
parallel_async_player_delay: ${PARALLEL_ASYNC_PLAYER_DELAY}
parallel_log_dir: ${parallel_log_dir}
---
EOF

if (( PARALLEL_JOBS > ${#opponent_keys[@]} )); then
  printf '[run_parallel_fixed_baseline] note: PARALLEL_JOBS=%s but only %s opponents are registered; effective parallelism=%s\n' \
    "${PARALLEL_JOBS}" "${#opponent_keys[@]}" "${effective_parallel_jobs}"
fi

if [[ "${ALLOW_UNSAFE_PARALLEL}" != "1" ]] && (( PARALLEL_JOBS > SAFE_PARALLEL_JOBS )); then
  printf '[run_parallel_fixed_baseline] note: requested PARALLEL_JOBS=%s, capped to safe full-match parallelism=%s. Set ALLOW_UNSAFE_PARALLEL=1 to override.\n' \
    "${PARALLEL_JOBS}" "${effective_parallel_jobs}"
fi

cleanup_children() {
  trap - EXIT INT TERM
  local pid
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    kill "${pid}" 2>/dev/null || true
  done < <(jobs -pr)
  wait 2>/dev/null || true
}

trap cleanup_children EXIT INT TERM

status=0
suspect_total=0
for index in "${!opponent_keys[@]}"; do
  while (( $(jobs -pr | wc -l) >= effective_parallel_jobs )); do
    if ! wait -n; then
      status=1
    fi
  done

  opponent_key="${opponent_keys[$index]}"
  if ! resolve_opponent "${opponent_key}"; then
    printf '[run_parallel_fixed_baseline] ERROR: failed to resolve opponent %s\n' "${opponent_key}" >&2
    exit 1
  fi
  port=$(( BASE_PORT + index * PORT_STEP ))
  result_path_file="$(mktemp "${TMPDIR:-/tmp}/parallel_run_match_${opponent_key}.XXXXXX")"
  worker_log="${parallel_log_dir}/$(printf '%02d' "$((index + 1))")_${opponent_key}.log"
  opponent_sync_mode="${OPP_PARALLEL_SERVER_SYNCH_MODE:-${PARALLEL_SERVER_SYNCH_MODE}}"
  opponent_launch_first="${OPP_LAUNCH_OPPONENT_FIRST:-0}"
  opponent_connect_wait="${CONNECT_WAIT:-}"
  opponent_home_launch_delay="${HOME_OPPONENT_LAUNCH_DELAY:-}"
  opponent_player_delay="${PLAYER_DELAY:-}"
  if [[ "${opponent_sync_mode}" == "0" ]]; then
    opponent_connect_wait="${opponent_connect_wait:-${PARALLEL_ASYNC_CONNECT_WAIT}}"
    opponent_home_launch_delay="${opponent_home_launch_delay:-${PARALLEL_ASYNC_HOME_OPPONENT_LAUNCH_DELAY}}"
    opponent_player_delay="${opponent_player_delay:-${PARALLEL_ASYNC_PLAYER_DELAY}}"
  fi

  opponent_ports[$index]="${port}"
  result_path_files[$index]="${result_path_file}"
  worker_logs[$index]="${worker_log}"
  opponent_sync_modes[$index]="${opponent_sync_mode}"
  opponent_launch_first_modes[$index]="${opponent_launch_first}"

  printf '[run_parallel_fixed_baseline] running %s on port %s (sync=%s, log: %s)\n' "${opponent_key}" "${port}" "${opponent_sync_mode}" "${worker_log}"
  (
    PORT="${port}" \
      RUN_ID="${run_id}_${opponent_key}" \
    ROBOCUP_OPPONENT_KEY="${opponent_key}" \
      ROBOCUP_OPPONENT_KEY="${opponent_key}" \
      RUN_PARALLEL_MODE="1" \
      SERVER_SYNCH_MODE="${opponent_sync_mode}" \
      SERVER_SYNCH_MICRO_SLEEP="${PARALLEL_SERVER_SYNCH_MICRO_SLEEP}" \
      CONNECT_WAIT="${opponent_connect_wait}" \
      HOME_OPPONENT_LAUNCH_DELAY="${opponent_home_launch_delay}" \
      LAUNCH_OPPONENT_FIRST="${opponent_launch_first}" \
      PLAYER_DELAY="${opponent_player_delay}" \
      MATCH_DISABLE_INTERNAL_FILE_LOGS="${PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS}" \
      RUN_MATCH_RESULT_PATH_FILE="${result_path_file}" \
      "${SCRIPTS_DIR}/run_match.sh" "${opponent_key}" "${MATCHES_PER_OPPONENT}"
  ) >"${worker_log}" 2>&1 &

  if [[ "${WORKER_LAUNCH_STAGGER_SECONDS}" != "0" && "${WORKER_LAUNCH_STAGGER_SECONDS}" != "0.0" ]]; then
    sleep "${WORKER_LAUNCH_STAGGER_SECONDS}"
  fi
done

while (( $(jobs -pr | wc -l) > 0 )); do
  if ! wait -n; then
    status=1
  fi
done

trap - EXIT INT TERM

for index in "${!opponent_keys[@]}"; do
  opponent_key="${opponent_keys[$index]}"
  port="${opponent_ports[$index]}"
  result_path_file="${result_path_files[$index]}"
  worker_log="${worker_logs[$index]}"
  opponent_sync_mode="${opponent_sync_modes[$index]}"
  opponent_launch_first="${opponent_launch_first_modes[$index]}"
  latest_result="$(sed -n '1p' "${result_path_file}" 2>/dev/null || true)"
  rm -f "${result_path_file}"

  {
    printf '%s\n' "${opponent_key}"
    printf '  port: %s\n' "${port}"
    printf '  sync_mode: %s\n' "${opponent_sync_mode}"
    printf '  launch_opponent_first: %s\n' "${opponent_launch_first}"
    printf '  worker_log: %s\n' "${worker_log}"
    if [[ -n "${latest_result}" && -f "${latest_result}" ]]; then
      suspicious_matches="$(grep -E -c '^  health: suspect$' "${latest_result}" 2>/dev/null || true)"
      total_disconnects="$(sed -n 's/^  disconnects: //p' "${latest_result}" | awk '{ total += $1 } END { print total + 0 }')"
      total_timing_warnings="$(sed -n 's/^  timing_warnings: //p' "${latest_result}" | awk '{ total += $1 } END { print total + 0 }')"
      total_opponent_actions="$(sed -n 's/^  opponent_actions: //p' "${latest_result}" | awk '{ total += $1 } END { print total + 0 }')"
      suspect_total=$((suspect_total + suspicious_matches))
      printf '  result: %s\n' "${latest_result}"
      printf '  suspicious_matches: %s\n' "${suspicious_matches}"
      printf '  total_disconnects: %s\n' "${total_disconnects}"
      printf '  total_timing_warnings: %s\n' "${total_timing_warnings}"
      printf '  total_opponent_actions: %s\n' "${total_opponent_actions}"
      sed -n '1,40p' "${latest_result}" | sed 's/^/    /'
    else
      printf '  result: ERROR missing result path\n'
      status=1
    fi
    printf -- '---\n'
  } >>"${summary_file}"
done

if [[ "${FAIL_ON_SUSPECT}" == "1" && "${suspect_total}" -gt 0 ]]; then
  printf 'gate_status: suspect_results_detected\n' >>"${summary_file}"
  status=1
else
  printf 'gate_status: clean\n' >>"${summary_file}"
fi

printf '[run_parallel_fixed_baseline] summary: %s\n' "${summary_file}"
exit "${status}"
