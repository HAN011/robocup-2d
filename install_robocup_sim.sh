#!/usr/bin/env bash

set -euo pipefail

RCSSSERVER_REPO="https://github.com/rcsoccersim/rcssserver"
RCSSMONITOR_REPO="https://github.com/rcsoccersim/rcssmonitor"
RCSSSERVER_TAG_REGEX='^rcssserver-19\.0\.[0-9]+$'
RCSSMONITOR_TAG_REGEX='^rcssmonitor-19\.0\.[0-9]+$'
BUILD_ROOT="${BUILD_ROOT:-$HOME/.cache/robocup-installer}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-robocup2d}"
CONDA_PYTHON_VERSION="${CONDA_PYTHON_VERSION:-3.11}"
APT_UPDATED=0
CONDA_BIN=""

log() {
  echo "[INFO] $*"
}

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

refresh_linker_cache() {
  log "Refreshing shared library cache..."
  run_as_root ldconfig
}

apt_install_if_missing() {
  local missing=()
  local pkg

  for pkg in "$@"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done

  if [[ "${#missing[@]}" -eq 0 ]]; then
    log "APT dependencies already present."
    return
  fi

  if [[ "${APT_UPDATED}" -eq 0 ]]; then
    log "Updating APT package lists..."
    run_as_root apt-get update
    APT_UPDATED=1
  fi

  log "Installing APT packages: ${missing[*]}"
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

resolve_latest_tag() {
  local repo="$1"
  local tag_regex="$2"
  local tag

  tag="$(
    git ls-remote --tags --refs "$repo" \
      | awk '{print $2}' \
      | sed 's#refs/tags/##' \
      | grep -E "$tag_regex" \
      | sort -V \
      | tail -n1
  )"

  if [[ -z "$tag" ]]; then
    die "Could not resolve a tag matching $tag_regex from $repo"
  fi

  printf '%s\n' "$tag"
}

extract_semver_from_binary() {
  local binary="$1"
  local output version
  local flags=(--version -version -v)
  local flag

  for flag in "${flags[@]}"; do
    output="$(timeout 5 "$binary" "$flag" 2>&1 || true)"
    version="$(printf '%s\n' "$output" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)"
    if [[ -n "$version" ]]; then
      printf '%s\n' "$version"
      return 0
    fi
  done

  return 1
}

binary_has_expected_version() {
  local binary="$1"
  local version_regex="$2"
  local version

  if ! command -v "$binary" >/dev/null 2>&1; then
    return 1
  fi

  version="$(extract_semver_from_binary "$binary" || true)"
  if [[ -z "$version" ]]; then
    return 1
  fi

  [[ "$version" =~ $version_regex ]]
}

clone_and_build_with_cmake() {
  local name="$1"
  local repo="$2"
  local tag="$3"
  local src_dir="$BUILD_ROOT/$name-$tag"
  local build_dir="$src_dir/build"

  log "Preparing source tree for $name ($tag)..."
  rm -rf "$src_dir"
  git clone --depth 1 --branch "$tag" "$repo" "$src_dir"

  log "Configuring $name with CMake..."
  cmake -S "$src_dir" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release

  log "Building $name..."
  cmake --build "$build_dir" --parallel "$(nproc)"

  log "Installing $name..."
  run_as_root cmake --install "$build_dir"
}

