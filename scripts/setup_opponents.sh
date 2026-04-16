#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPP_ROOT="${PROJECT_ROOT}/opponents"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
source "${SCRIPTS_DIR}/opponents_registry.sh"

HELIOS_LIBRCSC_REPO="https://github.com/helios-base/librcsc.git"
CYRUS_TEAM_LIBRCSC_REPO="https://github.com/Cyrus2D/cyrus-soccer-simulation-lib.git"
STARTER_LIBRCSC_REPO="https://github.com/RCSS-IR/StarterLibRCSC-V2.git"
CPPDNN_REPO="https://github.com/Cyrus2D/CppDNN.git"

LIBRCSC_SRC_DIR="${OPP_ROOT}/librcsc"
CYRUS_TEAM_LIBRCSC_SRC_DIR="${OPP_ROOT}/cyrus_team_librcsc"
STARTER_LIBRCSC_SRC_DIR="${OPP_ROOT}/starter_librcsc"
CPPDNN_SRC_DIR="${OPP_ROOT}/CppDNN"

CYRUS_LIBRCSC_PREFIX="${CYRUS_LIBRCSC_PREFIX:-${OPP_ROOT}/local_cyrus}"
HELIOS_LIBRCSC_PREFIX="${HELIOS_LIBRCSC_PREFIX:-${OPP_ROOT}/local_helios}"
CYRUS_TEAM_LIBRCSC_PREFIX="${CYRUS_TEAM_LIBRCSC_PREFIX:-${OPP_ROOT}/local_cyrus_team}"
FOXSY_LIBRCSC_PREFIX="${FOXSY_LIBRCSC_PREFIX:-${OPP_ROOT}/local_foxsy}"
STARTER_LIBRCSC_PREFIX="${STARTER_LIBRCSC_PREFIX:-${OPP_ROOT}/local_starter}"
CYRUS_LIBRCSC_REF="${CYRUS_LIBRCSC_REF:-19175f339dcb5c3f61b56a8c1bff5345109f22ef}"
HELIOS_LIBRCSC_REF="${HELIOS_LIBRCSC_REF:-__origin_default__}"
CYRUS_TEAM_LIBRCSC_REF="${CYRUS_TEAM_LIBRCSC_REF:-__origin_default__}"
FOXSY_LIBRCSC_REF="${FOXSY_LIBRCSC_REF:-__origin_default__}"
STARTER_LIBRCSC_REF="${STARTER_LIBRCSC_REF:-__origin_default__}"

JOBS="${JOBS:-$(nproc)}"
EXTRA_CXXFLAGS="${EXTRA_CXXFLAGS:-}"
CXXFLAGS_C17="${EXTRA_CXXFLAGS} -std=c++17"

usage() {
  cat <<EOF >&2
Usage: ./scripts/setup_opponents.sh [opponent_key ...]

If no opponent_key is provided, builds the default stable opponent pool:
$(default_setup_opponent_keys | sed 's/^/  /')

Available opponent keys:
$(opponent_usage_lines | sed 's/^/  /')
EOF
}

log() {
  printf '[setup_opponents] %s\n' "$*"
}

die() {
  printf '[setup_opponents] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "missing required command: $1"
  fi
}

run_with_retry() {
  local max_attempts="$1"
  shift

  local attempt
  for (( attempt = 1; attempt <= max_attempts; attempt++ )); do
    if "$@"; then
      return 0
    fi
    if (( attempt < max_attempts )); then
      log "Command failed (attempt ${attempt}/${max_attempts}), retrying in 2s: $*"
      sleep 2
    fi
  done

  return 1
}

