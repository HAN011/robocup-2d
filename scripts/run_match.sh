#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
source "${SCRIPTS_DIR}/opponents_registry.sh"

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
SERVER_SYNCH_MODE="${SERVER_SYNCH_MODE:-0}"
SERVER_SYNCH_MICRO_SLEEP="${SERVER_SYNCH_MICRO_SLEEP:-0}"
MATCH_TIMEOUT="${MATCH_TIMEOUT:-}"
CONNECT_WAIT="${CONNECT_WAIT:-20}"
KICK_OFF_WAIT="${KICK_OFF_WAIT:-20}"
GAME_OVER_WAIT="${GAME_OVER_WAIT:-20}"
RUN_LABEL="${RUN_LABEL:-${ROBOCUP_EXPERIMENT_PROFILE:-}}"
RUN_MATCH_RESULT_PATH_FILE="${RUN_MATCH_RESULT_PATH_FILE:-}"
MATCH_DISABLE_INTERNAL_FILE_LOGS="${MATCH_DISABLE_INTERNAL_FILE_LOGS:-0}"
HOME_OPPONENT_LAUNCH_DELAY="${HOME_OPPONENT_LAUNCH_DELAY:-1}"
LAUNCH_OPPONENT_FIRST="${LAUNCH_OPPONENT_FIRST:-0}"

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
CURRENT_OPPONENT_KILL_PATTERNS=""

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
  cat <<EOF >&2
Usage: ./scripts/run_match.sh <opponent_name> [num_matches]

opponent_name:
$(opponent_usage_lines | sed 's/^/  /')

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

sanitize_label() {
  local raw="$1"
  raw="${raw// /_}"
  raw="$(printf '%s' "${raw}" | tr -cs '[:alnum:]_-' '_')"
  raw="${raw##_}"
  raw="${raw%%_}"
  printf '%s\n' "${raw}"
}

die() {
  printf '[run_match] ERROR: %s\n' "$*" >&2
  exit 1
}

launch_in_session() {
  local __pid_var="$1"
  local output_log="$2"
  shift 2

  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >"${output_log}" 2>&1 &
  else
    "$@" >"${output_log}" 2>&1 &
  fi
  printf -v "${__pid_var}" '%s' "$!"
}

launch_in_dir_session() {
  local __pid_var="$1"
  local output_log="$2"
  local work_dir="$3"
  shift 3

  if command -v setsid >/dev/null 2>&1; then
    setsid bash -c 'cd "$1"; shift; exec "$@"' bash "${work_dir}" "$@" >"${output_log}" 2>&1 &
  else
    (
      cd "${work_dir}"
      "$@"
    ) >"${output_log}" 2>&1 &
  fi
  printf -v "${__pid_var}" '%s' "$!"
}

terminate_process_group() {
  local pid="$1"
  local wait_round
  local signal_target="-${pid}"

  [[ -n "${pid}" ]] || return 0

  if ! kill -0 "${pid}" 2>/dev/null; then
    if ! kill -TERM -- "${signal_target}" 2>/dev/null; then
      wait "${pid}" 2>/dev/null || true
      return 0
    fi
  else
    kill -TERM -- "${signal_target}" 2>/dev/null || kill "${pid}" 2>/dev/null || true
  fi

  for wait_round in 1 2 3 4 5; do
    if ! kill -0 "${pid}" 2>/dev/null && ! kill -0 -- "${signal_target}" 2>/dev/null; then
      wait "${pid}" 2>/dev/null || true
      return 0
    fi
    sleep 0.2
  done

  kill -9 -- "${signal_target}" 2>/dev/null || kill -9 "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true
}

