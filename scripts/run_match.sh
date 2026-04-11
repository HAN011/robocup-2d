#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"

START_SCRIPT="${PROJECT_ROOT}/start.sh"
PARSE_RESULT_SCRIPT="${SCRIPTS_DIR}/parse_result.py"

HOST="${HOST:-localhost}"
PORT="${PORT:-6000}"
PYTHON_BIN="${PYTHON_BIN:-}"
SERVER_DELAY="${SERVER_DELAY:-1}"
VISUAL="${VISUAL:-0}"
MONITOR_DELAY="${MONITOR_DELAY:-1}"
HALF_TIME_CYCLES="${HALF_TIME_CYCLES:-}"
HALF_TIME_SECONDS="${HALF_TIME_SECONDS:-${HALF_TIME_CYCLES:-300}}"
NR_NORMAL_HALFS="${NR_NORMAL_HALFS:-2}"
SIM_STEP_MS="${SIM_STEP_MS:-100}"
MATCH_TIMEOUT="${MATCH_TIMEOUT:-}"
CONNECT_WAIT="${CONNECT_WAIT:-20}"
KICK_OFF_WAIT="${KICK_OFF_WAIT:-20}"
GAME_OVER_WAIT="${GAME_OVER_WAIT:-20}"

if [[ -z "${MATCH_TIMEOUT}" ]]; then
  expected_match_sec=$(( HALF_TIME_SECONDS * NR_NORMAL_HALFS ))
  timeout_buffer=300
  if [[ "${VISUAL}" == "1" ]]; then
    timeout_buffer=480
  fi
  MATCH_TIMEOUT=$(( expected_match_sec + timeout_buffer ))
fi