clone_or_update_repo() {
  local repo_url="$1"
  local target_dir="$2"
  local repo_ref="${3:-}"

  if [[ -d "${target_dir}/.git" ]]; then
    log "Fetching repo updates: ${target_dir}"
    if ! run_with_retry 3 git -C "${target_dir}" fetch --all --tags --prune; then
      log "WARNING: failed to fetch ${target_dir}; using existing checkout."
    fi
  else
    log "Cloning ${repo_url} -> ${target_dir}"
    if [[ -n "${repo_ref}" ]]; then
      run_with_retry 3 git clone --branch "${repo_ref}" "${repo_url}" "${target_dir}" || die "failed to clone repo: ${repo_url}"
    else
      run_with_retry 3 git clone "${repo_url}" "${target_dir}" || die "failed to clone repo: ${repo_url}"
    fi
  fi

  if [[ -n "${repo_ref}" ]]; then
    if ! run_with_retry 3 git -C "${target_dir}" checkout -f "${repo_ref}"; then
      die "failed to checkout repo ref ${repo_ref} in ${target_dir}"
    fi
    if ! run_with_retry 3 git -C "${target_dir}" pull --ff-only origin "${repo_ref}"; then
      log "WARNING: failed to fast-forward ${target_dir} on ${repo_ref}; using checked-out revision."
    fi
  else
    if ! run_with_retry 3 git -C "${target_dir}" pull --ff-only; then
      log "WARNING: failed to update ${target_dir}; using existing checkout."
    fi
  fi
}

resolve_librcsc_ref_label() {
  local source_dir="$1"
  local requested_ref="$2"

  if [[ "${requested_ref}" == "__origin_default__" ]]; then
    local default_remote_ref
    default_remote_ref="$(git -C "${source_dir}" symbolic-ref -q --short refs/remotes/origin/HEAD || true)"
    if [[ -z "${default_remote_ref}" ]]; then
      printf '%s\n' "master"
      return 0
    fi
    printf '%s\n' "${default_remote_ref#origin/}"
    return 0
  fi

  printf '%s\n' "${requested_ref}"
}

checkout_librcsc_ref() {
  local source_dir="$1"
  local requested_ref="$2"
  local resolved_ref
  resolved_ref="$(resolve_librcsc_ref_label "${source_dir}" "${requested_ref}")"

  printf '[setup_opponents] Checking out librcsc ref: %s\n' "${resolved_ref}" >&2
  if ! run_with_retry 3 git -C "${source_dir}" checkout -f "${resolved_ref}"; then
    die "failed to checkout librcsc ref: ${resolved_ref}"
  fi

  printf '%s\n' "${resolved_ref}"
}

patch_librcsc_param_map() {
  local source_dir="$1"
  local header="${source_dir}/rcsc/param/param_map.h"
  local source="${source_dir}/rcsc/param/param_map.cpp"

  if [[ ! -f "${header}" ]] || [[ ! -f "${source}" ]]; then
    die "librcsc ParamMap sources not found"
  fi

  python3 - "${header}" "${source}" <<'PY'
import pathlib
import sys

header = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])

header_text = header.read_text(encoding="utf-8")
header_text = header_text.replace("#include <unordered_map>", "#include <map>")
header_text = header_text.replace(
    "using Map = std::unordered_map< std::string, ParamEntity::Ptr >;",
    "using Map = std::map< std::string, ParamEntity::Ptr >;",
)
header.write_text(header_text, encoding="utf-8")

source_text = source.read_text(encoding="utf-8")
source_text = source_text.replace(
    "            std::unordered_map< std::string, ParamEntity::Ptr >::iterator it_short = M_short_name_map.find( it_long->second->shortName() );",
    "            ParamMap::Map::iterator it_short = M_short_name_map.find( it_long->second->shortName() );",
)
source.write_text(source_text, encoding="utf-8")
PY
}

patch_starter_lib_install_prefix() {
  local source_dir="$1"
  local cmake_file="${source_dir}/CMakeLists.txt"

  if [[ ! -f "${cmake_file}" ]]; then
    die "Starter librcsc CMakeLists not found: ${cmake_file}"
  fi

  python3 - "${cmake_file}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = 'set(CMAKE_INSTALL_PREFIX "$ENV{HOME}/local/starter" CACHE PATH "Install destination path" FORCE)'
new = 'set(CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}" CACHE PATH "Install destination path" FORCE)'
if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
PY
}

