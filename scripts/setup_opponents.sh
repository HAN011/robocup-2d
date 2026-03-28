#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPP_ROOT="${PROJECT_ROOT}/opponents"

CYRUS_REPO="https://github.com/Cyrus2D/Cyrus2DBase.git"
HELIOS_REPO="https://github.com/helios-base/helios-base.git"
LIBRCSC_REPO="https://github.com/helios-base/librcsc.git"
CPPDNN_REPO="https://github.com/Cyrus2D/CppDNN.git"

CYRUS_DIR="${OPP_ROOT}/cyrus2d"
HELIOS_DIR="${OPP_ROOT}/helios"
LIBRCSC_SRC_DIR="${OPP_ROOT}/librcsc"
CPPDNN_SRC_DIR="${OPP_ROOT}/CppDNN"

CYRUS_LIBRCSC_PREFIX="${CYRUS_LIBRCSC_PREFIX:-${OPP_ROOT}/local_cyrus}"
HELIOS_LIBRCSC_PREFIX="${HELIOS_LIBRCSC_PREFIX:-${OPP_ROOT}/local_helios}"
CYRUS_LIBRCSC_REF="${CYRUS_LIBRCSC_REF:-19175f339dcb5c3f61b56a8c1bff5345109f22ef}"
HELIOS_LIBRCSC_REF="${HELIOS_LIBRCSC_REF:-__origin_default__}"

JOBS="${JOBS:-$(nproc)}"
EXTRA_CXXFLAGS="${EXTRA_CXXFLAGS:-}"
CXXFLAGS_C17="${EXTRA_CXXFLAGS} -std=c++17"

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

  if [[ -d "${target_dir}/.git" ]]; then
    log "Updating repo: ${target_dir}"
    if ! run_with_retry 3 git -C "${target_dir}" pull --ff-only; then
      log "WARNING: failed to update ${target_dir}; using existing checkout."
    fi
  else
    log "Cloning ${repo_url} -> ${target_dir}"
    run_with_retry 3 git clone "${repo_url}" "${target_dir}" || die "failed to clone repo: ${repo_url}"
  fi
}

ensure_librcsc_repo() {
  if [[ -d "${LIBRCSC_SRC_DIR}/.git" ]]; then
    log "Fetching librcsc repo updates: ${LIBRCSC_SRC_DIR}"
    if ! run_with_retry 3 git -C "${LIBRCSC_SRC_DIR}" fetch --all --tags --prune; then
      log "WARNING: failed to fetch librcsc updates; using existing checkout."
    fi
  else
    log "Cloning ${LIBRCSC_REPO} -> ${LIBRCSC_SRC_DIR}"
    run_with_retry 3 git clone "${LIBRCSC_REPO}" "${LIBRCSC_SRC_DIR}" || die "failed to clone librcsc repo"
  fi
}

resolve_librcsc_ref_label() {
  local requested_ref="$1"

  if [[ "${requested_ref}" == "__origin_default__" ]]; then
    local default_remote_ref
    default_remote_ref="$(git -C "${LIBRCSC_SRC_DIR}" symbolic-ref -q --short refs/remotes/origin/HEAD || true)"
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
  local requested_ref="$1"
  local resolved_ref
  resolved_ref="$(resolve_librcsc_ref_label "${requested_ref}")"

  printf '[setup_opponents] Checking out librcsc ref: %s\n' "${resolved_ref}" >&2
  if ! run_with_retry 3 git -C "${LIBRCSC_SRC_DIR}" checkout -f "${resolved_ref}"; then
    die "failed to checkout librcsc ref: ${resolved_ref}"
  fi

  printf '%s\n' "${resolved_ref}"
}

patch_librcsc_param_map() {
  local header="${LIBRCSC_SRC_DIR}/rcsc/param/param_map.h"
  local source="${LIBRCSC_SRC_DIR}/rcsc/param/param_map.cpp"

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

build_librcsc_to_prefix() {
  local install_prefix="$1"
  local ref_for_build="$2"
  local marker_file="${install_prefix}/.librcsc_ref"

  mkdir -p "${install_prefix}"

  if [[ -f "${marker_file}" ]] && [[ "$(cat "${marker_file}")" == "${ref_for_build}" ]] && [[ -f "${install_prefix}/include/rcsc/types.h" ]]; then
    log "Reusing librcsc at ${install_prefix} (ref ${ref_for_build})"
    return 0
  fi

  ensure_librcsc_repo
  local checked_out_ref
  checked_out_ref="$(checkout_librcsc_ref "${ref_for_build}")"
  patch_librcsc_param_map

  log "Building librcsc (${checked_out_ref}) -> ${install_prefix}"
  (
    cd "${LIBRCSC_SRC_DIR}"
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
  local makefile_am="${CYRUS_DIR}/src/player/Makefile.am"

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

main() {
  require_cmd git
  require_cmd make
  require_cmd g++
  require_cmd autoreconf
  require_cmd autoconf
  require_cmd automake
  require_cmd python3

  mkdir -p "${OPP_ROOT}"

  clone_or_update_repo "${CYRUS_REPO}" "${CYRUS_DIR}"
  clone_or_update_repo "${HELIOS_REPO}" "${HELIOS_DIR}"

  build_librcsc_to_prefix "${CYRUS_LIBRCSC_PREFIX}" "${CYRUS_LIBRCSC_REF}"
  build_librcsc_to_prefix "${HELIOS_LIBRCSC_PREFIX}" "${HELIOS_LIBRCSC_REF}"

  prepare_cppdnn_headers "${CYRUS_LIBRCSC_PREFIX}"
  patch_cyrus_autotools_sources

  build_opponent "Cyrus2DBase" "${CYRUS_DIR}" "${CYRUS_LIBRCSC_PREFIX}" "${CYRUS_LIBRCSC_PREFIX}/include"
  build_opponent "helios-base" "${HELIOS_DIR}" "${HELIOS_LIBRCSC_PREFIX}"

  log "Done."
  log "Cyrus start script: ${CYRUS_DIR}/src/start.sh"
  log "Helios start script: ${HELIOS_DIR}/src/start.sh"
}

main "$@"