find_conda() {
  local candidate
  local candidates=()

  if command -v conda >/dev/null 2>&1; then
    candidates+=("$(command -v conda)")
  fi

  candidates+=(
    "$HOME/anaconda3/bin/conda"
    "$HOME/miniconda3/bin/conda"
    "$HOME/mambaforge/bin/conda"
    "/opt/conda/bin/conda"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      CONDA_BIN="$candidate"
      return 0
    fi
  done

  die "conda was not found. Install Anaconda/Miniconda first or add conda to PATH."
}

conda_cmd() {
  "$CONDA_BIN" "$@"
}

conda_env_exists() {
  conda_cmd env list --json | python3 -c '
import json
import os
import sys

env_name = sys.argv[1]
data = json.load(sys.stdin)

for prefix in data.get("envs", []):
    if os.path.basename(prefix) == env_name:
        raise SystemExit(0)

raise SystemExit(1)
' "$CONDA_ENV_NAME"
}

ensure_conda_env() {
  if conda_env_exists; then
    log "Conda environment already exists: $CONDA_ENV_NAME"
  else
    log "Creating conda environment: $CONDA_ENV_NAME (python=$CONDA_PYTHON_VERSION)"
    conda_cmd create -y -n "$CONDA_ENV_NAME" "python=$CONDA_PYTHON_VERSION" pip
  fi

  if ! conda_cmd run -n "$CONDA_ENV_NAME" python -m pip --version >/dev/null 2>&1; then
    log "Installing pip into conda environment: $CONDA_ENV_NAME"
    conda_cmd install -y -n "$CONDA_ENV_NAME" pip
  fi
}

conda_run_python() {
  conda_cmd run -n "$CONDA_ENV_NAME" python "$@"
}

conda_python_dist_installed() {
  local dist_name="$1"

  conda_run_python - "$dist_name" <<'PY'
import importlib.metadata
import sys

dist = sys.argv[1]

try:
    importlib.metadata.version(dist)
except importlib.metadata.PackageNotFoundError:
    raise SystemExit(1)
PY
}

conda_pip_dist_available() {
  local dist_name="$1"

  conda_cmd run -n "$CONDA_ENV_NAME" python -m pip index versions "$dist_name" >/dev/null 2>&1
}

install_python_dist_in_conda_env_if_missing() {
  local dist_name="$1"

  if conda_python_dist_installed "$dist_name"; then
    log "Python package already installed in conda env '$CONDA_ENV_NAME': $dist_name"
    return
  fi

  if ! conda_pip_dist_available "$dist_name"; then
    die "Python package '$dist_name' is not available from pip for conda env '$CONDA_ENV_NAME'. Install it manually or adjust the package source."
  fi

  log "Installing Python package into conda env '$CONDA_ENV_NAME': $dist_name"
  conda_cmd run -n "$CONDA_ENV_NAME" python -m pip install "$dist_name"
}

install_pyrus2d_runtime_deps() {
  local deps=(
    "numpy==1.24.2"
    "scipy==1.10.1"
    "coloredlogs==15.0.1"
    "pyrusgeom==0.1.2"
  )
  local dep

  log "Installing Pyrus2D runtime dependencies into conda env '$CONDA_ENV_NAME'..."
  for dep in "${deps[@]}"; do
    conda_cmd run -n "$CONDA_ENV_NAME" python -m pip install "$dep"
  done
}

main() {
  local rcssserver_tag
  local rcssmonitor_tag

  mkdir -p "$BUILD_ROOT"
  find_conda

  log "Installing build prerequisites for rcssserver and rcssmonitor..."
  apt_install_if_missing \
    build-essential \
    bison \
    cmake \
    flex \
    git \
    libaudio-dev \
    libboost-all-dev \
    libfontconfig1-dev \
    libglib2.0-dev \
    libxi-dev \
    libxrender-dev \
    libxt-dev \
    qt5-qmake \
    qtbase5-dev

  rcssserver_tag="$(resolve_latest_tag "$RCSSSERVER_REPO" "$RCSSSERVER_TAG_REGEX")"
  rcssmonitor_tag="$(resolve_latest_tag "$RCSSMONITOR_REPO" "$RCSSMONITOR_TAG_REGEX")"

  if binary_has_expected_version rcssserver '^19\.0\.[0-9]+$'; then
    log "rcssserver 19.0.x is already installed. Skipping."
  else
    log "rcssserver 19.0.x not found. Installing..."
    clone_and_build_with_cmake "rcssserver" "$RCSSSERVER_REPO" "$rcssserver_tag"
  fi

  if binary_has_expected_version rcssmonitor '^19\.0\.[0-9]+$'; then
    log "rcssmonitor 19.0.x is already installed. Skipping."
  else
    log "rcssmonitor 19.0.x not found. Installing..."
    clone_and_build_with_cmake "rcssmonitor" "$RCSSMONITOR_REPO" "$rcssmonitor_tag"
  fi

  refresh_linker_cache

  ensure_conda_env
  install_pyrus2d_runtime_deps

  log "Checking Python dependencies inside conda env '$CONDA_ENV_NAME'..."
  install_python_dist_in_conda_env_if_missing "pyrus2d"
  install_python_dist_in_conda_env_if_missing "torch"
  install_python_dist_in_conda_env_if_missing "numpy"

  log "Installation complete. Activate the environment with: conda activate $CONDA_ENV_NAME"
}

main "$@"