cleanup_match_processes() {
  if [[ -n "${CURRENT_MONITOR_PID}" ]]; then
    terminate_process_group "${CURRENT_MONITOR_PID}"
  fi

  if [[ -n "${CURRENT_HOME_LAUNCHER_PID}" ]]; then
    terminate_process_group "${CURRENT_HOME_LAUNCHER_PID}"
  fi

  if [[ -n "${CURRENT_OPPONENT_LAUNCHER_PID}" ]]; then
    terminate_process_group "${CURRENT_OPPONENT_LAUNCHER_PID}"
  fi

  if [[ -n "${CURRENT_SERVER_PID}" ]]; then
    terminate_process_group "${CURRENT_SERVER_PID}"
  fi

  if [[ -n "${CURRENT_OPPONENT_KILL_PATTERNS}" ]]; then
    pkill -f "(${CURRENT_OPPONENT_KILL_PATTERNS}).*-h ${HOST}.*-p ${PORT}([[:space:]]|$)" 2>/dev/null || true
    pkill -f "(${CURRENT_OPPONENT_KILL_PATTERNS}).*-h ${HOST}.*-p $((PORT + 2))([[:space:]]|$)" 2>/dev/null || true
    pkill -f "(${CURRENT_OPPONENT_KILL_PATTERNS}).*--host ${HOST}.*--port ${PORT}([[:space:]]|$)" 2>/dev/null || true
    pkill -f "(${CURRENT_OPPONENT_KILL_PATTERNS}).*--host ${HOST}.*--port $((PORT + 2))([[:space:]]|$)" 2>/dev/null || true
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

ensure_opponent_ready() {
  local opponent_dir="$1"
  local opponent_target="${opponent_dir}/${OPP_START_REL}"

  case "${OPP_LAUNCH_MODE}" in
    start_script)
      if [[ ! -x "${opponent_target}" ]]; then
        die "opponent start script not found: ${opponent_target}. Run ./scripts/setup_opponents.sh ${OPP_KEY} first."
      fi
      ;;
    wrighteagle_release)
      if [[ ! -x "${SCRIPTS_DIR}/launch_wrighteagle.sh" ]]; then
        die "missing WrightEagle launcher: ${SCRIPTS_DIR}/launch_wrighteagle.sh"
      fi
      if [[ ! -x "${opponent_target}" ]]; then
        die "opponent binary not found: ${opponent_target}. Run ./scripts/setup_opponents.sh ${OPP_KEY} first."
      fi
      ;;
    *)
      die "unsupported launch mode: ${OPP_LAUNCH_MODE}"
      ;;
  esac
}

rewrite_config_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file

  tmp_file="${file}.tmp"
  if grep -qE "^[[:space:]]*${key}[[:space:]]*:" "${file}"; then
    awk -v key="${key}" -v value="${value}" '
      $0 ~ "^[[:space:]]*" key "[[:space:]]*:" { print key " : " value; next }
      { print }
    ' "${file}" >"${tmp_file}"
    mv "${tmp_file}" "${file}"
  else
    printf '%s : %s\n' "${key}" "${value}" >>"${file}"
  fi
}

rewrite_shell_assignment() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file

  tmp_file="${file}.tmp"
  if grep -qE "^[[:space:]]*${key}=" "${file}"; then
    awk -v key="${key}" -v value="${value}" '
      $0 ~ "^[[:space:]]*" key "=" { print key "=" value; next }
      { print }
    ' "${file}" >"${tmp_file}"
    chmod --reference="${file}" "${tmp_file}" 2>/dev/null || true
    mv "${tmp_file}" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${file}"
  fi
}

prepare_helios_async_runtime_dir() {
  local start_path="$1"
  local opponent_log="$2"
  local src_dir
  local runtime_dir

  src_dir="$(dirname "${start_path}")"
  runtime_dir="$(dirname "${opponent_log}")/opponent_runtime"
  mkdir -p "${runtime_dir}"

  cp "${src_dir}/start.sh" "${runtime_dir}/start.sh"
  chmod +x "${runtime_dir}/start.sh"
  cat >>"${runtime_dir}/start.sh" <<'EOF'

wait
EOF
  ln -sfn "${src_dir}/sample_player" "${runtime_dir}/sample_player"
  ln -sfn "${src_dir}/sample_coach" "${runtime_dir}/sample_coach"
  ln -sfn "${src_dir}/formations-dt" "${runtime_dir}/formations-dt"
  cp "${src_dir}/player.conf" "${runtime_dir}/player.conf"
  cp "${src_dir}/coach.conf" "${runtime_dir}/coach.conf"

  rewrite_config_key "${runtime_dir}/player.conf" "server_wait_seconds" "30"
  rewrite_config_key "${runtime_dir}/player.conf" "synch_see" "off"
  rewrite_config_key "${runtime_dir}/coach.conf" "server_wait_seconds" "30"

  printf '%s\n' "${runtime_dir}"
}

