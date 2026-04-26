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
  exp_e_box_shield
  exp_f_box_shield_transition
  exp_g_stable_box
  exp_h_stable_box_finish
  exp_i_box_finish
  exp_j_light_box_finish
  exp_k_box_finish_tight
  exp_l_light_box_finish_tight
  exp_m_box_shield_flank
  exp_ab_setplay_flank
EOF
}

if [[ -z "${PROFILE_NAME}" || "${PROFILE_NAME}" == "--help" ]]; then
  usage
  exit 1
fi

case "${PROFILE_NAME}" in
  baseline|exp_a_setplay_shield|exp_b_flank_lock|exp_c_box_clear|exp_d_transition_unlock|exp_e_box_shield|exp_f_box_shield_transition|exp_g_stable_box|exp_h_stable_box_finish|exp_i_box_finish|exp_j_light_box_finish|exp_k_box_finish_tight|exp_l_light_box_finish_tight|exp_m_box_shield_flank|exp_ab_setplay_flank)
    ;;
  exp_e|box_shield|candidate_01)
    PROFILE_NAME="exp_e_box_shield"
    ;;
  exp_f|box_shield_transition|candidate_02)
    PROFILE_NAME="exp_f_box_shield_transition"
    ;;
  exp_g|stable_box|candidate_03)
    PROFILE_NAME="exp_g_stable_box"
    ;;
  exp_h|stable_box_finish|candidate_04)
    PROFILE_NAME="exp_h_stable_box_finish"
    ;;
  exp_i|box_finish|candidate_05)
    PROFILE_NAME="exp_i_box_finish"
    ;;
  exp_j|light_box_finish|candidate_06)
    PROFILE_NAME="exp_j_light_box_finish"
    ;;
  exp_k|box_finish_tight|candidate_07)
    PROFILE_NAME="exp_k_box_finish_tight"
    ;;
  exp_l|light_box_finish_tight|candidate_08)
    PROFILE_NAME="exp_l_light_box_finish_tight"
    ;;
  exp_m|box_shield_flank|candidate_09)
    PROFILE_NAME="exp_m_box_shield_flank"
    ;;
  *)
    usage
    printf '[run_profile_fixed_baseline] ERROR: unsupported profile: %s\n' "${PROFILE_NAME}" >&2
    exit 1
    ;;
esac

export ROBOCUP_EXPERIMENT_PROFILE="${PROFILE_NAME}"
export RUN_LABEL="${RUN_LABEL:-${PROFILE_NAME}}"

if [[ "${PARALLEL_OPPONENTS:-0}" == "1" ]]; then
  exec "${PROJECT_ROOT}/scripts/run_parallel_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"
fi

exec "${PROJECT_ROOT}/scripts/run_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"
