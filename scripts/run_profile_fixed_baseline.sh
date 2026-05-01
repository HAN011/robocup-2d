#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MATCHES_PER_OPPONENT="${2:-3}"
PROFILE_NAME="${1:-}"

usage() {
  cat <<'EOF' >&2
Usage: ./scripts/run_profile_fixed_baseline.sh <profile> [matches_per_opponent]

Profiles are resolved by player.experiment_profile, so canonical names and aliases
such as exp_o, candidate_11, guarded_light_box_finish_tight are accepted.
EOF
}

if [[ -z "${PROFILE_NAME}" || "${PROFILE_NAME}" == "--help" ]]; then
  usage
  exit 1
fi

NORMALIZED_PROFILE="$(${PYTHON:-python3} - "${PROJECT_ROOT}" "${PROFILE_NAME}" <<'PYPROFILE'
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
raw_name = sys.argv[2]
sys.path.insert(0, str(project_root))

from player.experiment_profile import normalize_experiment_profile_name

baseline_aliases = {"", "0", "default", "none", "base", "baseline"}
normalized = normalize_experiment_profile_name(raw_name)
if normalized == "baseline" and raw_name.strip().lower() not in baseline_aliases:
    raise SystemExit(1)
print(normalized)
PYPROFILE
)" || {
  usage
  printf '[run_profile_fixed_baseline] ERROR: unsupported profile: %s
' "${PROFILE_NAME}" >&2
  exit 1
}

PROFILE_NAME="${NORMALIZED_PROFILE}"
export ROBOCUP_EXPERIMENT_PROFILE="${PROFILE_NAME}"
export RUN_LABEL="${RUN_LABEL:-${PROFILE_NAME}}"

if [[ "${PARALLEL_OPPONENTS:-0}" == "1" ]]; then
  exec "${PROJECT_ROOT}/scripts/run_parallel_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"
fi

exec "${PROJECT_ROOT}/scripts/run_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"
