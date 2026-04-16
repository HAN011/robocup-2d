#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MATCHES_PER_OPPONENT="${2:-3}"
PROFILE_NAME="${1:-}"

usage() {
  cat <<'EOF' >&2
Usage: ./scripts/run_profile_fixed_baseline.sh <profile> [matches_per_opponent]

Profiles:
  baseline
  exp_a_setplay_shield
  exp_b_flank_lock
  exp_c_box_clear
  exp_d_transition_unlock
  exp_ab_setplay_flank
EOF
}

if [[ -z "${PROFILE_NAME}" || "${PROFILE_NAME}" == "--help" ]]; then
  usage
  exit 1
fi

case "${PROFILE_NAME}" in
  baseline|exp_a_setplay_shield|exp_b_flank_lock|exp_c_box_clear|exp_d_transition_unlock|exp_ab_setplay_flank)
    ;;
  *)
    usage
    printf '[run_profile_fixed_baseline] ERROR: unsupported profile: %s\n' "${PROFILE_NAME}" >&2
    exit 1
    ;;
esac

export ROBOCUP_EXPERIMENT_PROFILE="${PROFILE_NAME}"
export RUN_LABEL="${RUN_LABEL:-${PROFILE_NAME}}"

exec "${PROJECT_ROOT}/scripts/run_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"
