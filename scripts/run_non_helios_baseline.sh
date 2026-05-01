#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${PROJECT_ROOT}/scripts/opponents_registry.sh"

MATCHES_PER_OPPONENT="${1:-1}"

keys="$(
  non_helios_opponent_keys | paste -sd ' ' -
)"

export BASELINE_OPPONENT_KEYS="${BASELINE_OPPONENT_KEYS:-${keys}}"
export BASE_PORT="${BASE_PORT:-6600}"

exec "${PROJECT_ROOT}/scripts/run_fixed_baseline.sh" "${MATCHES_PER_OPPONENT}"