build_autotools_librcsc_to_prefix() {
  local repo_url="$1"
  local source_dir="$2"
  local install_prefix="$3"
  local ref_for_build="$4"
  local marker_file="${install_prefix}/.librcsc_ref"

  mkdir -p "${install_prefix}"

  if [[ -f "${marker_file}" ]] && [[ "$(cat "${marker_file}")" == "${ref_for_build}" ]] && [[ -f "${install_prefix}/include/rcsc/types.h" ]]; then
    log "Reusing librcsc at ${install_prefix} (ref ${ref_for_build})"
    return 0
  fi

  clone_or_update_repo "${repo_url}" "${source_dir}"
  local checked_out_ref
  checked_out_ref="$(checkout_librcsc_ref "${source_dir}" "${ref_for_build}")"
  patch_librcsc_param_map "${source_dir}"

  log "Building librcsc (${checked_out_ref}) -> ${install_prefix}"
  (
    cd "${source_dir}"
    if [[ -f Makefile ]]; then
      make distclean >/dev/null 2>&1 || true
    fi

    if [[ -x ./bootstrap ]]; then
      ./bootstrap
    else
      autoreconf -fi
    fi

    CXXFLAGS="${CXXFLAGS_C17}" ./configure --prefix="${install_prefix}"
    make -j"${JOBS}"
    make install
  )

  printf '%s\n' "${checked_out_ref}" > "${marker_file}"
}

build_cmake_librcsc_to_prefix() {
  local repo_url="$1"
  local source_dir="$2"
  local build_dir="$3"
  local install_prefix="$4"
  local ref_for_build="$5"
  local patch_mode="${6:-}"
  local marker_file="${install_prefix}/.librcsc_ref"
  local marker_ref="${ref_for_build}"

  mkdir -p "${install_prefix}"

  if [[ -d "${source_dir}/.git" ]]; then
    marker_ref="$(resolve_librcsc_ref_label "${source_dir}" "${ref_for_build}")"
  fi

  if [[ -f "${marker_file}" ]] && [[ "$(cat "${marker_file}")" == "${marker_ref}" ]] && [[ -f "${install_prefix}/include/rcsc/types.h" ]]; then
    log "Reusing librcsc at ${install_prefix} (ref ${marker_ref})"
    return 0
  fi

  clone_or_update_repo "${repo_url}" "${source_dir}"
  local checked_out_ref
  checked_out_ref="$(checkout_librcsc_ref "${source_dir}" "${ref_for_build}")"

  case "${patch_mode}" in
    starter)
      patch_starter_lib_install_prefix "${source_dir}"
      ;;
    "")
      ;;
    *)
      die "unsupported librcsc patch mode: ${patch_mode}"
      ;;
  esac

  log "Building cmake librcsc (${checked_out_ref}) -> ${install_prefix}"
  cmake -S "${source_dir}" -B "${build_dir}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${install_prefix}"
  cmake --build "${build_dir}" --parallel "${JOBS}"
  cmake --install "${build_dir}"

  printf '%s\n' "${checked_out_ref}" > "${marker_file}"
}

prepare_cppdnn_headers() {
  local install_prefix="$1"

  clone_or_update_repo "${CPPDNN_REPO}" "${CPPDNN_SRC_DIR}"

  local include_root="${install_prefix}/include"
  local include_dst="${include_root}/CppDNN"
  mkdir -p "${include_dst}"
  cp -f "${CPPDNN_SRC_DIR}/src/"*.h "${include_dst}/"

  log "Prepared CppDNN headers at: ${include_dst}"
}

patch_cyrus_autotools_sources() {
  local source_dir="$1"
  local makefile_am="${source_dir}/src/player/Makefile.am"

  if [[ ! -f "${makefile_am}" ]]; then
    die "Cyrus Makefile.am not found: ${makefile_am}"
  fi

  if grep -q "bhv_unmark.cpp" "${makefile_am}"; then
    return 0
  fi

  log "Patching Cyrus autotools sources list (missing unmark/data_extractor files)"
  python3 - "${makefile_am}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

needle = "main_player.cpp"
replacement = """main_player.cpp \\
\tdata_extractor/DEState.cpp \\
\tdata_extractor/offensive_data_extractor.cpp \\
\tbhv_unmark.cpp \\
\tbhv_basic_block.cpp"""

if "bhv_unmark.cpp" not in text:
    text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="utf-8")
PY
}

