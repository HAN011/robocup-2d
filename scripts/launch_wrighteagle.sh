#!/usr/bin/env bash

set -euo pipefail

HOST="localhost"
PORT="6000"
VERSION="Release"
BINARY="WEBase"
TEAM_NAME="WEBase"
LOG_DIR="${LOG_DIR:-Logfiles}"
PLAYER_SLEEP="0.1"

usage() {
  cat <<'EOF' >&2
Usage: launch_wrighteagle.sh [-h host] [-p port] [-t team_name] [-v version] [-b binary]
EOF
}

while getopts "h:p:t:v:b:" flag; do
  case "${flag}" in
    h) HOST="${OPTARG}" ;;
    p) PORT="${OPTARG}" ;;
    t) TEAM_NAME="${OPTARG}" ;;
    v) VERSION="${OPTARG}" ;;
    b) BINARY="${OPTARG}" ;;
    *)
      usage
      exit 1
      ;;
  esac
done

CLIENT="./${VERSION}/${BINARY}"
if [[ ! -x "${CLIENT}" ]]; then
  printf '[launch_wrighteagle] ERROR: missing built binary: %s\n' "${CLIENT}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"

COACH_PORT=$(( PORT + 1 ))
OLCOACH_PORT=$(( PORT + 2 ))
COMMON_ARGS=(
  -team_name "${TEAM_NAME}"
  -host "${HOST}"
  -port "${PORT}"
  -coach_port "${COACH_PORT}"
  -olcoach_port "${OLCOACH_PORT}"
  -log_dir "${LOG_DIR}"
)

printf '>>>>>>>>>>>>>>>>>>>>>> %s Goalie: 1\n' "${TEAM_NAME}"
"${CLIENT}" "${COMMON_ARGS[@]}" -goalie on &
sleep 5

for (( player_num = 2; player_num <= 11; player_num++ )); do
  printf '>>>>>>>>>>>>>>>>>>>>>> %s Player: %d\n' "${TEAM_NAME}" "${player_num}"
  "${CLIENT}" "${COMMON_ARGS[@]}" &
  sleep "${PLAYER_SLEEP}"
done

sleep 3
printf '>>>>>>>>>>>>>>>>>>>>>> %s Coach\n' "${TEAM_NAME}"
"${CLIENT}" "${COMMON_ARGS[@]}" -coach on &

wait