launch_opponent() {
  local opponent_dir="$1"
  local opponent_team_name="$2"
  local opponent_log="$3"
  local start_path="${opponent_dir}/${OPP_START_REL}"
  local start_dir
  local extra_args=()

  if [[ -n "${OPP_LAUNCH_EXTRA_ARGS}" ]]; then
    read -r -a extra_args <<< "${OPP_LAUNCH_EXTRA_ARGS}"
  fi

  case "${OPP_LAUNCH_MODE}" in
    start_script)
      start_dir="$(dirname "${start_path}")"
      if [[ "${OPP_KEY}" == "helios" && "${SERVER_SYNCH_MODE}" == "0" ]]; then
        start_dir="$(prepare_helios_async_runtime_dir "${start_path}" "${opponent_log}")"
        extra_args+=("-C")
      fi

      launch_in_dir_session \
        CURRENT_OPPONENT_LAUNCHER_PID \
        "${opponent_log}" \
        "${start_dir}" \
        ./start.sh -h "${HOST}" -p "${PORT}" -t "${opponent_team_name}" "${extra_args[@]}"
      ;;
    wrighteagle_release)
      launch_in_dir_session \
        CURRENT_OPPONENT_LAUNCHER_PID \
        "${opponent_log}" \
        "${opponent_dir}" \
        "${SCRIPTS_DIR}/launch_wrighteagle.sh" -h "${HOST}" -p "${PORT}" -t "${opponent_team_name}"
      ;;
    *)
      die "unsupported launch mode: ${OPP_LAUNCH_MODE}"
      ;;
  esac
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

  if [[ "${left_team}" == "null" || "${right_team}" == "null" ]]; then
    return 1
  fi

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
    local left_team right_team left_score right_score
    IFS=$'\t' read -r left_team right_team left_score right_score <<< "${parsed_score}"
    if [[ "${left_team}" != "null" && "${right_team}" != "null" ]]; then
      printf '%s\n' "${parsed_score}"
      return 0
    fi
  fi

  return 1
}

sync_or_default() {
  local sync_value="$1"
  local normal_value="$2"
  if [[ "${SERVER_SYNCH_MODE}" == "1" ]]; then
    printf '%s\n' "${sync_value}"
  else
    printf '%s\n' "${normal_value}"
  fi
}

collect_match_health() {
  local match_dir="$1"
  local server_log="$2"
  local opponent_log="$3"
  local opponent_team_name="$4"
  local home_dir="${match_dir}/home"
  local record_dir="${match_dir}/server_records"
  local disconnect_count=0
  local timing_count=0
  local comm_warning_count=0
  local opponent_action_count=0
  local health_status="ok"

  if [[ -f "${server_log}" ]]; then
    disconnect_count="$(python - "${server_log}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
phase = "live"
count = 0
for raw in path.open(errors="ignore"):
    if "Waiting after end of match" in raw:
        phase = "post"
    if phase == "live" and ("A player disconnected" in raw or "An online coach disconnected" in raw):
        count += 1
print(count)
PY
)"
  fi

  read -r timing_count comm_warning_count < <(
    python - "${opponent_log}" "${home_dir}" <<'PY'
from pathlib import Path
import re
import sys

severe_pat = re.compile(r"skipped server time|missed last action|lost move\?|lost MOVE|lost TURN|lost DASH|lost command TURN_NECK|lost command CHANGE_VIEW")
comm_pat = re.compile(r"lost command SAY")
py_cycle_pat = re.compile(r"cycle GameTime cycle ([0-9]+(?:\.[0-9]+)?)")
cpp_cycle_pat = re.compile(r"\[(-?\d+),\s*(-?\d+)\]")

def warning_cycle(line):
    match = py_cycle_pat.search(line)
    if match:
        return float(match.group(1))

    match = cpp_cycle_pat.search(line)
    if match:
        return float(match.group(1))

    return 9999.0

severe = 0
comm = 0
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(
            p for p in path.glob("player_*.log")
            if p.is_file()
        )
    else:
        files = []
    for file_path in files:
        with file_path.open(errors="ignore") as fh:
            for line in fh:
                cycle = warning_cycle(line)
                if severe_pat.search(line) and cycle >= 5.0:
                    severe += 1
                if comm_pat.search(line):
                    comm += 1
print(severe, comm)
PY
  )


  opponent_action_count="$(python - "${record_dir}" "${opponent_team_name}" <<'PY'