build_opponent() {
  local name="$1"
  local source_dir="$2"
  local librcsc_prefix="$3"
  local extra_include_parent="${4:-}"
  local configure_args=()
  local cppflags="${CPPFLAGS:-}"

  if [[ ! -d "${source_dir}" ]]; then
    die "source dir not found: ${source_dir}"
  fi

  configure_args+=("--with-librcsc=${librcsc_prefix}")

  if [[ -n "${extra_include_parent}" ]]; then
    cppflags="${cppflags} -I${extra_include_parent}"
  fi

  log "Building ${name} with librcsc prefix: ${librcsc_prefix}"
  (
    cd "${source_dir}"

    if [[ -x ./bootstrap ]]; then
      ./bootstrap
    else
      autoreconf -fi
    fi

    CPPFLAGS="${cppflags}" CXXFLAGS="${CXXFLAGS_C17}" ./configure "${configure_args[@]}"
    make -j"${JOBS}"
  )

  if [[ ! -x "${source_dir}/src/start.sh" ]]; then
    die "${name} build finished but src/start.sh is missing"
  fi
}

build_cmake_opponent() {
  local name="$1"
  local source_dir="$2"
  local build_dir="$3"
  local librcsc_prefix="$4"
  local lib_var_name="$5"
  local expected_start_rel="$6"
  local extra_include_parent="${7:-}"
  local build_env=()

  log "Building ${name} with cmake (librcsc prefix: ${librcsc_prefix})"
  if [[ -n "${extra_include_parent}" ]]; then
    build_env+=(env "CPATH=${extra_include_parent}${CPATH:+:${CPATH}}")
  fi

  "${build_env[@]}" cmake -S "${source_dir}" -B "${build_dir}" \
    -DCMAKE_BUILD_TYPE=Release \
    "-D${lib_var_name}=${librcsc_prefix}"
  "${build_env[@]}" cmake --build "${build_dir}" --parallel "${JOBS}"

  if [[ ! -f "${source_dir}/${expected_start_rel}" ]]; then
    die "${name} build finished but ${expected_start_rel} is missing"
  fi
  chmod +x "${source_dir}/${expected_start_rel}"
}

build_wrighteagle_release() {
  local source_dir="$1"

  log "Building WrightEagle release binary"
  (
    cd "${source_dir}"
    make release
  )

  if [[ ! -x "${source_dir}/Release/WEBase" ]]; then
    die "WrightEagle build finished but Release/WEBase is missing"
  fi
}

