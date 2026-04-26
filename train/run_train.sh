#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRAIN_ENV_NAME="${ROBOCUP_TRAIN_CONDA_ENV:-}"

find_conda_sh() {
  local candidates=(
    "${HOME}/miniconda3/etc/profile.d/conda.sh"
    "${HOME}/anaconda3/etc/profile.d/conda.sh"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

resolve_player_python() {
  local candidates=(
    "${ROBOCUP_PLAYER_PYTHON:-}"
    "${PROJECT_ROOT}/python/bin/python"
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
    "${CONDA_PREFIX:-}/bin/python"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]] && "${candidate}" -c 'import pyrusgeom' >/dev/null 2>&1; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  printf '%s\n' "${PYTHON:-python3}"
}

python_supports_training() {
  local candidate="$1"
  "${candidate}" -c 'import torch, gymnasium' >/dev/null 2>&1
}

resolve_train_python() {
  local candidates=(
    "${ROBOCUP_TRAIN_PYTHON:-}"
    "${PROJECT_ROOT}/python/bin/python"
    "${CONDA_PREFIX:-}/bin/python"
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
    "$(command -v python3 2>/dev/null || true)"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]] && python_supports_training "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  printf '%s\n' "${PYTHON:-python3}"
}

CONDA_SH="$(find_conda_sh || true)"
if [[ -n "${TRAIN_ENV_NAME}" && -n "${CONDA_SH}" ]]; then
  # shellcheck disable=SC1090
  source "${CONDA_SH}"
  conda activate "${TRAIN_ENV_NAME}"
fi

TRAIN_PYTHON="${ROBOCUP_TRAIN_PYTHON:-$(resolve_train_python)}"

export ROBOCUP_RL_MODE=1
export ROBOCUP_RL_CONTROL_UNUM="${ROBOCUP_RL_CONTROL_UNUM:-10}"
export ROBOCUP_PLAYER_PYTHON="${ROBOCUP_PLAYER_PYTHON:-$(resolve_player_python)}"
export PYTHONUNBUFFERED=1

cd "${PROJECT_ROOT}"
exec "${TRAIN_PYTHON}" -u -m train.train_loop "$@"