from pathlib import Path
import re
import sys

record_dir = Path(sys.argv[1])
opponent_team = sys.argv[2]
action_re = re.compile(r"\((dash|turn|kick|move|catch|tackle|change_view|turn_neck|pointto|attentionto|say|done)(?:\s|\))")
count = 0
for rcl_path in sorted(record_dir.glob("*.rcl")):
    with rcl_path.open(errors="ignore") as fh:
        for line in fh:
            if f"Recv {opponent_team}_" in line and action_re.search(line):
                count += 1
print(count)
PY
  )"

  if (( disconnect_count > 0 || opponent_action_count == 0 )); then
    health_status="suspect"
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' "${health_status}" "${disconnect_count}" "${timing_count}" "${comm_warning_count}" "${opponent_action_count}"
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
    terminate_process_group "${pid}"
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
    terminate_process_group "${pid}"
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

  if ! resolve_opponent "${opponent_name}"; then
    usage
    die "unsupported opponent_name: ${opponent_name}"
  fi

  local opponent_dir="${OPP_DIR}"
  local opponent_team_name="${OPPONENT_TEAM_NAME:-${OPP_TEAM_NAME}}"

  if [[ ! -x "${START_SCRIPT}" ]]; then
    die "our start script is not executable: ${START_SCRIPT}"
  fi

  ensure_opponent_ready "${opponent_dir}"

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

  local effective_server_delay
  local effective_connect_wait
  local effective_kick_off_wait
  local effective_game_over_wait
  local effective_home_opponent_launch_delay
  effective_server_delay="$(sync_or_default 0 "${SERVER_DELAY}")"
  effective_connect_wait="$(sync_or_default 500 "${CONNECT_WAIT}")"
  effective_kick_off_wait="$(sync_or_default 500 "${KICK_OFF_WAIT}")"
  effective_game_over_wait="$(sync_or_default 100 "${GAME_OVER_WAIT}")"
  effective_home_opponent_launch_delay="$(sync_or_default 0 "${HOME_OPPONENT_LAUNCH_DELAY}")"

  local run_ts
  run_ts="$(date +%Y%m%d_%H%M%S)"
  local run_id="${RUN_ID:-${run_ts}_$$}"
  local label_suffix=""
  local run_label_sanitized=""
  if [[ -n "${RUN_LABEL}" ]]; then
    run_label_sanitized="$(sanitize_label "${RUN_LABEL}")"
    if [[ -n "${run_label_sanitized}" ]]; then
      label_suffix="_${run_label_sanitized}"
    fi
  fi

  local result_file="${RESULT_DIR}/${opponent_name}${label_suffix}_${run_id}.txt"
  local run_log_dir="${MATCH_LOG_ROOT}/${opponent_name}${label_suffix}_${run_id}"
  mkdir -p "${run_log_dir}"

  local wins=0
  local draws=0
  local losses=0

  cat >"${result_file}" <<EOF