build_selected_opponent() {
  local key="$1"

  resolve_opponent "${key}" || die "unsupported opponent key: ${key}"
  clone_or_update_repo "${OPP_REPO}" "${OPP_DIR}" "${OPP_REPO_REF}"

  case "${OPP_LIB_PROFILE}" in
    cyrus_autotools)
      build_autotools_librcsc_to_prefix "${HELIOS_LIBRCSC_REPO}" "${LIBRCSC_SRC_DIR}" "${CYRUS_LIBRCSC_PREFIX}" "${CYRUS_LIBRCSC_REF}"
      prepare_cppdnn_headers "${CYRUS_LIBRCSC_PREFIX}"
      patch_cyrus_autotools_sources "${OPP_DIR}"
      build_opponent "Cyrus2DBase" "${OPP_DIR}" "${CYRUS_LIBRCSC_PREFIX}" "${CYRUS_LIBRCSC_PREFIX}/include"
      ;;
    helios_autotools)
      build_autotools_librcsc_to_prefix "${HELIOS_LIBRCSC_REPO}" "${LIBRCSC_SRC_DIR}" "${HELIOS_LIBRCSC_PREFIX}" "${HELIOS_LIBRCSC_REF}"
      build_opponent "helios-base" "${OPP_DIR}" "${HELIOS_LIBRCSC_PREFIX}"
      ;;
    cyrus_team_cmake)
      build_cmake_librcsc_to_prefix "${CYRUS_TEAM_LIBRCSC_REPO}" "${CYRUS_TEAM_LIBRCSC_SRC_DIR}" "${CYRUS_TEAM_LIBRCSC_SRC_DIR}/build" "${CYRUS_TEAM_LIBRCSC_PREFIX}" "${CYRUS_TEAM_LIBRCSC_REF}"
      prepare_cppdnn_headers "${CYRUS_TEAM_LIBRCSC_PREFIX}"
      build_cmake_opponent "cyrus-soccer-simulation-team" "${OPP_DIR}" "${OPP_BUILD_DIR}" "${CYRUS_TEAM_LIBRCSC_PREFIX}" "${OPP_CMAKE_LIB_VAR}" "${OPP_START_REL}" "${CYRUS_TEAM_LIBRCSC_PREFIX}/include"
      ;;
    foxsy_cmake)
      build_cmake_librcsc_to_prefix "${CYRUS_TEAM_LIBRCSC_REPO}" "${CYRUS_TEAM_LIBRCSC_SRC_DIR}" "${CYRUS_TEAM_LIBRCSC_SRC_DIR}/build" "${FOXSY_LIBRCSC_PREFIX}" "${FOXSY_LIBRCSC_REF}"
      prepare_cppdnn_headers "${FOXSY_LIBRCSC_PREFIX}"
      build_cmake_opponent "FoxsyCyrus2DBase" "${OPP_DIR}" "${OPP_BUILD_DIR}" "${FOXSY_LIBRCSC_PREFIX}" "${OPP_CMAKE_LIB_VAR}" "${OPP_START_REL}" "${FOXSY_LIBRCSC_PREFIX}/include"
      ;;
    starter_cmake)
      build_cmake_librcsc_to_prefix "${STARTER_LIBRCSC_REPO}" "${STARTER_LIBRCSC_SRC_DIR}" "${STARTER_LIBRCSC_SRC_DIR}/build" "${STARTER_LIBRCSC_PREFIX}" "${STARTER_LIBRCSC_REF}" "starter"
      build_cmake_opponent "StarterAgent2D-V2" "${OPP_DIR}" "${OPP_BUILD_DIR}" "${STARTER_LIBRCSC_PREFIX}" "${OPP_CMAKE_LIB_VAR}" "${OPP_START_REL}"
      ;;
    none)
      :
      ;;
    *)
      die "unsupported lib profile: ${OPP_LIB_PROFILE}"
      ;;
  esac

  case "${OPP_BUILD_SYSTEM}" in
    autotools)
      :
      ;;
    cmake)
      :
      ;;
    make_release)
      build_wrighteagle_release "${OPP_DIR}"
      ;;
    *)
      die "unsupported build system: ${OPP_BUILD_SYSTEM}"
      ;;
  esac
}

main() {
  local selected_keys=()
  local need_autotools="0"
  local need_cmake="0"

  if [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  if (( $# == 0 )); then
    mapfile -t selected_keys < <(default_setup_opponent_keys)
  else
    local key
    for key in "$@"; do
      if ! resolve_opponent "${key}"; then
        usage
        die "unsupported opponent key: ${key}"
      fi
      selected_keys+=("${key}")
    done
  fi

  require_cmd git
  require_cmd make
  require_cmd g++
  require_cmd python3

  mkdir -p "${OPP_ROOT}"

  local key
  for key in "${selected_keys[@]}"; do
    resolve_opponent "${key}" || die "unsupported opponent key: ${key}"
    case "${OPP_BUILD_SYSTEM}" in
      autotools)
        need_autotools="1"
        ;;
      cmake)
        need_cmake="1"
        ;;
    esac
    case "${OPP_LIB_PROFILE}" in
      cyrus_autotools|helios_autotools)
        need_autotools="1"
        ;;
      cyrus_team_cmake|foxsy_cmake)
        need_cmake="1"
        ;;
    esac
  done

  if [[ "${need_autotools}" == "1" ]]; then
    require_cmd autoreconf
    require_cmd autoconf
    require_cmd automake
  fi

  if [[ "${need_cmake}" == "1" ]]; then
    require_cmd cmake
  fi

  for key in "${selected_keys[@]}"; do
    build_selected_opponent "${key}"
  done

  log "Done."
  for key in "${selected_keys[@]}"; do
    resolve_opponent "${key}" || die "unsupported opponent key: ${key}"
    log "${key} ready: ${OPP_DIR}/${OPP_START_REL}"
  done
}

main "$@"