DEFAULT_LOG_ROOT="${ROBOCUP_LOG_ROOT:-log}"
if [[ "${DEFAULT_LOG_ROOT}" != /* ]]; then
  DEFAULT_LOG_ROOT="${PROJECT_ROOT}/${DEFAULT_LOG_ROOT}"
fi

RESULT_DIR="${PROJECT_ROOT}/results"
MATCH_LOG_ROOT="${MATCH_LOG_ROOT:-${DEFAULT_LOG_ROOT}/matches}"

MY_TEAM_NAME=""
CURRENT_SERVER_PID=""
CURRENT_HOME_LAUNCHER_PID=""
CURRENT_OPPONENT_LAUNCHER_PID=""
CURRENT_MONITOR_PID=""
CURRENT_OPPONENT_DIR=""

python_supports_submission_runtime() {
  local candidate="$1"
  [[ -x "${candidate}" ]] || return 1
  "${candidate}" -c 'import sys; print(sys.version_info[0])' >/dev/null 2>&1
}

resolve_python_bin() {
  local candidate
  local candidates=(
    "${PYTHON_BIN:-}"
    "${PROJECT_ROOT}/python/bin/python"
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
    "${CONDA_PREFIX:-}/bin/python"
    "$(command -v python3 2>/dev/null || true)"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" ]] && python_supports_submission_runtime "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  printf '%s\n' "python3"
}

RUN_PYTHON_BIN="$(resolve_python_bin)"

usage() {
  cat <<'EOF' >&2
Usage: ./scripts/run_match.sh <opponent_name> [num_matches]

opponent_name:
  cyrus2d
  helios

Environment:
  VISUAL=1          enable live monitor (rcssmonitor)
  HALF_TIME_SECONDS set match half duration in seconds (preferred)
  MATCH_TIMEOUT=NNN override match timeout in seconds
  RCSSMONITOR_BIN   custom rcssmonitor path
EOF
}

log() {
  printf '[run_match] %s\n' "$*"
}

die() {
  printf '[run_match] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup_match_processes() {
  if [[ -n "${CURRENT_MONITOR_PID}" ]] && kill -0 "${CURRENT_MONITOR_PID}" 2>/dev/null; then
    kill "${CURRENT_MONITOR_PID}" 2>/dev/null || true
    wait "${CURRENT_MONITOR_PID}" 2>/dev/null || true
  fi

  if [[ -n "${CURRENT_HOME_LAUNCHER_PID}" ]] && kill -0 "${CURRENT_HOME_LAUNCHER_PID}" 2>/dev/null; then
    kill "${CURRENT_HOME_LAUNCHER_PID}" 2>/dev/null || true
    wait "${CURRENT_HOME_LAUNCHER_PID}" 2>/dev/null || true
  fi

  if [[ -n "${CURRENT_OPPONENT_LAUNCHER_PID}" ]] && kill -0 "${CURRENT_OPPONENT_LAUNCHER_PID}" 2>/dev/null; then
    kill "${CURRENT_OPPONENT_LAUNCHER_PID}" 2>/dev/null || true
    wait "${CURRENT_OPPONENT_LAUNCHER_PID}" 2>/dev/null || true
  fi

  if [[ -n "${CURRENT_SERVER_PID}" ]] && kill -0 "${CURRENT_SERVER_PID}" 2>/dev/null; then
    kill "${CURRENT_SERVER_PID}" 2>/dev/null || true
    wait "${CURRENT_SERVER_PID}" 2>/dev/null || true
  fi

  if [[ -n "${CURRENT_OPPONENT_DIR}" ]]; then
    pkill -f "${CURRENT_OPPONENT_DIR}/src/sample_player" 2>/dev/null || true
    pkill -f "${CURRENT_OPPONENT_DIR}/src/sample_coach" 2>/dev/null || true
  fi

  if [[ -n "${MY_TEAM_NAME}" ]]; then
    pkill -f "${PROJECT_ROOT}/player/main.py.*--host ${HOST}.*--port ${PORT}" 2>/dev/null || true
    pkill -f "${PROJECT_ROOT}/coach/main.py.*--host ${HOST}.*--port ${PORT}" 2>/dev/null || true
  fi

  CURRENT_HOME_LAUNCHER_PID=""
  CURRENT_OPPONENT_LAUNCHER_PID=""
  CURRENT_SERVER_PID=""
  CURRENT_MONITOR_PID=""
}

resolve_my_team_name() {
  if [[ -n "${MY_TEAM:-}" ]]; then
    printf '%s\n' "${MY_TEAM}"
    return 0
  fi

  local team_name
  team_name="$(PYTHONPATH="${PROJECT_ROOT}" "${RUN_PYTHON_BIN}" - <<'PY'
try:
    import team_config
    print(getattr(team_config, "TEAM_NAME", "MyTeam"))
except Exception:
    print("MyTeam")
PY
)"

  printf '%s\n' "${team_name}"
}

wait_for_match_result() {
  local pid="$1"
  local timeout_sec="$2"
  local server_log="$3"
  local elapsed=0

  while true; do
    if parse_server_score "${server_log}" >/dev/null 2>&1; then
      return 0
    fi

    if ! kill -0 "${pid}" 2>/dev/null; then
      break
    fi

    if (( elapsed >= timeout_sec )); then
      return 124
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  if parse_server_score "${server_log}" >/dev/null 2>&1; then
    return 0
  fi

  wait "${pid}" >/dev/null 2>&1 || true
  return 1
}

parse_server_score() {
  local server_log="$1"
  local teams_line
  local score_line

  teams_line="$(grep -E "^[[:space:]]*'[^']+'[[:space:]]+vs[[:space:]]+'[^']+'" "${server_log}" | tail -n1 || true)"
  score_line="$(grep -E "^[[:space:]]*Score:[[:space:]]*[0-9]+[[:space:]]*-[[:space:]]*[0-9]+" "${server_log}" | tail -n1 || true)"

  if [[ -z "${teams_line}" || -z "${score_line}" ]]; then
    return 1
  fi

  if [[ ! "${teams_line}" =~ \'([^\']+)\'[[:space:]]+vs[[:space:]]+\'([^\']+)\' ]]; then
    return 1
  fi
  local left_team="${BASH_REMATCH[1]}"
  local right_team="${BASH_REMATCH[2]}"

  if [[ ! "${score_line}" =~ Score:[[:space:]]*([0-9]+)[[:space:]]*-[[:space:]]*([0-9]+) ]]; then
    return 1
  fi
  local left_score="${BASH_REMATCH[1]}"
  local right_score="${BASH_REMATCH[2]}"

  printf '%s\t%s\t%s\t%s\n' "${left_team}" "${right_team}" "${left_score}" "${right_score}"
}

parse_rcg_score() {
  local record_dir="$1"
  local rcg_file

  rcg_file="$(find "${record_dir}" -maxdepth 1 -type f -name '*.rcg' | sort | tail -n1 || true)"
  if [[ -z "${rcg_file}" || ! -f "${rcg_file}" || ! -f "${PARSE_RESULT_SCRIPT}" ]]; then
    return 1
  fi

  "${RUN_PYTHON_BIN}" "${PARSE_RESULT_SCRIPT}" --format tsv "${rcg_file}" 2>/dev/null
}

parse_match_score() {
  local server_log="$1"
  local record_dir="$2"
  local parsed_score

  parsed_score="$(parse_server_score "${server_log}" || true)"
  if [[ -n "${parsed_score}" ]]; then
    printf '%s\n' "${parsed_score}"
    return 0
  fi

  parsed_score="$(parse_rcg_score "${record_dir}" || true)"
  if [[ -n "${parsed_score}" ]]; then
    printf '%s\n' "${parsed_score}"
    return 0
  fi

  return 1
}

finalize_match_result() {
  local pid="$1"
  local server_log="$2"
  local record_dir="$3"
  local timeout_reason="${4:-0}"
  local parsed_score=""
  local wait_sec

  parsed_score="$(parse_match_score "${server_log}" "${record_dir}" || true)"
  if [[ -n "${parsed_score}" ]]; then
    printf '%s\n' "${parsed_score}"
    return 0
  fi

  if kill -0 "${pid}" 2>/dev/null; then
    if [[ "${timeout_reason}" == "1" ]]; then
      log "match timeout reached; terminating rcssserver to flush final result"
    fi
    kill "${pid}" 2>/dev/null || true
  fi

  for wait_sec in 1 2 3 4 5; do
    parsed_score="$(parse_match_score "${server_log}" "${record_dir}" || true)"
    if [[ -n "${parsed_score}" ]]; then
      printf '%s\n' "${parsed_score}"
      return 0
    fi

    if ! kill -0 "${pid}" 2>/dev/null; then
      wait "${pid}" >/dev/null 2>&1 || true
    fi
    sleep 1
  done

  if kill -0 "${pid}" 2>/dev/null; then
    kill -9 "${pid}" 2>/dev/null || true
    wait "${pid}" >/dev/null 2>&1 || true
  fi

  parsed_score="$(parse_match_score "${server_log}" "${record_dir}" || true)"
  if [[ -n "${parsed_score}" ]]; then
    printf '%s\n' "${parsed_score}"
    return 0
  fi

  return 1
}

resolve_rcssserver_bin() {
  if [[ -n "${RCSSSERVER_BIN:-}" ]]; then
    printf '%s\n' "${RCSSSERVER_BIN}"
    return 0
  fi

  if command -v rcssserver >/dev/null 2>&1; then
    command -v rcssserver
    return 0
  fi

  if [[ -x "/usr/local/bin/rcssserver" ]]; then
    printf '%s\n' "/usr/local/bin/rcssserver"
    return 0
  fi

  return 1
}

resolve_rcssmonitor_bin() {
  if [[ -n "${RCSSMONITOR_BIN:-}" ]]; then
    printf '%s\n' "${RCSSMONITOR_BIN}"
    return 0
  fi

  if command -v rcssmonitor >/dev/null 2>&1; then
    command -v rcssmonitor
    return 0
  fi

  if [[ -x "/usr/local/bin/rcssmonitor" ]]; then
    printf '%s\n' "/usr/local/bin/rcssmonitor"
    return 0
  fi

  return 1
}

main() {
  local opponent_name="${1:-}"
  local num_matches="${2:-1}"

  if [[ -z "${opponent_name}" ]]; then
    usage
    exit 1
  fi

  if [[ ! "${num_matches}" =~ ^[1-9][0-9]*$ ]]; then
    die "num_matches must be a positive integer"
  fi

  if [[ ! "${PORT}" =~ ^[0-9]+$ ]]; then
    die "PORT must be numeric, got: ${PORT}"
  fi

  if [[ ! "${MATCH_TIMEOUT}" =~ ^[1-9][0-9]*$ ]]; then
    die "MATCH_TIMEOUT must be a positive integer, got: ${MATCH_TIMEOUT}"
  fi

  if [[ ! "${VISUAL}" =~ ^[01]$ ]]; then
    die "VISUAL must be 0 or 1, got: ${VISUAL}"
  fi

  MY_TEAM_NAME="$(resolve_my_team_name)"

  local opponent_dir
  local opponent_start
  local opponent_team_name

  case "${opponent_name}" in
    cyrus2d)
      opponent_dir="${PROJECT_ROOT}/opponents/cyrus2d"
      opponent_start="${opponent_dir}/src/start.sh"
      opponent_team_name="${OPPONENT_TEAM_NAME:-Cyrus2D_base}"
      ;;
    helios)
      opponent_dir="${PROJECT_ROOT}/opponents/helios"
      opponent_start="${opponent_dir}/src/start.sh"
      opponent_team_name="${OPPONENT_TEAM_NAME:-HELIOS_base}"
      ;;
    *)
      usage
      die "unsupported opponent_name: ${opponent_name}"
      ;;
  esac

  if [[ ! -x "${START_SCRIPT}" ]]; then
    die "our start script is not executable: ${START_SCRIPT}"
  fi

  if [[ ! -x "${opponent_start}" ]]; then
    die "opponent start script not found: ${opponent_start}. Run ./scripts/setup_opponents.sh first."
  fi

  local rcssserver_bin
  rcssserver_bin="$(resolve_rcssserver_bin || true)"
  if [[ -z "${rcssserver_bin}" || ! -x "${rcssserver_bin}" ]]; then
    die "rcssserver not found. Set RCSSSERVER_BIN or install rcssserver-19.0.x."
  fi

  local rcssmonitor_bin=""
  if [[ "${VISUAL}" == "1" ]]; then
    rcssmonitor_bin="$(resolve_rcssmonitor_bin || true)"
    if [[ -z "${rcssmonitor_bin}" || ! -x "${rcssmonitor_bin}" ]]; then
      die "VISUAL=1 but rcssmonitor not found. Set RCSSMONITOR_BIN or install rcssmonitor."
    fi
  fi

  mkdir -p "${RESULT_DIR}" "${MATCH_LOG_ROOT}"

  local run_ts
  run_ts="$(date +%Y%m%d_%H%M%S)"
  local result_file="${RESULT_DIR}/${opponent_name}_${run_ts}.txt"
  local run_log_dir="${MATCH_LOG_ROOT}/${opponent_name}_${run_ts}"
  mkdir -p "${run_log_dir}"

  local wins=0
  local draws=0
  local losses=0

  cat >"${result_file}" <<EOF
RoboCup 2D Match Report
timestamp: ${run_ts}
my_team: ${MY_TEAM_NAME}
opponent_key: ${opponent_name}
opponent_team: ${opponent_team_name}
matches: ${num_matches}
host: ${HOST}
port: ${PORT}
visual: ${VISUAL}
---
EOF

  log "my team: ${MY_TEAM_NAME}"
  log "opponent: ${opponent_team_name} (${opponent_name})"
  log "match timeout: ${MATCH_TIMEOUT}s"
  log "match logs: ${run_log_dir}"

  CURRENT_OPPONENT_DIR="${opponent_dir}"
  trap cleanup_match_processes EXIT INT TERM

  local i
  for (( i = 1; i <= num_matches; i++ )); do
    cleanup_match_processes

    local match_dir="${run_log_dir}/match_$(printf '%03d' "${i}")"
    local record_dir="${match_dir}/server_records"
    mkdir -p "${match_dir}" "${record_dir}" "${match_dir}/home"

    local server_log="${match_dir}/rcssserver.log"
    local home_log="${match_dir}/home_launcher.log"
    local opponent_log="${match_dir}/opponent_launcher.log"
    local monitor_log="${match_dir}/rcssmonitor.log"

    log "starting match ${i}/${num_matches}"

    "${rcssserver_bin}" \
      "server::port=${PORT}" \
      "server::coach_port=$((PORT + 1))" \
      "server::olcoach_port=$((PORT + 2))" \
      "server::auto_mode=true" \
      "server::synch_mode=0" \
      "server::half_time=${HALF_TIME_SECONDS}" \
      "server::nr_normal_halfs=${NR_NORMAL_HALFS}" \
      "server::connect_wait=${CONNECT_WAIT}" \
      "server::kick_off_wait=${KICK_OFF_WAIT}" \
      "server::game_over_wait=${GAME_OVER_WAIT}" \
      "server::game_log_dir=${record_dir}" \
      "server::text_log_dir=${record_dir}" \
      "server::keepaway_log_dir=${record_dir}" \
      >"${server_log}" 2>&1 &
    CURRENT_SERVER_PID="$!"

    sleep "${SERVER_DELAY}"

    if [[ "${VISUAL}" == "1" ]]; then
      "${rcssmonitor_bin}" \
        --connect \
        --server-host "${HOST}" \
        --server-port "${PORT}" \
        >"${monitor_log}" 2>&1 &
      CURRENT_MONITOR_PID="$!"
      sleep "${MONITOR_DELAY}"
    fi

    LOG_DIR="${match_dir}/home" "${START_SCRIPT}" "${MY_TEAM_NAME}" "${HOST}" "${PORT}" >"${home_log}" 2>&1 &
    CURRENT_HOME_LAUNCHER_PID="$!"

    sleep 1
    (
      cd "$(dirname "${opponent_start}")"
      ./start.sh -h "${HOST}" -p "${PORT}" -t "${opponent_team_name}"
    ) >"${opponent_log}" 2>&1 &
    CURRENT_OPPONENT_LAUNCHER_PID="$!"

    local wait_status=0
    local score_fields
    if wait_for_match_result "${CURRENT_SERVER_PID}" "${MATCH_TIMEOUT}" "${server_log}"; then
      score_fields="$(parse_match_score "${server_log}" "${record_dir}" || true)"
    else
      wait_status=$?
      score_fields="$(finalize_match_result "${CURRENT_SERVER_PID}" "${server_log}" "${record_dir}" "$(( wait_status == 124 ? 1 : 0 ))" || true)"
      if [[ -z "${score_fields}" ]]; then
        echo "Match ${i}: ERROR timeout or server crash" | tee -a "${result_file}" >&2
        exit 1
      fi
    fi

    cleanup_match_processes
    CURRENT_SERVER_PID=""

    if [[ -z "${score_fields}" ]]; then
      echo "Match ${i}: ERROR failed to parse score from ${server_log}" | tee -a "${result_file}" >&2
      exit 1
    fi

    local left_team right_team left_score right_score
    IFS=$'\t' read -r left_team right_team left_score right_score <<< "${score_fields}"

    local my_score opp_score displayed_opp_team
    if [[ "${left_team}" == "${MY_TEAM_NAME}" ]]; then
      my_score="${left_score}"
      opp_score="${right_score}"
      displayed_opp_team="${right_team}"
    elif [[ "${right_team}" == "${MY_TEAM_NAME}" ]]; then
      my_score="${right_score}"
      opp_score="${left_score}"
      displayed_opp_team="${left_team}"
    else
      my_score="${left_score}"
      opp_score="${right_score}"
      displayed_opp_team="${right_team}"
    fi

    if (( my_score > opp_score )); then
      wins=$((wins + 1))
    elif (( my_score < opp_score )); then
      losses=$((losses + 1))
    else
      draws=$((draws + 1))
    fi

    local rcg_file rcg_result
    rcg_file="$(find "${record_dir}" -maxdepth 1 -type f -name '*.rcg' | sort | tail -n1 || true)"
    rcg_result=""
    if [[ -n "${rcg_file}" && -f "${PARSE_RESULT_SCRIPT}" ]]; then
      rcg_result="$("${RUN_PYTHON_BIN}" "${PARSE_RESULT_SCRIPT}" "${rcg_file}" 2>/dev/null || true)"
    fi

    local match_line="Match ${i}: ${MY_TEAM_NAME} ${my_score} - ${opp_score} ${displayed_opp_team}"
    log "${match_line}"
    echo "${match_line}" >>"${result_file}"
    if [[ -n "${rcg_result}" ]]; then
      echo "  rcg: ${rcg_result}" >>"${result_file}"
    fi
    echo "  logs: ${match_dir}" >>"${result_file}"
  done

  cat >>"${result_file}" <<EOF
---
Summary:
W-D-L = ${wins}-${draws}-${losses}
EOF

  log "summary W-D-L: ${wins}-${draws}-${losses}"
  log "result file: ${result_file}"
}

main "$@"
