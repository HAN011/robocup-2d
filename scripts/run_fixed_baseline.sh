#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
source "${SCRIPTS_DIR}/opponents_registry.sh"

MATCHES_PER_OPPONENT="${1:-1}"
BASE_PORT="${BASE_PORT:-6100}"
PORT_STEP="${PORT_STEP:-10}"
RESULT_DIR="${PROJECT_ROOT}/results"
RUN_LABEL="${RUN_LABEL:-${ROBOCUP_EXPERIMENT_PROFILE:-}}"

sanitize_label() {
  local raw="$1"
  raw="${raw// /_}"
  raw="$(printf '%s' "${raw}" | tr -cs '[:alnum:]_-' '_')"
  raw="${raw##_}"
  raw="${raw%%_}"
  printf '%s\n' "${raw}"
}

if [[ ! "${MATCHES_PER_OPPONENT}" =~ ^[1-9][0-9]*$ ]]; then
  printf '[run_fixed_baseline] ERROR: matches per opponent must be a positive integer, got %s\n' "${MATCHES_PER_OPPONENT}" >&2
  exit 1
fi

mkdir -p "${RESULT_DIR}"
run_ts="$(date +%Y%m%d_%H%M%S)"
run_label_sanitized=""
if [[ -n "${RUN_LABEL}" ]]; then
  run_label_sanitized="$(sanitize_label "${RUN_LABEL}")"
fi

if [[ -n "${run_label_sanitized}" ]]; then
  summary_file="${RESULT_DIR}/fixed_baseline_${run_label_sanitized}_${run_ts}.txt"
else
  summary_file="${RESULT_DIR}/fixed_baseline_${run_ts}.txt"
fi

cat >"${summary_file}" <<EOF
RoboCup 2D Fixed Baseline
timestamp: ${run_ts}
run_label: ${run_label_sanitized:-none}
experiment_profile: ${ROBOCUP_EXPERIMENT_PROFILE:-baseline}
matches_per_opponent: ${MATCHES_PER_OPPONENT}
base_port: ${BASE_PORT}
port_step: ${PORT_STEP}
---
EOF

index=0
while IFS= read -r opponent_key; do
  [[ -n "${opponent_key}" ]] || continue
  port=$(( BASE_PORT + index * PORT_STEP ))
  printf '[run_fixed_baseline] running %s on port %s\n' "${opponent_key}" "${port}"
  PORT="${port}" "${SCRIPTS_DIR}/run_match.sh" "${opponent_key}" "${MATCHES_PER_OPPONENT}"

  latest_result="$(ls -td "${RESULT_DIR}/${opponent_key}"_*.txt | head -n 1)"
  {
    printf '%s\n' "${opponent_key}"
    printf '  port: %s\n' "${port}"
    printf '  result: %s\n' "${latest_result}"
    sed -n '1,40p' "${latest_result}" | sed 's/^/    /'
    printf -- '---\n'
  } >>"${summary_file}"

  index=$((index + 1))
done < <(stable_opponent_keys)

printf '[run_fixed_baseline] summary: %s\n' "${summary_file}"
