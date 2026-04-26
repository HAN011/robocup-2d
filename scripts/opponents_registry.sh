#!/usr/bin/env bash

OPPONENTS_REGISTRY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPPONENTS_PROJECT_ROOT="$(cd "${OPPONENTS_REGISTRY_DIR}/.." && pwd)"
OPPONENTS_ROOT="${OPPONENTS_PROJECT_ROOT}/opponents"

stable_opponent_keys() {
  cat <<'EOF'
cyrus2d
helios
wrighteagle
cyrus_team
foxsy_cyrus
starter2d
EOF
}

non_helios_opponent_keys() {
  cat <<'EOF'
cyrus2d
wrighteagle
cyrus_team
foxsy_cyrus
starter2d
EOF
}

optional_opponent_keys() {
  :
}

all_opponent_keys() {
  stable_opponent_keys
  optional_opponent_keys
}

default_setup_opponent_keys() {
  stable_opponent_keys
}

selected_opponent_keys() {
  local raw_keys="${BASELINE_OPPONENT_KEYS:-}"

  if [[ -z "${raw_keys}" ]]; then
    stable_opponent_keys
    return 0
  fi

  local normalized="${raw_keys//,/ }"
  local key
  for key in ${normalized}; do
    [[ -n "${key}" ]] || continue
    if ! resolve_opponent "${key}" >/dev/null 2>&1; then
      printf '[opponents_registry] ERROR: unknown opponent key: %s\n' "${key}" >&2
      return 1
    fi
    printf '%s\n' "${key}"
  done
}

opponent_usage_lines() {
  all_opponent_keys
}

resolve_opponent() {
  local key="$1"

  OPP_KEY=""
  OPP_REPO=""
  OPP_REPO_REF=""
  OPP_DIR=""
  OPP_BUILD_DIR=""
  OPP_BUILD_SYSTEM=""
  OPP_LAUNCH_MODE=""
  OPP_LAUNCH_EXTRA_ARGS=""
  OPP_START_REL=""
  OPP_TEAM_NAME=""
  OPP_KILL_PATTERNS=""
  OPP_LIB_PROFILE=""
  OPP_CMAKE_LIB_VAR=""
  OPP_NEEDS_CPPDNN="0"
  OPP_OPTIONAL="0"
  OPP_PARALLEL_SERVER_SYNCH_MODE="1"
  OPP_LAUNCH_OPPONENT_FIRST="0"

  case "${key}" in
    cyrus2d)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/Cyrus2D/Cyrus2DBase.git"
      OPP_DIR="${OPPONENTS_ROOT}/cyrus2d"
      OPP_BUILD_SYSTEM="autotools"
      OPP_LAUNCH_MODE="start_script"
      OPP_START_REL="src/start.sh"
      OPP_TEAM_NAME="Cyrus2D_base"
      OPP_KILL_PATTERNS="${OPP_DIR}/src/sample_player|${OPP_DIR}/src/sample_coach"
      OPP_LIB_PROFILE="cyrus_autotools"
      OPP_NEEDS_CPPDNN="1"
      ;;
    helios)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/helios-base/helios-base.git"
      OPP_DIR="${OPPONENTS_ROOT}/helios"
      OPP_BUILD_SYSTEM="autotools"
      OPP_LAUNCH_MODE="start_script"
      OPP_START_REL="src/start.sh"
      OPP_TEAM_NAME="HELIOS_base"
      OPP_KILL_PATTERNS="${OPP_DIR}/src/sample_player|${OPP_DIR}/src/sample_coach"
      OPP_LIB_PROFILE="helios_autotools"
      OPP_PARALLEL_SERVER_SYNCH_MODE="0"
      OPP_LAUNCH_OPPONENT_FIRST="1"
      ;;
    wrighteagle)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/wrighteagle2d/wrighteaglebase.git"
      OPP_DIR="${OPPONENTS_ROOT}/wrighteagle"
      OPP_BUILD_SYSTEM="make_release"
      OPP_LAUNCH_MODE="wrighteagle_release"
      OPP_START_REL="Release/WEBase"
      OPP_TEAM_NAME="WEBase"
      OPP_KILL_PATTERNS="${OPP_DIR}/Release/WEBase"
      OPP_LIB_PROFILE="none"
      ;;
    cyrus_team)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/Cyrus2D/cyrus-soccer-simulation-team.git"
      OPP_DIR="${OPPONENTS_ROOT}/cyrus_team"
      OPP_BUILD_DIR="${OPP_DIR}/build"
      OPP_BUILD_SYSTEM="cmake"
      OPP_LAUNCH_MODE="start_script"
      OPP_START_REL="build/src/start.sh"
      OPP_TEAM_NAME="CYRUS"
      OPP_KILL_PATTERNS="${OPP_DIR}/build/src/sample_player|${OPP_DIR}/build/src/sample_coach"
      OPP_LIB_PROFILE="cyrus_team_cmake"
      OPP_CMAKE_LIB_VAR="TEAM_DIR_LIB"
      ;;
    foxsy_cyrus)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/Cyrus2D/FoxsyCyrus2DBase.git"
      OPP_REPO_REF="cyrus2d"
      OPP_DIR="${OPPONENTS_ROOT}/foxsy_cyrus"
      OPP_BUILD_DIR="${OPP_DIR}/build"
      OPP_BUILD_SYSTEM="cmake"
      OPP_LAUNCH_MODE="start_script"
      OPP_LAUNCH_EXTRA_ARGS="-s right"
      OPP_START_REL="build/bin/start.sh"
      OPP_TEAM_NAME="Cyrus2D_base"
      OPP_KILL_PATTERNS="${OPP_DIR}/build/bin/sample_player|${OPP_DIR}/build/bin/sample_coach"
      OPP_LIB_PROFILE="foxsy_cmake"
      OPP_CMAKE_LIB_VAR="LIBRCSC_INSTALL_DIR"
      ;;
    starter2d)
      OPP_KEY="${key}"
      OPP_REPO="https://github.com/RCSS-IR/StarterAgent2D-V2.git"
      OPP_DIR="${OPPONENTS_ROOT}/starter2d"
      OPP_BUILD_DIR="${OPP_DIR}/build"
      OPP_BUILD_SYSTEM="cmake"
      OPP_LAUNCH_MODE="start_script"
      OPP_START_REL="build/bin/start.sh"
      OPP_TEAM_NAME="STARTER_base"
      OPP_KILL_PATTERNS="${OPP_DIR}/build/bin/sample_player|${OPP_DIR}/build/bin/sample_coach"
      OPP_LIB_PROFILE="starter_cmake"
      OPP_CMAKE_LIB_VAR="LIBRCSC_INSTALL_DIR"
      ;;
    *)
      return 1
      ;;
  esac

  return 0
}