RoboCup 2D Match Report
timestamp: ${run_ts}
run_id: ${run_id}
run_label: ${run_label_sanitized:-none}
experiment_profile: ${ROBOCUP_EXPERIMENT_PROFILE:-baseline}
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
  log "server synch mode: ${SERVER_SYNCH_MODE}"

  CURRENT_OPPONENT_DIR="${opponent_dir}"
  CURRENT_OPPONENT_KILL_PATTERNS="${OPP_KILL_PATTERNS}"
  trap cleanup_match_processes EXIT INT TERM

  local i
  for (( i = 1; i <= num_matches; i++ )); do
    cleanup_match_processes
    CURRENT_OPPONENT_DIR="${opponent_dir}"
    CURRENT_OPPONENT_KILL_PATTERNS="${OPP_KILL_PATTERNS}"

    local match_dir="${run_log_dir}/match_$(printf '%03d' "${i}")"
    local record_dir="${match_dir}/server_records"
    mkdir -p "${match_dir}" "${record_dir}" "${match_dir}/home"

    local server_log="${match_dir}/rcssserver.log"
    local home_log="${match_dir}/home_launcher.log"
    local opponent_log="${match_dir}/opponent_launcher.log"
    local monitor_log="${match_dir}/rcssmonitor.log"

    log "starting match ${i}/${num_matches}"

    local server_args=(
      "server::port=${PORT}"
      "server::coach_port=$((PORT + 1))"
      "server::olcoach_port=$((PORT + 2))"
      "server::auto_mode=true"
      "server::synch_mode=${SERVER_SYNCH_MODE}"
      "server::synch_micro_sleep=${SERVER_SYNCH_MICRO_SLEEP}"
      "server::half_time=${HALF_TIME_SECONDS}"
      "server::nr_normal_halfs=${NR_NORMAL_HALFS}"
      "server::connect_wait=${effective_connect_wait}"
      "server::kick_off_wait=${effective_kick_off_wait}"
      "server::game_over_wait=${effective_game_over_wait}"
      "server::game_log_dir=${record_dir}"
      "server::text_log_dir=${record_dir}"
      "server::keepaway_log_dir=${record_dir}"
    )
    if [[ "${OPP_KEY}" == "helios" && "${SERVER_SYNCH_MODE}" == "0" ]]; then
      server_args+=("player::allow_mult_default_type=true")
    fi

    launch_in_session \
      CURRENT_SERVER_PID \
      "${server_log}" \
      "${rcssserver_bin}" \
      "${server_args[@]}"

    sleep "${effective_server_delay}"

    if [[ "${VISUAL}" == "1" ]]; then
      launch_in_session \
        CURRENT_MONITOR_PID \
        "${monitor_log}" \
        "${rcssmonitor_bin}" \
        --connect \
        --server-host "${HOST}" \
        --server-port "${PORT}"
      sleep "${MONITOR_DELAY}"
    fi

  local home_env=(
    LOG_DIR="${match_dir}/home"
    DISABLE_FILE_LOG="${MATCH_DISABLE_INTERNAL_FILE_LOGS}"
    PLAYER_DELAY="$(sync_or_default 0.03 "${PLAYER_DELAY:-0.1}")"
  )
  if [[ "${OPP_KEY}" == "helios" && "${SERVER_SYNCH_MODE}" == "0" ]]; then
    home_env+=(ROBOCUP_DISABLE_COACH_SUBSTITUTIONS=1)
  fi

  if [[ "${LAUNCH_OPPONENT_FIRST}" == "1" ]]; then
      launch_opponent "${opponent_dir}" "${opponent_team_name}" "${opponent_log}"
      sleep "${effective_home_opponent_launch_delay}"

      launch_in_session \
        CURRENT_HOME_LAUNCHER_PID \
        "${home_log}" \
        env "${home_env[@]}" "${START_SCRIPT}" "${MY_TEAM_NAME}" "${HOST}" "${PORT}"
    else
      launch_in_session \
        CURRENT_HOME_LAUNCHER_PID \
        "${home_log}" \
        env "${home_env[@]}" "${START_SCRIPT}" "${MY_TEAM_NAME}" "${HOST}" "${PORT}"

      sleep "${effective_home_opponent_launch_delay}"
      launch_opponent "${opponent_dir}" "${opponent_team_name}" "${opponent_log}"
    fi

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
    local health_fields health_status disconnect_count timing_count comm_warning_count opponent_action_count
    health_fields="$(collect_match_health "${match_dir}" "${server_log}" "${opponent_log}" "${opponent_team_name}")"
    IFS=$'\t' read -r health_status disconnect_count timing_count comm_warning_count opponent_action_count <<< "${health_fields}"
    echo "  health: ${health_status}" >>"${result_file}"
    echo "  disconnects: ${disconnect_count}" >>"${result_file}"
    echo "  timing_warnings: ${timing_count}" >>"${result_file}"
    echo "  comm_warnings: ${comm_warning_count}" >>"${result_file}"
    echo "  opponent_actions: ${opponent_action_count}" >>"${result_file}"
  done

  cat >>"${result_file}" <<EOF
---
Summary:
W-D-L = ${wins}-${draws}-${losses}
EOF

  log "summary W-D-L: ${wins}-${draws}-${losses}"
  log "result file: ${result_file}"
  if [[ -n "${RUN_MATCH_RESULT_PATH_FILE}" ]]; then
    mkdir -p "$(dirname "${RUN_MATCH_RESULT_PATH_FILE}")"
    printf '%s\n' "${result_file}" >"${RUN_MATCH_RESULT_PATH_FILE}"
  fi
}

main "$@"
