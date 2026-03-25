#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRAIN_ENV_NAME="${ROBOCUP_TRAIN_CONDA_ENV:-rl_robot}"

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
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
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

CONDA_SH="$(find_conda_sh || true)"
if [[ -n "${CONDA_SH}" ]]; then
  # shellcheck disable=SC1090
  source "${CONDA_SH}"
  conda activate "${TRAIN_ENV_NAME}"
fi

export ROBOCUP_RL_MODE=1
export ROBOCUP_RL_CONTROL_UNUM="${ROBOCUP_RL_CONTROL_UNUM:-10}"
export ROBOCUP_PLAYER_PYTHON="${ROBOCUP_PLAYER_PYTHON:-$(resolve_player_python)}"
export PYTHONUNBUFFERED=1

cd "${PROJECT_ROOT}"
python -u -m train.train_loop "$@"
